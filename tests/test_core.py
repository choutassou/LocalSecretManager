import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import Store, evaluate_expression, generate_password


class StoreCase(unittest.TestCase):
    def new_store(self):
        d = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # Windows: sqlite holds the file
        self.addCleanup(d.cleanup)
        s = Store(os.path.join(d.name, "db"), os.path.join(d.name, "key"))
        self.addCleanup(s.close)
        return s


class GenerateTests(unittest.TestCase):
    def test_length_and_classes(self):
        for _ in range(100):
            p = generate_password(True, False, False, 8, 12)
            self.assertTrue(8 <= len(p) <= 12)
            self.assertFalse(any(c.islower() for c in p))
            self.assertTrue(any(c.isupper() for c in p))
            self.assertTrue(any(c.isdigit() for c in p))

    def test_only_digits(self):
        p = generate_password(False, False, False, 5, 5)
        self.assertTrue(p.isdigit() and len(p) == 5)

    def test_symbols_included(self):
        for _ in range(30):
            p = generate_password(False, False, True, 6, 6)
            self.assertTrue(any(not c.isalnum() for c in p))

    def test_defaults_are_8_to_64(self):
        lens = {len(generate_password()) for _ in range(300)}
        self.assertTrue(min(lens) >= 8 and max(lens) <= 64)

    def test_invalid(self):
        for args in [(True, True, True, 0, 5), (True, True, True, 9, 8),
                     (True, True, True, 1, 2000), (True, True, True, 1, 3),
                     (True, True, True, "8", 9), (True, True, True, True, 9),
                     (True, True, True, 8.5, 9)]:
            with self.assertRaises(ValueError, msg=args):
                generate_password(*args)


class ExpressionTests(unittest.TestCase):
    def test_basic(self):
        v = {"A": True, "B": False, "C": True}
        self.assertTrue(evaluate_expression("A&&(B||C)", v))
        self.assertFalse(evaluate_expression("A && !C", v))
        self.assertTrue(evaluate_expression("!B", v))
        self.assertTrue(evaluate_expression("!!A", v))
        self.assertTrue(evaluate_expression("  A  ||  B ", v))
        self.assertFalse(evaluate_expression("B||D", v))  # D unset -> False

    def test_precedence(self):
        v = {"A": True, "B": False, "C": False}
        self.assertTrue(evaluate_expression("A||B&&C", v))       # && binds tighter
        self.assertFalse(evaluate_expression("(A||B)&&C", v))
        self.assertFalse(evaluate_expression("!A||B", v))        # ! binds tighter than ||

    def test_errors(self):
        v = {"A": True}
        for bad in ["", "   ", "A &", "A B", "(A", "A)", "&&A", "A||", "a", "F",
                    "__import__('os')", "A & B", "A | B", "!", "()", "A" * 600]:
            with self.assertRaises(ValueError, msg=bad):
                evaluate_expression(bad, v)
        with self.assertRaises(ValueError):
            evaluate_expression(None, v)

    def test_deep_nesting_is_rejected_not_crashing(self):
        with self.assertRaises(ValueError):
            evaluate_expression("(" * 400 + "A" + ")" * 400, {"A": True})


