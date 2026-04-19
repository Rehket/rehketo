"""
Application logging under uvicorn's logger hierarchy.

Use get_logger(__name__) so app loggers inherit uvicorn's handler and format
when the app is run with uvicorn (e.g. "uvicorn fastapp.main:app").

Secret redaction
~~~~~~~~~~~~~~~~
All log records are automatically scrubbed of common credential patterns
(Bearer tokens, JWTs, API keys, passwords, PEM blocks, etc.) by the
:class:`LogSanitizingFilter` attached to every uvicorn handler.

The standalone helpers (:func:`redact_secrets_in_text`, :func:`sanitize_for_log`,
:func:`format_exc_for_log`, …) are also available for explicit use at call sites.
"""

from __future__ import annotations

import logging
import os
import re

# ---------------------------------------------------------------------------
# Secret-redaction patterns (compiled once at import time)
# ---------------------------------------------------------------------------

_CTRL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

_RE_BEARER = re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~-]+")
_RE_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\b")
_RE_KV_SECRET = re.compile(
    r"(?i)((?:[\w-]*_)?(?:password|passwd|pwd|client_secret|refresh_token|access_token|"
    r"api[_-]?key|apikey|authorization))\s*[=:]\s*[^\s;&,'\"<>]+"
)
_RE_URL_PARAM = re.compile(r"(?i)\b(tempauth|token|sig|signature)\s*=\s*[^\s&]+")
_RE_OPENAI_SK = re.compile(r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}")
_RE_PEM_INLINE = re.compile(r"-----BEGIN [^-]+-----[\s\S]*?-----END [^-]+-----", re.DOTALL)


# ---------------------------------------------------------------------------
# Public helpers — importable for explicit use at call sites
# ---------------------------------------------------------------------------


def redact_secrets_in_text(s: str) -> str:
    """Replace common credential patterns; keep surrounding diagnostic text."""
    if not s:
        return s
    out = _RE_PEM_INLINE.sub("<redacted-pem>", s)
    out = _RE_BEARER.sub(r"\1<redacted>", out)
    out = _RE_JWT.sub("<redacted-jwt>", out)
    out = _RE_OPENAI_SK.sub("<redacted>", out)
    out = _RE_KV_SECRET.sub(lambda m: f"{m.group(1)}=<redacted>", out)
    out = _RE_URL_PARAM.sub(lambda m: f"{m.group(1)}=<redacted>", out)
    return out


def sanitize_for_log(value: object, *, max_len: int = 256) -> str:
    """
    Return a single-line, bounded string safe to pass as a logging argument.

    Replaces control characters (including CR/LF/TAB) with spaces and truncates to *max_len*.
    """
    if value is None:
        return ""
    s = str(value).strip()
    s = _CTRL_CHARS.sub(" ", s)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def log_basename(path: object) -> str:
    """Last path segment only."""
    if path is None:
        return ""
    s = str(path).strip()
    if not s:
        return ""
    return os.path.basename(s) or s


def exc_type_for_log(exc: BaseException) -> str:
    """Exception class name and driver errno when present (no message body)."""
    name = type(exc).__name__
    errno = getattr(exc, "errno", None)
    if errno is not None:
        return f"{name}(errno={errno})"
    return name


def exception_message_for_log(exc: BaseException, *, max_len: int = 1200) -> str:
    """
    Human-readable exception text for operators: message is redacted and single-lined.

    Prefers driver ``msg`` when set (e.g. Snowflake ``DatabaseError``), else ``str(exc)``.
    """
    raw = ""
    msg = getattr(exc, "msg", None)
    if msg is not None and str(msg).strip():
        raw = str(msg).strip()
    elif str(exc).strip() and str(exc).strip() != type(exc).__name__:
        raw = str(exc).strip()
    if not raw:
        return exc_type_for_log(exc)
    return sanitize_for_log(redact_secrets_in_text(raw), max_len=max_len)


def format_exc_for_log(exc: BaseException, *, max_len: int = 1200) -> str:
    """Exception class (and errno if any) plus sanitized message, or type only if no message."""
    t = exc_type_for_log(exc)
    body = exception_message_for_log(exc, max_len=max_len)
    if body == t:
        return t
    return f"{t}: {body}"


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger under the uvicorn hierarchy so it uses uvicorn's format.

    The LogSanitizingFilter is applied to protect against log injection attacks.
    This is done automatically when the logger is created.
    """
    logger = logging.getLogger("uvicorn." + name)
    _ensure_sanitizing_filter_applied()
    return logger


def _ensure_sanitizing_filter_applied() -> None:
    """
    Ensure LogSanitizingFilter is applied to all uvicorn handlers.

    This function is called every time get_logger() is used to ensure that
    the sanitizing filter is applied as early as possible, even if handlers
    are added at module import time before uvicorn is fully initialized.

    If no handlers exist yet, creates a basic StreamHandler with the filter
    so that early logging is still protected. Uvicorn will replace/add its
    own handlers later, and we'll ensure those get the filter too.
    """
    uvicorn_logger = logging.getLogger("uvicorn")

    # If no handlers exist, add a basic one with the filter for early logging
    if not uvicorn_logger.handlers:
        handler = logging.StreamHandler()
        handler.addFilter(LogSanitizingFilter())
        uvicorn_logger.addHandler(handler)
    else:
        # Apply filter to any existing handlers that don't have it yet
        for handler in uvicorn_logger.handlers:  # type: ignore[assignment]
            # Check if filter already exists to avoid duplicates
            if not any(isinstance(f, LogSanitizingFilter) for f in handler.filters):
                handler.addFilter(LogSanitizingFilter())


class LogSanitizingFilter(logging.Filter):
    """
    Filter that sanitises every log record before it reaches a handler.

    Two layers of protection:

    1. **Log-injection prevention (CWE-117)** — strips ``\\r`` and ``\\n`` so
       attackers cannot forge multi-line log entries.
    2. **Secret redaction** — applies :func:`redact_secrets_in_text` to scrub
       Bearer tokens, JWTs, API keys, passwords, PEM blocks, and other
       credential patterns from log messages and their string arguments.

    IMPORTANT: Must be attached to log HANDLERS (not loggers) so all child loggers
    inherit the protection without needing per-call-site sanitisation.

    Usage::

        uvicorn_logger = logging.getLogger("uvicorn")
        for handler in uvicorn_logger.handlers:
            handler.addFilter(LogSanitizingFilter())
    """

    _CONTROL_CHARS = str.maketrans({"\r": "", "\n": ""})

    @staticmethod
    def _clean(s: str) -> str:
        return redact_secrets_in_text(s.translate(LogSanitizingFilter._CONTROL_CHARS))

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._clean(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._clean(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._clean(v) if isinstance(v, str) else v for v in record.args)
        return True


class EndpointAccessFilter(logging.Filter):
    """
    Filter that suppresses uvicorn access log entries for specified URL paths.

    Uvicorn access log records contain the HTTP request line in the log message
    (e.g. ``"GET /health HTTP/1.1" 200 OK``). This filter checks whether any of
    the configured *excluded_paths* appear in that message and, if so, suppresses
    the record.

    Usage::

        access_logger = logging.getLogger("uvicorn.access")
        access_logger.addFilter(EndpointAccessFilter(["/health"]))
    """

    def __init__(self, excluded_paths: list[str]) -> None:
        super().__init__()
        self.excluded_paths = excluded_paths

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(path in message for path in self.excluded_paths)
