"""gquery — boolean search-expression parser for board_grep.

Grammar (precedence: parentheses > & > |):

    expr    := and_expr ('|' and_expr)*
    and_expr:= factor  ('&' factor)*
    factor  := '(' expr ')' | WORD
    WORD    := any run of characters except '|', '&', '(', ')', trimmed

So `(a|b)&c` is "(a OR b) AND c", and `a&b|c&d` is "(a AND b) OR (c AND d)"
because & binds tighter than |.

WHY A PARSER AND NOT A SPLIT
A flat DNF split -- ',' between OR groups, '&' within a group -- is
expressively complete (any boolean expression has a DNF form), but an agent
that types brackets gets no error: '(' and ')' are not special to LIKE and are
not escaped by _lit(), so `(parser|lexer)` would be searched as that LITERAL
string and return a confident, wrong answer (`(parser,lexer)&crash` splits into
groups [["(parser"], ["lexer)","crash"]]). Silent wrong answers are worse than
a rejected query, so every malformed expression raises QueryError with a reason.

',' is NOT an operator here. Search terms legitimately contain commas (a
PATCH_SUMMARY reads `files=a.c,b.c`), so a comma is an ordinary character
inside a WORD.
"""
from __future__ import annotations

from typing import Any, Callable, List, Tuple

__all__ = ["QueryError", "parse", "count_terms", "compile_sql", "parse_type_list"]

_SPECIAL = "|&()"


class QueryError(ValueError):
    """Raised for any expression that cannot be parsed. Message is agent-facing."""


# --- tokenizer --------------------------------------------------------------
def _tokenize(s: str) -> List[Tuple[str, str]]:
    """-> [(kind, value)] where kind is one of: WORD ( ) & |

    Only the four operator characters split a word, so a multi-word phrase
    needs no quoting: `machine learning` is already a single term.
    """
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


# --- recursive-descent parser ----------------------------------------------
# Node shapes: ("term", str) | ("and", [node, ...]) | ("or", [node, ...])
def parse(expr: str) -> Any:
    toks = _tokenize(expr)
    if not toks:
        raise QueryError("empty expression")
    pos = 0
    depth = 0   # bracket nesting, so a ')' fault can be described accurately

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
            # Inside a group the '(' is matched, so the real fault is a missing
            # operand -- saying "no matching '('" would send the agent looking
            # for the wrong thing.
            if depth > 0:
                raise QueryError("expected a term before ')'")
            raise QueryError("unexpected ')' — no matching '('")
        if k in ("&", "|"):
            raise QueryError(f"'{k}' needs a term on both sides")
        raise QueryError("expected a search term")

    node = parse_or()
    if pos != len(toks):
        # A complete expression followed by more tokens. Name what was found:
        # a stray ')' and a missing operator are different mistakes, and
        # reporting the wrong one sends the agent looking in the wrong place.
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


def compile_sql(node: Any, lit: Callable[[str], str],
                col: str = "content") -> Tuple[str, List[Any]]:
    """-> (sql_fragment, params). `lit` wraps a term as a LIKE pattern."""
    if node[0] == "term":
        return f"{col} LIKE %s ESCAPE '\\\\'", [lit(node[1])]
    joiner = " AND " if node[0] == "and" else " OR "
    frags: List[str] = []
    params: List[Any] = []
    for child in node[1]:
        f, p = compile_sql(child, lit, col)
        frags.append(f)
        params.extend(p)
    return "(" + joiner.join(frags) + ")", params


def parse_type_list(types: str, valid: Any) -> List[str]:
    """Parse the `types` filter into a validated, de-duplicated list.

    A note has exactly ONE type, so an AND across types is unsatisfiable and
    every separator can only mean OR. '|' is the documented one; '&' and ','
    are accepted because an agent carrying either habit over from `words` means
    the same thing unambiguously. Brackets are not meaningful in a flat list
    and are rejected rather than silently searched for.
    """
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
