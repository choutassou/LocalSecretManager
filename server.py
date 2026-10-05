import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from core import Store, generate_password

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.realpath(os.path.join(BASE, "static"))
MAX_BODY = 1024 * 1024
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
mimetypes.add_type("text/javascript", ".js")  # Windows registry may say text/plain
mimetypes.add_type("text/css", ".css")


def host_name(host):
    """'127.0.0.1:8000' -> '127.0.0.1', '[::1]:8000' -> '[::1]'."""
    return host.rsplit(":", 1)[0] if not host.endswith("]") and ":" in host else host


def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(data)

        def _host_ok(self):
            # Reject unexpected Host headers (DNS rebinding protection).
            host = self.headers.get("Host", "")
            if host_name(host) not in LOCAL_HOSTS:
                self._send(403, {"error": "forbidden"})
                return False
            return True

        def do_GET(self):
            if not self._host_ok():
                return
            path = urlparse(self.path).path
            rel = "index.html" if path == "/" else path.lstrip("/")
            full = os.path.realpath(os.path.join(STATIC, rel))
            if full.startswith(STATIC + os.sep) and os.path.isfile(full):
                ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
                with open(full, "rb") as f:
                    self._send(200, f.read(), ctype)
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._host_ok():
                return
            # reject cross-site requests (CSRF)
            origin = self.headers.get("Origin")
            if origin and origin.split("://", 1)[-1] != self.headers.get("Host", ""):
                return self._send(403, {"error": "forbidden"})
            try:
                n = int(self.headers.get("Content-Length", 0))
                if n < 0 or n > MAX_BODY:
                    return self._send(413, {"error": "request too large"})
                req = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(req, dict):
                    raise ValueError("request body must be a JSON object")
                path = urlparse(self.path).path
                if path == "/api/generate":
                    pw = generate_password(
                        bool(req.get("upper", True)), bool(req.get("lower", True)),
                        bool(req.get("symbol", True)),
                        req.get("min", 8), req.get("max", 64))
                    self._send(200, {"password": pw})
                elif path == "/api/entries":
                    store.save(req.get("site"), req.get("username"),
                               req.get("keywords"), req.get("password"))
                    self._send(200, {"ok": True})
                elif path == "/api/delete":
                    deleted = store.delete(req.get("site"), req.get("username"))
                    self._send(200, {"ok": True, "deleted": deleted})
                elif path == "/api/list":
                    self._send(200, {"results": store.list_all()})
                elif path == "/api/search":
                    res = store.search(req.get("conditions", {}), req.get("expression", ""))
                    self._send(200, {"results": res})
                else:
                    self._send(404, {"error": "not found"})
            except (ValueError, TypeError, AttributeError) as e:
                self._send(400, {"error": str(e)})

        def log_message(self, *a):
            pass

    return Handler


def make_server(store, port=8000, host="127.0.0.1"):
    return ThreadingHTTPServer((host, port), make_handler(store))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    data = os.environ.get("LSM_DATA_DIR", os.path.join(BASE, "data"))
    os.makedirs(data, exist_ok=True)
    store = Store(os.path.join(data, "secrets.db"), os.path.join(data, "secret.key"))
    print("http://127.0.0.1:%d" % port, flush=True)
    make_server(store, port).serve_forever()
