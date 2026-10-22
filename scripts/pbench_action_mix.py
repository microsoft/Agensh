#!/usr/bin/env python3
# Estimate tool-action categories from archived Copilot assistant tool requests.
# Shell classification is heuristic: separate executable commands from file-writing
# heredocs so generated source is not mistaken for a build or reference probe.

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

_VERB_END = r"(?=[\s<>;&|)]|$)"
BASH_RULES: list[tuple[str, re.Pattern]] = [
    ("vcs/git",      re.compile(r"^git\s+(?!.*\bgrep\b)")),
    ("build",        re.compile(r"^(make|cmake|gcc|g\+\+|cc|c\+\+|clang|clang\+\+|\./compile\S*|"
                                r"(ba)?sh\s+(-\S+\s+)*(\./)?compile\.sh|"
                                r"meson|ninja|cargo build|go build|cabal build|stack build)" + _VERB_END)),
    ("test",         re.compile(r"^(pytest|bats|ctest|run_tests\S*|"
                                r"cargo test|go test|cabal test|stack test|"
                                r"python\d*(\.\d+)?\s+-m\s+(pytest|unittest)|"
                                r"((ba)?sh\s+(-\S+\s+)*)?\S*(tests?/run\.sh|\./run\.sh|"
                                r"\btests?\b\S*\.sh))" + _VERB_END)),
    ("run artifact", re.compile(r"\./executable\b|\bexecutable\s+--")),
    ("read code",    re.compile(r"^(cat|head|tail|less|sed -n|nl|wc|grep|rg|"
                                r"find|ls|tree|diff|file|stat|awk)\b")),
]

SEGMENT_SPLIT = re.compile(r"&&|\|\||\$\(|[;|&\n(){}`]")
PREFIX = re.compile(r"^((\w+=\S*|sudo|time|nohup|exec|command|env|nice|if|then|elif|"
                    r"else|do|while|until|!|timeout(\s+-\S+)*\s+\S+)\s+)*")


def segments(text: str) -> list[str]:
    segs = (PREFIX.sub("", s.strip()) for s in SEGMENT_SPLIT.split(text))
    return [s for s in segs if s]


HEREDOC = re.compile(r"(?<!<)<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")
INTERPRETER = re.compile(r"((ba|da|z)?sh|python\d*(\.\d+)?|node|perl|ruby|runghc|runhaskell)")


def command_text(cmd: str) -> str:
    # Keep interpreter-fed heredocs, but omit literal file contents from classification.
    out: list[str] = []
    pending: list[tuple[str, bool]] = []
    for line in cmd.split("\n"):
        if pending:
            delim, keep = pending[0]
            if line.strip() == delim:
                pending.pop(0)
            elif keep:
                out.append(line)
            continue
        out.append(line)
        for m in HEREDOC.finditer(line):
            before = segments(line[: m.start()])
            verb = os.path.basename(before[-1].split()[0]) if before else ""
            pending.append((m.group(2), bool(INTERPRETER.fullmatch(verb))))
    return "\n".join(out)

WRITE_OP = re.compile(r"(>>?\s*(?P<redir>\S+))|(\b(?P<verb>tee|cp|mv)\b(?P<rest>[^|;&]*))"
                      r"|(<<\s*'?[A-Za-z_]*EOF)")
PROBE_PATH = re.compile(r"(/tmp/|/var/tmp/|\$\{?d\}?\b|\$TMPDIR|\$\{?TMP\w*\}?|"
                        r"mktemp|/dev/(null|stdout|stderr)|\.tmp\b)")


def write_target(cmd: str) -> str | None:
    m = WRITE_OP.search(cmd)
    if not m:
        return None
    if m.group("redir"):
        return m.group("redir")
    if m.group("verb"):
        args = [a for a in (m.group("rest") or "").split() if not a.startswith("-")]
        return args[-1] if args else ""
    r = re.search(r">>?\s*(\S+)", cmd[: m.start()])
    return r.group(1) if r else ""

COORD_NS = ("gitea", "mattermost", "board")
COORD_WRITE = ("write", "post_message", "create", "merge", "add_comment",
               "finalize", "unfold", "close", "update", "delete", "edit")

TOOL_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("planning",      ("todowrite", "toolsearch", "exitplanmode")),
    ("write code",    ("edit", "write_file", "apply_patch", "create_file",
                       "multiedit", "str_replace", "notebookedit")),
    ("read code",     ("read", "view", "grep", "glob", "rg", "search", "ls")),
]


