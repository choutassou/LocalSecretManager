import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import Store, evaluate_expression, generate_password


class Tests(unittest.TestCase):
    def test_generate(self):
        for _ in range(50):
            p = generate_password(True, False, False, 8, 12)
            self.assertTrue(8 <= len(p) <= 12)
            self.assertFalse(any(c.islower() for c in p))
            self.assertTrue(any(c.isupper() for c in p))

    def test_expr(self):
        v = {"A": True, "B": False, "C": True}
        self.assertTrue(evaluate_expression("A&&(B||C)", v))
        self.assertFalse(evaluate_expression("A && !C", v))
        with self.assertRaises(ValueError):
            evaluate_expression("A &", v)
        with self.assertRaises(ValueError):
            evaluate_expression("__import__('os')", v)

    def test_store(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(os.path.join(d, "db"), os.path.join(d, "key"))
            s.save("GitHub", "me", ["git", "code"], "secret1")
            s.save("AWS", "", ["cloud"], "secret2")
            raw = s.db.execute("SELECT password FROM entries").fetchall()
            self.assertFalse(any(b"secret" in r[0] for r in raw))
            self.assertEqual(len(s.search({"A": "git", "B": "cloud"}, "A||B")), 2)
            self.assertEqual(s.search({"A": "git", "B": "cloud"}, "A&&B"), [])
            self.assertEqual(s.search({"A": "hub"}, "A")[0]["password"], "secret1")
            with self.assertRaises(ValueError):
                s.save("x", "", ["1", "2", "3", "4"], "p")


if __name__ == "__main__":
    unittest.main()
