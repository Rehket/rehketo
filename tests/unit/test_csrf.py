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
    """CSRF TTL now tracks SESSION_TTL_MINUTES. Advance time past the default
    7 days + slack to confirm the signed token is rejected as expired."""
    token = issue_csrf_token("s-1")
    future = time.time() + 60 * 60 * 24 * 8  # 8 days — past the 7-day default
    monkeypatch.setattr(time, "time", lambda: future)
    assert not verify_csrf_token("s-1", token)


def test_verify_honors_custom_session_ttl(
    settings_env: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid session with a custom SESSION_TTL_MINUTES must produce a CSRF
    token whose verification window matches — not the old hardcoded 24h."""
    from rehketo.config import get_settings

    settings_env.setenv("SESSION_TTL_MINUTES", "60")  # 1 hour
    get_settings.cache_clear()

    real_time = time.time
    token = issue_csrf_token("s-1")

    # 30 minutes in: still valid.
    monkeypatch.setattr(time, "time", lambda: real_time() + 60 * 30)
    assert verify_csrf_token("s-1", token)


def test_verify_matches_session_ttl_at_upper_bound(
    settings_env: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard against reintroducing a 24h hardcoded TTL: with a
    3-day SESSION_TTL_MINUTES, a 2-day-old token must still verify, but a
    4-day-old one must not."""
    from rehketo.config import get_settings

    settings_env.setenv("SESSION_TTL_MINUTES", str(60 * 24 * 3))  # 3 days
    get_settings.cache_clear()

    real_time = time.time
    token = issue_csrf_token("s-1")

    monkeypatch.setattr(time, "time", lambda: real_time() + 60 * 60 * 24 * 2)
    assert verify_csrf_token("s-1", token)

    monkeypatch.setattr(time, "time", lambda: real_time() + 60 * 60 * 24 * 4)
    assert not verify_csrf_token("s-1", token)
