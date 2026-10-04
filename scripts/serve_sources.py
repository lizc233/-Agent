from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from urllib.parse import unquote, urlparse

from backend.config import load_settings
from backend.rules import load_rules
from backend.source_pages import find_rule, render_rule_page


SETTINGS = load_settings(require_database=False)
RULES = load_rules(SETTINGS)


class SourceHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = unquote(urlparse(self.path).path)
        if not path.startswith("/sources/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        rule_id = path.removeprefix("/sources/").strip("/")
        rule = find_rule(RULES, rule_id)
        if rule is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Rule Not Found")
            return
        content = render_rule_page(rule).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    port = int(os.getenv("SOURCE_SERVER_PORT", "8000"))
    print(f"Rule source server: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), SourceHandler).serve_forever()