class StoreTests(StoreCase):
    def test_encrypted_at_rest_and_roundtrip(self):
        s = self.new_store()
        s.save("GitHub", "me", ["git", "code"], "secret1")
        raw = s.db.execute("SELECT password FROM entries").fetchall()
        self.assertFalse(any(b"secret1" in r[0] for r in raw))
        self.assertEqual(s.list_all()[0]["password"], "secret1")

    def test_site_required_password_required(self):
        s = self.new_store()
        for site in [None, "", "   "]:
            with self.assertRaises(ValueError):
                s.save(site, "", [], "p")
        for pw in [None, "", 0]:
            with self.assertRaises(ValueError):
                s.save("x", "", [], pw)
        with self.assertRaises(ValueError):
            s.save(123, "", [], "p")
        with self.assertRaises(ValueError):
            s.save("x", 5, [], "p")
        self.assertEqual(s.list_all(), [])

    def test_composite_primary_key(self):
        s = self.new_store()
        s.save("msn.co.jp", "user01", [], "pw-user")
        s.save("msn.co.jp", "", [], "pw-empty")
        s.save("other.jp", "user01", [], "pw-other")
        got = {(e["site"], e["username"]): e["password"] for e in s.list_all()}
        self.assertEqual(got, {("msn.co.jp", "user01"): "pw-user",
                               ("msn.co.jp", ""): "pw-empty",
                               ("other.jp", "user01"): "pw-other"})

    def test_same_key_overwrites(self):
        s = self.new_store()
        s.save("a", "u", ["k1"], "old")
        s.save("a", "u", ["k2"], "new")
        self.assertEqual(s.list_all(), [{"site": "a", "username": "u", "keywords": ["k2"], "password": "new"}])

    def test_none_username_equals_empty(self):
        s = self.new_store()
        s.save("a", None, [], "p1")
        s.save("a", "", [], "p2")
        self.assertEqual([e["password"] for e in s.list_all()], ["p2"])

    def test_whitespace_trimmed_in_key(self):
        s = self.new_store()
        s.save("  a  ", "  u ", [], "p1")
        s.save("a", "u", [], "p2")
        self.assertEqual(len(s.list_all()), 1)

    def test_password_kept_verbatim(self):
        s = self.new_store()
        s.save("a", "", [], "  sp ace ")
        self.assertEqual(s.list_all()[0]["password"], "  sp ace ")

    def test_delete_only_exact_pair(self):
        s = self.new_store()
        s.save("msn", "user01", [], "p1")
        s.save("msn", "", [], "p2")
        self.assertTrue(s.delete("msn", ""))
        self.assertEqual([e["username"] for e in s.list_all()], ["user01"])
        self.assertFalse(s.delete("msn", ""))
        self.assertFalse(s.delete("nope", "x"))
        self.assertEqual(len(s.list_all()), 1)

    def test_keywords(self):
        s = self.new_store()
        s.save("a", "", ["x", " ", "", None, " y "], "p")
        self.assertEqual(s.list_all()[0]["keywords"], ["x", "y"])
        with self.assertRaises(ValueError):
            s.save("b", "", ["1", "2", "3", "4"], "p")
        with self.assertRaises(ValueError):
            s.save("b", "", "abc", "p")
        with self.assertRaises(ValueError):
            s.save("b", "", [1], "p")
        s.save("c", "", ["日本語", "キー"], "p")
        self.assertEqual(s.search({"A": "キー"}, "A")[0]["site"], "c")

    def test_list_order(self):
        s = self.new_store()
        s.save("b", "z", [], "p")
        s.save("b", "", [], "p")
        s.save("a", "", [], "p")
        self.assertEqual([(e["site"], e["username"]) for e in s.list_all()],
                         [("a", ""), ("b", ""), ("b", "z")])

    def test_unicode_password(self):
        s = self.new_store()
        s.save("a", "", [], "パスワード🔑")
        self.assertEqual(s.list_all()[0]["password"], "パスワード🔑")


