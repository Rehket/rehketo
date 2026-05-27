"""cascade deletes for conversation/run child rows

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-27 17:35:00.000000+00:00

The 0002 schema created child FKs with Postgres's default ``RESTRICT`` rule.
v1 only soft-deletes conversations (sets ``archived_at``), so this hasn't
surfaced — but the moment any path hard-deletes a conversation, every
``DELETE`` will fail with ``violates foreign key constraint``, leaving
operators to write manual cleanup SQL.

This migration encodes the intended semantics on the FKs themselves:

- ``CASCADE`` for child rows owned by their parent's lifecycle:
  - ``runs.conversation_id`` → ``conversations.id``
  - ``messages.conversation_id`` → ``conversations.id``
  - ``run_events.run_id`` → ``runs.id``
- ``SET NULL`` for the optional link from ``messages`` to a ``Run`` — the
  assistant message survives the run row going away (e.g., when a
  conversation is hard-deleted, the cascade reaches messages before runs;
  the order is undefined and we don't want a deferred FK violation).
- **Untouched**: every user-FK (``runs.user_id``, ``conversations.user_id``,
  ``identities.user_id``, ``sessions.user_id``, ``connections.user_id``,
  ``user_roles.user_id``). User deletion is an audited path with its own
  cleanup; we do not want cascade-deleting a user to wipe their history
  silently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


# (constraint_name, table, column, ref_table, ref_column, on_delete)
_FKS: tuple[tuple[str, str, str, str, str, str], ...] = (
    (
        "runs_conversation_id_fkey",
        "runs",
        "conversation_id",
        "conversations",
        "id",
        "CASCADE",
    ),
    (
        "messages_conversation_id_fkey",
        "messages",
        "conversation_id",
        "conversations",
        "id",
        "CASCADE",
    ),
    (
        "messages_run_id_fkey",
        "messages",
        "run_id",
        "runs",
        "id",
        "SET NULL",
    ),
    (
        "run_events_run_id_fkey",
        "run_events",
        "run_id",
        "runs",
        "id",
        "CASCADE",
    ),
)


def upgrade() -> None:
    for name, table, column, ref_table, ref_column, on_delete in _FKS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name,
            table,
            ref_table,
            [column],
            [ref_column],
            ondelete=on_delete,
        )


def downgrade() -> None:
    # Restore the default (RESTRICT) behavior of 0002.
    for name, table, column, ref_table, ref_column, _on_delete in _FKS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(name, table, ref_table, [column], [ref_column])
