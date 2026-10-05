"""End-to-end tests of the HTTP API: a real server on an ephemeral port."""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import Store
from server import make_server


class ApiCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.store = Store(os.path.join(cls.tmp.name, "db"), os.path.join(cls.tmp.name, "key"))
        cls.srv = make_server(cls.store, 0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.store.close()
        cls.tmp.cleanup()

    def setUp(self):
        for e in self.store.list_all():
            self.store.delete(e["site"], e["username"])

    def req(self, method, path, body=None, headers=None, raw=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = dict(headers or {})
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if data is not None:
            h.setdefault("Content-Type", "application/json")
        c.request(method, path, body=data, headers=h)
        r = c.getresponse()
        payload = r.read()
        c.close()
        return r.status, dict(r.getheaders()), payload

    def post(self, path, body=None, **kw):
        status, _, payload = self.req("POST", path, {} if body is None else body, **kw)
        return status, json.loads(payload)

    def save(self, site, username="", keywords=(), password="pw"):
        return self.post("/api/entries", {"site": site, "username": username,
                                          "keywords": list(keywords), "password": password})


class StaticTests(ApiCase):
    def test_index_and_assets(self):
        status, h, body = self.req("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", h["Content-Type"])
        self.assertIn(b'id="root"', body)
        self.assertEqual(h["Cache-Control"], "no-store")
        import re
        for ref in re.findall(rb'(?:src|href)="\./(assets/[^"]+)"', body):
            status, h, _ = self.req("GET", "/" + ref.decode())
            self.assertEqual(status, 200, ref)
        js = re.search(rb'src="\./(assets/[^"]+\.js)"', body).group(1).decode()
        self.assertIn("javascript", self.req("GET", "/" + js)[1]["Content-Type"])

    def test_query_string_ignored(self):
        self.assertEqual(self.req("GET", "/?x=1")[0], 200)
        self.assertEqual(self.req("GET", "/index.html")[0], 200)

    def test_not_found_and_traversal(self):
        for p in ["/nope", "/assets/", "/../server.py", "/%2e%2e/server.py", "/..%5cserver.py",
                  "/assets/../../core.py", "/data/secret.key", "/%2e%2e%2fcore.py"]:
            self.assertEqual(self.req("GET", p)[0], 404, p)

    def test_security_headers(self):
        h = self.req("GET", "/")[1]
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertEqual(h["X-Frame-Options"], "DENY")


class SecurityTests(ApiCase):
    def test_foreign_origin_rejected(self):
        status, _ = self.post("/api/list", headers={"Origin": "http://evil.example"})
        self.assertEqual(status, 403)

    def test_same_origin_accepted(self):
        status, _ = self.post("/api/list", headers={"Origin": "http://127.0.0.1:%d" % self.port})
        self.assertEqual(status, 200)

    def test_foreign_host_rejected_dns_rebinding(self):
        # A rebinding page is "same origin" with its own hostname, so Host must be allow-listed.
        h = {"Host": "evil.example:%d" % self.port, "Origin": "http://evil.example:%d" % self.port}
        self.assertEqual(self.post("/api/list", headers=h)[0], 403)
        self.assertEqual(self.req("GET", "/", headers={"Host": "evil.example"})[0], 403)

    def test_localhost_host_accepted(self):
        self.assertEqual(self.post("/api/list", headers={"Host": "localhost:%d" % self.port})[0], 200)

    def test_oversized_body_rejected(self):
        status, _, _ = self.req("POST", "/api/entries", raw=b"x" * (1024 * 1024 + 1))
        self.assertEqual(status, 413)

    def test_negative_content_length(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.putrequest("POST", "/api/list")
        c.putheader("Content-Length", "-5")
        c.endheaders()
        self.assertEqual(c.getresponse().status, 413)
        c.close()


class EntryApiTests(ApiCase):
    def test_register_and_list(self):
        self.assertEqual(self.save("GitHub", "me", ["git"], "pw1")[0], 200)
        st, j = self.post("/api/list")
        self.assertEqual(st, 200)
        self.assertEqual(j["results"], [{"site": "GitHub", "username": "me", "keywords": ["git"], "password": "pw1"}])

    def test_composite_key_via_api(self):
        self.save("msn.co.jp", "user01", [], "a")
        self.save("msn.co.jp", "", [], "b")
        self.assertEqual(len(self.post("/api/list")[1]["results"]), 2)
        self.assertEqual(self.post("/api/delete", {"site": "msn.co.jp", "username": ""})[1]["deleted"], True)
        rest = self.post("/api/list")[1]["results"]
        self.assertEqual([(e["site"], e["username"]) for e in rest], [("msn.co.jp", "user01")])

    def test_delete_without_username_means_empty_username(self):
        self.save("s", "u", [], "a")
        self.save("s", "", [], "b")
        self.post("/api/delete", {"site": "s"})
        self.assertEqual([e["username"] for e in self.post("/api/list")[1]["results"]], ["u"])

    def test_delete_missing_is_not_an_error(self):
        st, j = self.post("/api/delete", {"site": "nope", "username": "x"})
        self.assertEqual((st, j["deleted"]), (200, False))

    def test_validation_errors_are_400_with_message(self):
        for body in [{"site": "", "password": "p"}, {"site": "a"}, {"site": "a", "password": ""},
                     {"site": "a", "password": "p", "keywords": ["1", "2", "3", "4"]},
                     {"site": "a", "password": "p", "keywords": "abc"},
                     {"site": 1, "password": "p"}, {"site": "a", "password": 5}]:
            st, j = self.post("/api/entries", body)
            self.assertEqual(st, 400, body)
            self.assertIn("error", j)
        self.assertEqual(self.post("/api/list")[1]["results"], [])

    def test_malformed_requests(self):
        for raw in [b"{bad json", b"[]", b'"str"', b"null", b"123"]:
            self.assertEqual(self.req("POST", "/api/entries", raw=raw)[0], 400, raw)
        self.assertEqual(self.req("POST", "/api/nope", raw=b"{}")[0], 404)

    def test_empty_body_treated_as_empty_object(self):
        self.assertEqual(self.req("POST", "/api/list")[0], 200)

    def test_api_path_with_query_string(self):
        self.assertEqual(self.req("POST", "/api/list?x=1", {})[0], 200)

    def test_get_on_api_is_not_allowed(self):
        self.assertEqual(self.req("GET", "/api/list")[0], 404)

    def test_non_ascii_roundtrip(self):
        self.save("日本のサイト", "太郎", ["キーワード"], "パス🔑")
        e = self.post("/api/list")[1]["results"][0]
        self.assertEqual((e["site"], e["username"], e["keywords"], e["password"]),
                         ("日本のサイト", "太郎", ["キーワード"], "パス🔑"))


class SearchApiTests(ApiCase):
    def setUp(self):
        super().setUp()
        self.save("GitHub", "me", ["git", "code"], "p1")
        self.save("GitHub", "", [], "p2")
        self.save("AWS", "", ["cloud"], "p3")

    def search(self, conds, expr):
        return self.post("/api/search", {"conditions": conds, "expression": expr})

    def test_search_returns_decrypted_passwords(self):
        st, j = self.search({"A": "aws"}, "A")
        self.assertEqual((st, [e["password"] for e in j["results"]]), (200, ["p3"]))

    def test_logic(self):
        self.assertEqual(len(self.search({"A": "git", "B": "cloud"}, "A||B")[1]["results"]), 3)
        self.assertEqual(self.search({"A": "git", "B": "cloud"}, "A&&B")[1]["results"], [])
        self.assertEqual(len(self.search({"A": "hub", "B": "code"}, "A&&!B")[1]["results"]), 1)

    def test_errors(self):
        for conds, expr in [({"A": "x"}, "A &&"), ({"A": ""}, "A"), ({"A": "x"}, "Z"),
                            ("bad", "A"), ({"A": 1}, "A")]:
            st, j = self.search(conds, expr)
            self.assertEqual(st, 400, (conds, expr))
            self.assertTrue(j["error"])

    def test_missing_expression_is_error(self):
        self.assertEqual(self.post("/api/search", {"conditions": {"A": "x"}})[0], 400)


class GenerateApiTests(ApiCase):
    def test_defaults(self):
        st, j = self.post("/api/generate")
        self.assertEqual(st, 200)
        self.assertTrue(8 <= len(j["password"]) <= 64)

    def test_options(self):
        st, j = self.post("/api/generate", {"upper": False, "lower": False, "symbol": False, "min": 10, "max": 10})
        self.assertTrue(j["password"].isdigit() and len(j["password"]) == 10)
        st, j = self.post("/api/generate", {"upper": True, "lower": False, "symbol": False, "min": 20, "max": 20})
        self.assertFalse(any(c.islower() for c in j["password"]))

    def test_errors(self):
        for body in [{"min": 10, "max": 5}, {"min": 0}, {"max": 5000}, {"min": "a"}, {"min": None}, {"min": 1.5}]:
            self.assertEqual(self.post("/api/generate", body)[0], 400, body)

    def test_unique(self):
        self.assertEqual(len({self.post("/api/generate", {"min": 24, "max": 24})[1]["password"] for _ in range(20)}), 20)


class ConcurrencyTests(ApiCase):
    def test_parallel_writes_and_reads(self):
        errors = []

        def worker(i):
            try:
                for j in range(15):
                    st, _ = self.save("site%d" % i, "u%d" % j, [], "p")
                    assert st == 200
                    assert self.post("/api/list")[0] == 200
                    assert self.post("/api/search", {"conditions": {"A": "site"}, "expression": "A"})[0] == 200
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        ts = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(errors, [])
        self.assertEqual(len(self.post("/api/list")[1]["results"]), 8 * 15)


if __name__ == "__main__":
    unittest.main()
