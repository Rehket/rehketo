from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from rehketo.agent.sweep import sweep_abandoned_runs
from rehketo.db.models import Conversation, Run, User


async def test_sweep_marks_running_runs_as_failed(
    settings_env: object,
    db_url: str,
    db: object,
) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession

    db_session: AsyncSession = db  # type: ignore[assignment]

    u = User(id=uuid4(), display_name="A", email="a@x")
    db_session.add(u)
    await db_session.flush()
    conv = Conversation(id=uuid4(), user_id=u.id, title="t")
    db_session.add(conv)
    await db_session.commit()

    run_id = uuid4()
    db_session.add(
        Run(
            id=run_id,
            conversation_id=conv.id,
            user_id=u.id,
            status="running",
            model="claude-sonnet-4-6",
            started_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    await sweep_abandoned_runs()

    # Use a fresh session to avoid SQLAlchemy identity-map returning stale state.
    fresh_engine = create_async_engine(db_url, future=True)
    maker = async_sessionmaker(fresh_engine, expire_on_commit=False)
    async with maker() as s:
        run = (await s.execute(select(Run).where(Run.id == run_id))).scalar_one()
    await fresh_engine.dispose()

    assert run.status == "failed"
    assert isinstance(run.error, dict)
    assert run.error["code"] == "process_restart"
