"""messages composite index for ordered conversation reads

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-27 17:30:00.000000+00:00

`GET /conversations/{id}` and the agent's `_load_history` both run
``SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at``.
The 0002 schema indexes ``conversation_id`` alone, so Postgres must do an
in-memory sort of every row matching the WHERE — fine on tiny conversations,
quadratic-ish on a busy one. A composite index on
``(conversation_id, created_at)`` is a covering ordered scan: the planner
walks the leaf in order and produces results without a sort step.

Kept alongside the existing ``ix_messages_conversation_id`` (from 0002) for
v1; revisit dropping the single-column index when we have profiling data on
which queries use which.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_messages_conversation_id_created_at",
        "messages",
        ["conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_id_created_at", table_name="messages")
