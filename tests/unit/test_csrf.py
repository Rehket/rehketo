from __future__ import annotations

import time
from typing import TYPE_CHECKING

from rehketo.auth.csrf import issue_csrf_token, verify_csrf_token

if TYPE_CHECKING:
    import pytest


def test_issue_and_verify(settings_env: pytest.MonkeyPatch) -> None:
    token = issue_csrf_token("s-1")
    assert verify_csrf_token("s-1", token)


def test_verify_fails_for_other_session(settings_env: pytest.MonkeyPatch) -> None:
    token = issue_csrf_token("s-1")
    assert not verify_csrf_token("s-2", token)


def test_verify_fails_for_tampered(settings_env: pytest.MonkeyPatch) -> None:
    token = issue_csrf_token("s-1") + "x"
    assert not verify_csrf_token("s-1", token)


def test_verify_fails_for_expired(
    settings_env: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = issue_csrf_token("s-1")
    # Advance time by 7 days — past the 24h max_age
    future = time.time() + 60 * 60 * 24 * 7
    monkeypatch.setattr(time, "time", lambda: future)
    assert not verify_csrf_token("s-1", token)
