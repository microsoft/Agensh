# Parse board-grep expressions into a small tree and parameterized SQL.
# '&' binds tighter than '|'; parentheses group terms and spaces remain literal.

from __future__ import annotations

from typing import Any, Callable, List, Tuple

_SPECIAL = "|&()"


class QueryError(ValueError):
    pass


def _tokenize(s: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    buf: List[str] = []

    def flush() -> None:
        w = "".join(buf).strip()
        buf.clear()
        if w:
            out.append(("WORD", w))

    for ch in s or "":
        if ch in _SPECIAL:
            flush()
            out.append((ch, ch))
        else:
            buf.append(ch)
    flush()
    return out


def parse(expr: str) -> Any:
    toks = _tokenize(expr)
    if not toks:
        raise QueryError("empty expression")
    pos = 0
    depth = 0

    def peek() -> str:
        return toks[pos][0] if pos < len(toks) else ""

    def parse_or() -> Any:
        nonlocal pos
        parts = [parse_and()]
        while peek() == "|":
            pos += 1
            parts.append(parse_and())
        return parts[0] if len(parts) == 1 else ("or", parts)

    def parse_and() -> Any:
        nonlocal pos
        parts = [parse_factor()]
        while peek() == "&":
            pos += 1
            parts.append(parse_factor())
        return parts[0] if len(parts) == 1 else ("and", parts)

    def parse_factor() -> Any:
        nonlocal pos, depth
        k = peek()
        if k == "(":
            pos += 1
            depth += 1
            if peek() == ")":
                raise QueryError("empty group '()' — put at least one term inside")
            inner = parse_or()
            if peek() != ")":
                raise QueryError("unbalanced '(' — missing a closing ')'")
            pos += 1
            depth -= 1
            return inner
        if k == "WORD":
            w = toks[pos][1]
            pos += 1
            return ("term", w)
        if k == ")":
            if depth > 0:
                raise QueryError("expected a term before ')'")
            raise QueryError("unexpected ')' — no matching '('")
        if k in ("&", "|"):
            raise QueryError(f"'{k}' needs a term on both sides")
        raise QueryError("expected a search term")

    node = parse_or()
    if pos != len(toks):
        k = peek()
        if k == ")":
            raise QueryError("unexpected ')' — no matching '('")
        raise QueryError(
            "missing an operator ('&' or '|') before "
            + ("'('" if k == "(" else repr(toks[pos][1]))
        )
    return node


def count_terms(node: Any) -> int:
    if node[0] == "term":
        return 1
    return sum(count_terms(c) for c in node[1])


def compile_sql(node: Any, lit: Callable[[str], str]) -> Tuple[str, List[Any]]:
    # Operators come from the parser; user terms are returned as bound parameters.
    if node[0] == "term":
        return "content LIKE %s ESCAPE '\\\\'", [lit(node[1])]
    joiner = " AND " if node[0] == "and" else " OR "
    frags: List[str] = []
    params: List[Any] = []
    for child in node[1]:
        f, p = compile_sql(child, lit)
        frags.append(f)
        params.extend(p)
    return "(" + joiner.join(frags) + ")", params


def parse_type_list(types: str, valid: Any) -> List[str]:
    # Types form a flat set of alternatives, independent of the text expression.
    raw = types or ""
    if "(" in raw or ")" in raw:
        raise QueryError("brackets are not valid in `types`; it is a flat list, e.g. FAIL|FACT")
    parts = []
    cur: List[str] = []
    for ch in raw:
        if ch in "|&,":
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))

    out: List[str] = []
    seen = set()
    for p in parts:
        t = p.strip().upper()
        if not t:
            continue
        if t not in valid:
            raise QueryError(
                f"unknown type {t!r}; valid types are {', '.join(sorted(valid))}"
            )
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out
