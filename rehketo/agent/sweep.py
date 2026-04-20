from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import update

from rehketo.core.logging import get_logger
from rehketo.db import sessionmaker
from rehketo.db.models import Run

logger = get_logger(__name__)


async def sweep_abandoned_runs() -> None:
    """On startup, mark any runs stuck in `running` or `queued` as failed.

    Anything in those states at startup was abandoned by the previous
    process; the checkpointer may still have state but v1 does not resume.
    """
    async with sessionmaker()() as db:
        result = await db.execute(
            update(Run)
            .where(Run.status.in_(["queued", "running"]))
            .values(
                status="failed",
                error={
                    "code": "process_restart",
                    "message": "run abandoned by process restart",
                },
                finished_at=datetime.now(UTC),
            )
            .returning(Run.id)
        )
        ids = [row[0] for row in result.all()]
        await db.commit()
        if ids:
            logger.info("swept %d abandoned runs on startup", len(ids))
