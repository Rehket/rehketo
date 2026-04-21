from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import select, update

from rehketo.agent.events import transform_chunk
from rehketo.agent.graph import build_agent
from rehketo.agent.title import generate_title_if_needed
from rehketo.core.logging import get_logger
from rehketo.db import sessionmaker
from rehketo.db.models import Conversation, Message, Run

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from rehketo.runs.event_bus import RunEventBus

logger = get_logger(__name__)


async def _load_history(
    db: AsyncSession, conversation_id: UUID
) -> list[AIMessage | HumanMessage | SystemMessage]:
    msgs = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
    ).scalars().all()
    result: list[AIMessage | HumanMessage | SystemMessage] = [
        SystemMessage(content="You are a helpful assistant.")
    ]
    for m in msgs:
        text = (
            m.content
            if isinstance(m.content, str)
            else str(m.content.get("text", ""))
        )
        if m.role == "user":
            result.append(HumanMessage(content=text))
        elif m.role == "assistant":
            result.append(AIMessage(content=text))
    return result


async def run_agent(run_id: UUID, bus: RunEventBus) -> None:
    """Drive the agent for `run_id`. Called as an asyncio.Task."""
    async with sessionmaker()() as db:
        run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one()
        conversation_id: UUID = run.conversation_id

        await db.execute(
            update(Run).where(Run.id == run_id).values(
                status="running",
                started_at=datetime.now(UTC),
            )
        )
        await db.commit()
        await bus.publish(str(run_id), {"type": "run.status", "status": "running"})

        history = await _load_history(db, conversation_id)

    assembled_text = ""
    assembled_message_id: str | None = None

    try:
        async for agent in build_agent(str(run_id)):
            async for chunk in agent.astream(
                {"messages": history},
                config={"configurable": {"thread_id": str(run_id)}},
                stream_mode="messages",
            ):
                for event in transform_chunk(chunk):  # type: ignore[arg-type]
                    await bus.publish(str(run_id), event)
                    if event["type"] == "message.delta":
                        assembled_text += str(event["delta"])
                        assembled_message_id = (
                            str(event.get("message_id")) or assembled_message_id
                        )

        # Persist the assistant message and finalize the run.
        assistant_id = uuid4()
        async with sessionmaker()() as db:
            db.add(
                Message(
                    id=assistant_id,
                    conversation_id=conversation_id,
                    role="assistant",
                    content={"text": assembled_text},
                    run_id=run_id,
                )
            )
            await db.execute(
                update(Run).where(Run.id == run_id).values(
                    status="succeeded",
                    finished_at=datetime.now(UTC),
                )
            )
            await db.execute(
                update(Conversation)
                .where(Conversation.id == conversation_id)
                .values(updated_at=datetime.now(UTC))
            )
            await db.commit()

        await bus.publish(
            str(run_id),
            {
                "type": "message.complete",
                "message": {
                    "id": str(assistant_id),
                    "role": "assistant",
                    "content": {"text": assembled_text},
                    "run_id": str(run_id),
                },
            },
        )
        await bus.publish(str(run_id), {"type": "run.status", "status": "succeeded"})
        # Best-effort title generation. Fire and forget.
        asyncio.create_task(generate_title_if_needed(conversation_id))  # noqa: RUF006

    except Exception as exc:
        # Broad catch is intentional: this is a top-level task handler that
        # must finalize DB state and publish a terminal event for any failure,
        # including unexpected LangGraph / LangChain internals. CancelledError
        # is NOT a subclass of Exception in Python 3.8+, so it is not caught here.
        logger.exception("run_agent failed run_id=%s", str(run_id))
        async with sessionmaker()() as db:
            await db.execute(
                update(Run).where(Run.id == run_id).values(
                    status="failed",
                    error={"code": "llm_failure", "message": str(exc)},
                    finished_at=datetime.now(UTC),
                )
            )
            await db.commit()
        await bus.publish(
            str(run_id),
            {
                "type": "run.status",
                "status": "failed",
                "error": {"code": "llm_failure", "message": str(exc)},
            },
        )

    except asyncio.CancelledError:
        # Shield the finalizer so a second cancel during cleanup doesn't strand
        # the run in 'running' status. The re-raise at the end still propagates
        # the cancellation so asyncio marks the task as cancelled.
        async def _finalize_cancel() -> None:
            async with sessionmaker()() as db:
                await db.execute(
                    update(Run).where(Run.id == run_id).values(
                        status="cancelled",
                        finished_at=datetime.now(UTC),
                    )
                )
                await db.commit()
            await bus.publish(
                str(run_id), {"type": "run.status", "status": "cancelled"}
            )

        await asyncio.shield(_finalize_cancel())
        raise
