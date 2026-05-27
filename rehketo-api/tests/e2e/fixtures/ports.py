"""Free-port allocation via the bind-to-0 trick.

Used in session fixtures to pick a port for uvicorn-in-thread servers
without colliding. Hand the returned port to the consumer immediately
(uvicorn re-binds within milliseconds); the small window between close
and re-bind is acceptable for an isolated single-host test runner.
"""

from __future__ import annotations

import socket


def free_port() -> int:
    """Return a port the OS just assigned us on 127.0.0.1.

    Binds to port 0 (kernel chooses), reads the assigned port, closes.
    SO_REUSEADDR is set so the consumer can re-bind without TIME_WAIT.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
    finally:
        s.close()
