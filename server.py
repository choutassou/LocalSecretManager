import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core import Store, generate_password

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("LSM_DATA_DIR", os.path.join(BASE, "data"))
os.makedirs(DATA, exist_ok=True)
store = Store(os.path.join(DATA, "secrets.db"), os.path.join(DATA, "secret.key"))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(BASE, "static", "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html")
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        # reject cross-site requests (CSRF / DNS rebinding protection)
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if origin and origin.split("://", 1)[-1] != host:
            return self._send(403, {"error": "forbidden"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/api/generate":
                pw = generate_password(
                    bool(req.get("upper", True)), bool(req.get("lower", True)),
                    bool(req.get("symbol", True)),
                    int(req.get("min", 8)), int(req.get("max", 64)))
                self._send(200, {"password": pw})
            elif self.path == "/api/entries":
                store.save(req.get("site"), req.get("username"),
                           req.get("keywords"), req.get("password"))
                self._send(200, {"ok": True})
            elif self.path == "/api/delete":
                store.delete(req.get("site", ""))
                self._send(200, {"ok": True})
            elif self.path == "/api/search":
                res = store.search(req.get("conditions", {}), req.get("expression", ""))
                self._send(200, {"results": res})
            else:
                self._send(404, {"error": "not found"})
        except (ValueError, TypeError, AttributeError) as e:
            self._send(400, {"error": str(e)})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print("http://127.0.0.1:%d" % port)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
