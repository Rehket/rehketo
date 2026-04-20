from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from rehketo.agent.llm import build_chat_model
from rehketo.core.logging import get_logger
from rehketo.db import sessionmaker
from rehketo.db.models import Conversation, Message

if TYPE_CHECKING:
    from uuid import UUID

logger = get_logger(__name__)


async def generate_title_if_needed(conversation_id: UUID) -> None:
    """Best-effort async title generation. Failures are logged and swallowed."""
    try:
        async with sessionmaker()() as db:
            conv = (
                await db.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
            ).scalar_one()
            if conv.title:
                return
            msgs = (
                await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at)
                    .limit(4)
                )
            ).scalars().all()
        if not msgs:
            return

        prompt = "Summarize this exchange in 4 words or less, plain text only:\n\n"
        for m in msgs:
            text = (
                m.content.get("text", "")
                if isinstance(m.content, dict)
                else str(m.content)
            )
            prompt += f"{m.role}: {text}\n"

        model = build_chat_model()
        resp = await model.ainvoke(prompt)
        title = (
            (getattr(resp, "content", "") or "").strip().strip('"').strip(".")[:80]
        )
        if not title:
            return

        async with sessionmaker()() as db:
            await db.execute(
                update(Conversation)
                .where(Conversation.id == conversation_id)
                .values(title=title)
            )
            await db.commit()
    except Exception:  # broad catch intentional — swallow all failures
        logger.exception(
            "title generation failed for conversation %s", conversation_id
        )
