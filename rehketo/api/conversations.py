from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,  # noqa: TC002  # FastAPI needs runtime type for Depends()
)

from rehketo.db import get_session
from rehketo.db.models import Conversation, Message
from rehketo.permissions.dependencies import ResolvedPermissions, resolve_permissions

router = APIRouter(prefix="/conversations", tags=["conversations"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationOut(BaseModel):
    id: UUID


class ConversationSummary(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationList(BaseModel):
    items: list[ConversationSummary]


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: dict[str, object]
    run_id: UUID | None
    created_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageOut]


class ConversationPatch(BaseModel):
    title: str | None = None
    archived: bool | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=ConversationOut)
async def create_conversation(
    payload: ConversationCreate,
    db: Annotated[AsyncSession, Depends(get_session)],
    perms: Annotated[ResolvedPermissions, Depends(resolve_permissions)],
) -> ConversationOut:
    perms.require("chat.create_conversation", resource_type="conversation")
    conv = Conversation(id=uuid4(), user_id=perms.user_id, title=payload.title)
    db.add(conv)
    await db.commit()
    return ConversationOut(id=conv.id)


@router.get("", response_model=ConversationList)
async def list_conversations(
    db: Annotated[AsyncSession, Depends(get_session)],
    perms: Annotated[ResolvedPermissions, Depends(resolve_permissions)],
    include_archived: bool = False,
) -> ConversationList:
    perms.require("chat.view_conversation", resource_type="conversation")
    stmt = select(Conversation).where(Conversation.user_id == perms.user_id)
    if not include_archived:
        stmt = stmt.where(Conversation.archived_at.is_(None))
    stmt = stmt.order_by(Conversation.updated_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return ConversationList(
        items=[
            ConversationSummary(
                id=r.id,
                title=r.title,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    perms: Annotated[ResolvedPermissions, Depends(resolve_permissions)],
) -> ConversationDetail:
    perms.require(
        "chat.view_conversation",
        resource_type="conversation",
        resource_id=conversation_id,
    )
    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == perms.user_id,
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    msgs = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at)
        )
    ).scalars().all()
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                run_id=m.run_id,
                created_at=m.created_at,
            )
            for m in msgs
        ],
    )


@router.patch("/{conversation_id}", response_model=ConversationSummary)
async def patch_conversation(
    conversation_id: UUID,
    payload: ConversationPatch,
    db: Annotated[AsyncSession, Depends(get_session)],
    perms: Annotated[ResolvedPermissions, Depends(resolve_permissions)],
) -> ConversationSummary:
    perms.require(
        "chat.rename_conversation",
        resource_type="conversation",
        resource_id=conversation_id,
    )
    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == perms.user_id,
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    if payload.title is not None:
        conv.title = payload.title
        conv.updated_at = datetime.now(UTC)
    if payload.archived is True and conv.archived_at is None:
        conv.archived_at = datetime.now(UTC)
    if payload.archived is False:
        conv.archived_at = None

    await db.commit()
    await db.refresh(conv)
    return ConversationSummary(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    perms: Annotated[ResolvedPermissions, Depends(resolve_permissions)],
) -> Response:
    perms.require(
        "chat.delete_conversation",
        resource_type="conversation",
        resource_id=conversation_id,
    )
    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == perms.user_id,
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    if conv.archived_at is None:
        conv.archived_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=204)
