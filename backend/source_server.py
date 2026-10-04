from __future__ import annotations

from http.server import ThreadingHTTPServer
from threading import Thread

from scripts.serve_sources import SourceHandler


def start_source_server(port: int = 8000) -> tuple[ThreadingHTTPServer | None, Thread | None]:
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), SourceHandler)
    except OSError:
        return None, None
    thread = Thread(target=server.serve_forever, name="rule-source-server", daemon=True)
    thread.start()
    return server, thread
