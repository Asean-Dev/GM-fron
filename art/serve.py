"""Serves the art/ pages on http://localhost:8765 (town viewer at /viewer/, grass meadow at /meadow/).

    python3 art/serve.py [port]

Each page's index.html is written as an artifact fragment (no <html>/<head>), the way the artifact
host expects it, so this wraps it in the same document skeleton the host adds.
"""

import http.server
import os
import sys
from functools import partial
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.abspath(__file__))
SKELETON = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
    "<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
    "body{margin:0;font:14px system-ui,sans-serif}[hidden]{display:none!important}</style>"
    "</head><body>%s</body></html>"
)


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path.endswith("/"):
            path += "index.html"
        local = os.path.normpath(os.path.join(ROOT, path.lstrip("/")))
        if path.endswith(".html") and local.startswith(ROOT) and os.path.isfile(local):
            with open(local, encoding="utf-8") as f:
                body = (SKELETON % f.read()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"GM art pages: http://localhost:{port}/viewer/  http://localhost:{port}/meadow/", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=ROOT)).serve_forever()
