import json
import os
import re
import secrets
import sqlite3
import string
import threading

from cryptography.fernet import Fernet

UPPER = string.ascii_uppercase
LOWER = string.ascii_lowercase
DIGITS = string.digits
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?"


def generate_password(upper=True, lower=True, symbol=True, min_len=8, max_len=64):
    """Generate a password. Digits are always allowed."""
    if not all(isinstance(n, int) and not isinstance(n, bool) for n in (min_len, max_len)):
        raise ValueError("length must be an integer")
    if min_len < 1 or max_len < min_len:
        raise ValueError("invalid length range")
    if max_len > 1024:
        raise ValueError("max length too large")
    pools = [DIGITS]
    if upper:
        pools.append(UPPER)
    if lower:
        pools.append(LOWER)
    if symbol:
        pools.append(SYMBOLS)
    if max_len < len(pools):
        raise ValueError("max length too small for selected character types")
    min_len = max(min_len, len(pools))
    length = min_len + secrets.randbelow(max_len - min_len + 1)
    chars = [secrets.choice(p) for p in pools]
    allchars = "".join(pools)
    chars += [secrets.choice(allchars) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


_NAMES = ("A", "B", "C", "D", "E")

# ---- C-style logic expression over A..E (&&, ||, !, parentheses) ----
_TOKEN = re.compile(r"\s*(&&|\|\||!|\(|\)|[A-E])")


def _tokenize(expr):
    pos, tokens = 0, []
    expr = expr.rstrip()
    while pos < len(expr):
        m = _TOKEN.match(expr, pos)
        if not m:
            raise ValueError("invalid expression near position %d" % (pos + 1))
        tokens.append(m.group(1))
        pos = m.end()
    return tokens


def evaluate_expression(expr, values):
    """Evaluate e.g. 'A&&(B||C)'; values maps 'A'..'E' to booleans."""
    if not isinstance(expr, str):
        raise ValueError("expression must be a string")
    if len(expr) > 500:
        raise ValueError("expression too long")
    tokens = _tokenize(expr)
    if not tokens:
        raise ValueError("empty expression")
    idx = 0

    def peek():
        return tokens[idx] if idx < len(tokens) else None

    def take():
        nonlocal idx
        idx += 1
        return tokens[idx - 1]

    def parse_or():
        v = parse_and()
        while peek() == "||":
            take()
            r = parse_and()
            v = v or r
        return v

    def parse_and():
        v = parse_not()
        while peek() == "&&":
            take()
            r = parse_not()
            v = v and r
        return v

    def parse_not():
        if peek() == "!":
            take()
            return not parse_not()
        return parse_atom()

    def parse_atom():
        t = peek()
        if t == "(":
            take()
            v = parse_or()
            if peek() != ")":
                raise ValueError("missing ')'")
            take()
            return v
        if t in ("A", "B", "C", "D", "E"):
            take()
            return bool(values.get(t, False))
        raise ValueError("unexpected token: %s" % (t or "end of expression"))

    result = parse_or()
    if idx != len(tokens):
        raise ValueError("unexpected token: %s" % tokens[idx])
    return result



class Store:
    """Encrypted entry store. An entry is identified by (site, username);
    username may be an empty string, which is a distinct record."""

    COLUMNS = "site, username, keywords, password"

    def __init__(self, db_path, key_path):
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(key)
        self.fernet = Fernet(key)
        self.lock = threading.RLock()  # one shared connection, many server threads
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        with self.lock:
            cols = self.db.execute("PRAGMA table_info(entries)").fetchall()
            if cols and sum(1 for c in cols if c[5]) == 1:
                # legacy schema: PRIMARY KEY(site) only -> migrate to (site, username)
                self.db.execute("ALTER TABLE entries RENAME TO entries_old")
                cols = []
            if not cols:
                self.db.execute(
                    "CREATE TABLE entries ("
                    "site TEXT NOT NULL, username TEXT NOT NULL DEFAULT '', "
                    "keywords TEXT NOT NULL DEFAULT '[]', password BLOB NOT NULL, "
                    "PRIMARY KEY (site, username))"
                )
                has_old = self.db.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='entries_old'").fetchone()
                if has_old:
                    self.db.execute(
                        "INSERT INTO entries SELECT %s FROM entries_old" % self.COLUMNS)
                    self.db.execute("DROP TABLE entries_old")
            self.db.commit()

    def close(self):
        with self.lock:
            self.db.close()

    @staticmethod
    def _text(value, name):
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("%s must be a string" % name)
        return value.strip()

    def save(self, site, username, keywords, password):
        """Insert or overwrite the entry identified by (site, username)."""
        site = self._text(site, "site")
        username = self._text(username, "username")
        if not site:
            raise ValueError("site/app name is required")
        if not isinstance(password, str) or not password:
            raise ValueError("password is required")
        if keywords is None:
            keywords = []
        if not isinstance(keywords, list) or not all(
                k is None or isinstance(k, str) for k in keywords):
            raise ValueError("keywords must be a list of strings")
        keywords = [k.strip() for k in keywords if k and k.strip()]
        if len(keywords) > 3:
            raise ValueError("up to 3 keywords allowed")
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO entries (%s) VALUES (?,?,?,?)" % self.COLUMNS,
                (site, username, json.dumps(keywords, ensure_ascii=False),
                 self.fernet.encrypt(password.encode())),
            )
            self.db.commit()

    def delete(self, site, username=""):
        """Delete one entry. Returns True if a row was removed."""
        site = self._text(site, "site")
        username = self._text(username, "username")
        with self.lock:
            cur = self.db.execute(
                "DELETE FROM entries WHERE site=? AND username=?", (site, username))
            self.db.commit()
            return cur.rowcount > 0

    def _rows(self):
        with self.lock:
            rows = self.db.execute(
                "SELECT %s FROM entries ORDER BY site, username" % self.COLUMNS
            ).fetchall()
        return [
            {"site": site, "username": user, "keywords": json.loads(kws),
             "password": self.fernet.decrypt(pw).decode()}
            for site, user, kws, pw in rows
        ]

    def list_all(self):
        """Return every entry with its password decrypted, ordered by site, username."""
        return self._rows()

    def search(self, conditions, expression):
        """conditions: dict 'A'..'E' -> string; returns decrypted entries.

        A condition is True for an entry when its (case-insensitive) text is
        contained in the site name or in any keyword. Referencing a condition
        whose text is empty is an error."""
        if not isinstance(conditions, dict):
            raise ValueError("conditions must be an object")
        if not isinstance(expression, str):
            raise ValueError("expression must be a string")
        conds = {}
        for k, v in conditions.items():
            if k not in _NAMES:
                continue
            if v is not None and not isinstance(v, str):
                raise ValueError("condition %s must be a string" % k)
            if v:
                conds[k] = v.lower()
        # Validate the expression up front so that errors do not depend on the data.
        evaluate_expression(expression, {k: True for k in _NAMES})
        missing = [t for t in _tokenize(expression) if t in _NAMES and t not in conds]
        if missing:
            raise ValueError("condition %s is empty" % missing[0])
        results = []
        for e in self._rows():
            targets = [e["site"].lower()] + [k.lower() for k in e["keywords"]]
            values = {k: any(v in t for t in targets) for k, v in conds.items()}
            if evaluate_expression(expression, values):
                results.append(e)
        return results
