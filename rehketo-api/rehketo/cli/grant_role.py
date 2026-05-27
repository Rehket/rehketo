"""
Bootstrap / admin CLI:
    uv run python -m rehketo.cli.grant_role alice@example.com Admin
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from rehketo.db import sessionmaker
from rehketo.db.models import User, UserRole


async def grant(email: str, role: str) -> int:
    async with sessionmaker()() as s:
        user = (
            await s.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is None:
            sys.stderr.write(f"no user with email={email}\n")
            return 2
        exists = (
            await s.execute(
                select(UserRole).where(
                    UserRole.user_id == user.id,
                    UserRole.role == role,
                )
            )
        ).scalar_one_or_none()
        if exists:
            sys.stdout.write("already has role\n")
            return 0
        s.add(UserRole(user_id=user.id, role=role))
        await s.commit()
        sys.stdout.write(f"granted {role} to {email}\n")
        return 0


_EXPECTED_ARGS = 3  # script name + email + role


def main() -> None:
    if len(sys.argv) != _EXPECTED_ARGS:
        sys.stderr.write("usage: grant_role <email> <role>\n")
        raise SystemExit(2)
    raise SystemExit(asyncio.run(grant(sys.argv[1], sys.argv[2])))


if __name__ == "__main__":
    main()
