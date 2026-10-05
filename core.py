import json
import os
import re
import secrets
import sqlite3
import string

from cryptography.fernet import Fernet

UPPER = string.ascii_uppercase
LOWER = string.ascii_lowercase
DIGITS = string.digits
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?"


def generate_password(upper=True, lower=True, symbol=True, min_len=8, max_len=64):
    """Generate a password. Digits are always allowed."""
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
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS entries ("
            "site TEXT PRIMARY KEY, username TEXT NOT NULL DEFAULT '', "
            "keywords TEXT NOT NULL DEFAULT '[]', password BLOB NOT NULL)"
        )
        self.db.commit()

    def save(self, site, username, keywords, password):
        site = (site or "").strip()
        if not site:
            raise ValueError("site/app name is required")
        if not password:
            raise ValueError("password is required")
        keywords = [k.strip() for k in (keywords or []) if k and k.strip()]
        if len(keywords) > 3:
            raise ValueError("up to 3 keywords allowed")
        self.db.execute(
            "INSERT OR REPLACE INTO entries VALUES (?,?,?,?)",
            (site, (username or "").strip(), json.dumps(keywords),
             self.fernet.encrypt(password.encode())),
        )
        self.db.commit()

    def delete(self, site):
        self.db.execute("DELETE FROM entries WHERE site=?", (site,))
        self.db.commit()

    def search(self, conditions, expression):
        """conditions: dict 'A'..'E' -> string; returns decrypted entries."""
        conds = {k: v for k, v in conditions.items() if k in "ABCDE" and v}
        results = []
        rows = self.db.execute(
            "SELECT site, username, keywords, password FROM entries ORDER BY site"
        ).fetchall()
        for site, user, kws, pw in rows:
            kws = json.loads(kws)
            targets = [site.lower()] + [k.lower() for k in kws]
            values = {
                k: any(v.lower() in t for t in targets) for k, v in conds.items()
            }
            if evaluate_expression(expression, values):
                results.append({
                    "site": site, "username": user, "keywords": kws,
                    "password": self.fernet.decrypt(pw).decode(),
                })
        return results
