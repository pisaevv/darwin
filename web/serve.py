"""Serves the chart page to this laptop only: just web/ and runs/, never .env.

Run:  .venv/bin/python web/serve.py          (port 8010)
      .venv/bin/python web/serve.py 8015     (another port)
"""
import http.server
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8010


class Handler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        if self.path.split("?")[0] == "/":
            self.send_response(302)
            self.send_header("Location", "/web/chart.html")
            self.end_headers()
            return None
        # Decide on the file the address really leads to, not on the address as typed.
        target = Path(self.translate_path(self.path)).resolve()
        parts = target.relative_to(ROOT).parts if target.is_relative_to(ROOT) else ()
        if not parts or parts[0] not in ("web", "runs") or any(p.startswith(".") for p in parts):
            self.send_error(404)
            return None
        return super().send_head()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), lambda *a: Handler(*a, directory=str(ROOT)))
    print(f"Chart page: http://127.0.0.1:{PORT}/web/chart.html   (Ctrl-C stops it)")
    server.serve_forever()
