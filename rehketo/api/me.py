from __future__ import annotations

from typing import Annotated
from uuid import (
    UUID,  # noqa: TC003  # used in Pydantic fields and FastAPI query params at runtime
)

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,  # noqa: TC002  # FastAPI needs runtime type for Depends()
)

from rehketo.db import get_session
from rehketo.db.models import User
from rehketo.permissions.actions import ACTIONS
from rehketo.permissions.dependencies import ResolvedPermissions, resolve_permissions

router = APIRouter(tags=["me"])


class MeOut(BaseModel):
    id: UUID
    display_name: str | None
    email: str | None
    roles: list[str]


class CapabilitiesOut(BaseModel):
    actions: list[str]


@router.get("/me", response_model=MeOut)
async def me(
    db: Annotated[AsyncSession, Depends(get_session)],
    perms: Annotated[ResolvedPermissions, Depends(resolve_permissions)],
) -> MeOut:
    user = (
        await db.execute(select(User).where(User.id == perms.user_id))
    ).scalar_one()
    return MeOut(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        roles=sorted(perms.roles),
    )


@router.get("/me/capabilities", response_model=CapabilitiesOut)
async def capabilities(
    perms: Annotated[ResolvedPermissions, Depends(resolve_permissions)],
    resource_type: str | None = None,
    resource_id: UUID | None = None,
) -> CapabilitiesOut:
    allowed = [
        a
        for a in ACTIONS
        if perms.can(a, resource_type=resource_type, resource_id=resource_id)
    ]
    return CapabilitiesOut(actions=allowed)