class SearchTests(StoreCase):
    def setUp(self):
        self.s = self.new_store()
        self.s.save("GitHub", "me", ["git", "code"], "secret1")
        self.s.save("GitHub", "", ["work"], "secret1b")
        self.s.save("AWS", "", ["cloud"], "secret2")

    def sites(self, cond, expr):
        return sorted((e["site"], e["username"]) for e in self.s.search(cond, expr))

    def test_or_and(self):
        self.assertEqual(len(self.s.search({"A": "git", "B": "cloud"}, "A||B")), 3)
        self.assertEqual(self.s.search({"A": "git", "B": "cloud"}, "A&&B"), [])
        self.assertEqual(self.s.search({"A": "hub"}, "A")[0]["password"], "secret1b")

    def test_all_users_of_a_site_are_returned(self):
        self.assertEqual(self.sites({"A": "github"}, "A"), [("GitHub", ""), ("GitHub", "me")])

    def test_case_insensitive_and_substring(self):
        self.assertEqual(self.sites({"A": "AWS"}, "A"), [("AWS", "")])
        self.assertEqual(self.sites({"A": "aw"}, "A"), [("AWS", "")])
        self.assertEqual(self.sites({"A": "CLOUD"}, "A"), [("AWS", "")])

    def test_username_and_password_not_searched(self):
        self.assertEqual(self.sites({"A": "me"}, "A"), [])
        self.assertEqual(self.sites({"A": "secret"}, "A"), [])

    def test_not_and_grouping(self):
        self.assertEqual(self.sites({"A": "git", "B": "work"}, "A&&!B"), [("GitHub", "me")])
        self.assertEqual(self.sites({"A": "hub", "B": "work", "C": "git"}, "A&&(B||C)"),
                         [("GitHub", ""), ("GitHub", "me")])

    def test_five_conditions(self):
        c = {"A": "git", "B": "aws", "C": "zzz", "D": "work", "E": "cloud"}
        self.assertEqual(len(self.s.search(c, "A||B||C||D||E")), 3)
        self.assertEqual(self.sites(c, "(A||B)&&(D||E)"), [("AWS", ""), ("GitHub", "")])

    def test_empty_condition_referenced_is_error(self):
        with self.assertRaises(ValueError):
            self.s.search({"A": "", "B": "x"}, "A")
        with self.assertRaises(ValueError):
            self.s.search({}, "!A")

    def test_unreferenced_empty_conditions_ok(self):
        self.assertEqual(len(self.s.search({"A": "git", "B": ""}, "A")), 2)  # both GitHub rows

    def test_bad_expression_is_error_even_if_store_empty(self):
        s = self.new_store()
        with self.assertRaises(ValueError):
            s.search({"A": "x"}, "A &&")

    def test_bad_input_types(self):
        for cond, expr in [(None, "A"), ([], "A"), ({"A": 5}, "A"), ({"A": "x"}, None), ({"A": "x"}, 5)]:
            with self.assertRaises(ValueError, msg=(cond, expr)):
                self.s.search(cond, expr)

    def test_junk_condition_keys_ignored(self):
        self.assertEqual(len(self.s.search({"A": "git", "AB": "zzz", "": "q", "F": "x"}, "A")), 2)


class MigrationTests(unittest.TestCase):
    def test_legacy_site_only_primary_key_is_migrated(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            db, key = os.path.join(d, "db"), os.path.join(d, "key")
            s = Store(db, key)
            s.save("keep", "u", ["k"], "pw")
            s.close()
            # rebuild the table the way the first release created it
            c = sqlite3.connect(db)
            c.execute("ALTER TABLE entries RENAME TO n")
            c.execute("CREATE TABLE entries (site TEXT PRIMARY KEY, username TEXT NOT NULL DEFAULT '', "
                      "keywords TEXT NOT NULL DEFAULT '[]', password BLOB NOT NULL)")
            c.execute("INSERT INTO entries SELECT site, username, keywords, password FROM n")
            c.execute("DROP TABLE n")
            c.commit()
            c.close()
            s = Store(db, key)
            try:
                self.assertEqual(s.list_all(), [{"site": "keep", "username": "u", "keywords": ["k"], "password": "pw"}])
                s.save("keep", "", [], "pw2")  # now allowed: same site, other username
                self.assertEqual(len(s.list_all()), 2)
            finally:
                s.close()

    def test_reopen_keeps_data(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            db, key = os.path.join(d, "db"), os.path.join(d, "key")
            s = Store(db, key)
            s.save("a", "", [], "p")
            s.close()
            s = Store(db, key)
            try:
                self.assertEqual(s.list_all()[0]["password"], "p")
            finally:
                s.close()


if __name__ == "__main__":
    unittest.main()