def classify(name: str, args: dict) -> str:
    # Match specific shell activities before broad file/tool-name categories.
    n = (name or "").lower()
    base = n.split("__")[-1] if "__" in n else n

    if base in ("bash", "shell", "run_command", "execute"):
        cmd = ""
        for k in ("command", "cmd", "script", "input"):
            v = args.get(k)
            if isinstance(v, str):
                cmd = v
                break
        segs = segments(command_text(cmd))
        for label, pat in BASH_RULES[:4]:
            if any(pat.search(s) for s in segs):
                return label
        tgt = write_target(cmd)
        if tgt is not None:
            return "probe/scaffold" if PROBE_PATH.search(tgt or cmd) else "write code"
        first = next((s for s in segs if not re.match(r"cd\b", s)), "")
        for label, pat in BASH_RULES[4:]:
            if pat.search(first):
                return label
        return "shell: other"

    head = re.split(r"[-_]+", n)[0]
    if head in COORD_NS or any(f"__{s}__" in n or n.startswith(f"{s}-")
                               for s in COORD_NS):
        return ("coord: write" if any(v in n for v in COORD_WRITE)
                else "coord: read")

    for label, keys in TOOL_RULES:
        if any(k in n for k in keys):
            return label
    if base == "write":
        return "write code"
    return "other"


def walk_copilot(root: Path):
    for f in root.rglob("events.jsonl"):
        try:
            text = f.read_text(errors="replace")
        except (PermissionError, OSError):
            continue
        for line in text.splitlines():
            try:
                o = json.loads(line)
            except Exception:
                continue
            if not isinstance(o, dict) or o.get("type") != "assistant.message":
                continue
            for t in (o.get("data") or {}).get("toolRequests") or []:
                if isinstance(t, dict):
                    yield t.get("name", "?"), (t.get("arguments") or {})


def column_labels(names: list[str]) -> list[str]:
    def cut(s: str, w: int) -> str:
        if len(s) <= w:
            return s
        head = (w - 1) // 2
        return s[:head] + "…" + s[len(s) - (w - 1 - head):]
    width = 26
    labels = [cut(Path(n).name, width) for n in names]
    if len(set(labels)) < len(labels):
        labels = [f"{i}:" + cut(Path(n).name, width - len(f"{i}:"))
                  for i, n in enumerate(names, 1)]
    return labels


ORDER = ["write code", "probe/scaffold", "build", "test", "run artifact", "read code",
         "vcs/git", "coord: read", "coord: write", "planning",
         "shell: other", "other"]


def main(argv: list[str]) -> int:
    cols: dict[str, Counter] = {}
    for d in argv[1:]:
        root = Path(d) / "data-root"
        if not root.is_dir():
            root = Path(d)
        c: Counter = Counter()
        for name, args in walk_copilot(root):
            c[classify(name, args)] += 1
        cols[str(Path(d))] = c
        if not sum(c.values()):
            print(f"WARNING: {d} yielded 0 tool calls — root-owned transcripts? "
                  "rerun with sudo", file=sys.stderr)

    names = list(cols)
    w = max(len(x) for x in ORDER) + 2
    print("\n" + "category".ljust(w) + "".join(f"{lab:>28}" for lab in column_labels(names)))
    print("-" * (w + 28 * len(names)))
    for cat in ORDER:
        if not any(cols[n][cat] for n in names):
            continue
        line = cat.ljust(w)
        for n in names:
            tot = sum(cols[n].values()) or 1
            line += f"{cols[n][cat]:>17,} {100 * cols[n][cat] / tot:>8.1f}%"
        print(line)
    print("-" * (w + 28 * len(names)))
    line = "TOTAL".ljust(w)
    for n in names:
        line += f"{sum(cols[n].values()):>17,} {100.0:>8.1f}%"
    print(line)

    print()
    for n in names:
        c = cols[n]
        tot = sum(c.values()) or 1
        prod = c["write code"] + c["build"] + c["test"] + c["run artifact"]
        coord = c["coord: read"] + c["coord: write"]
        print(f"{n}: productive {100*prod/tot:.1f}%  coordination {100*coord/tot:.1f}%  "
              f"code-writing {100*c['write code']/tot:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
