#!/usr/bin/env python3
"""pbench_action_mix.py — classify Copilot tool calls by the work they perform.

Reads **/events.jsonl, including assistant.message.data.toolRequests.
Shell calls are classified by their commands rather than grouped together.

Usage:
  sudo python3 scripts/pbench_action_mix.py <task-dir> [<task-dir> ...]
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

# Order matters: first match wins, so the specific patterns precede the general
# ones. Matched per simple command (see segments()), and anchored on the verb at
# its head: an unanchored `\bmake\b` also fires on "make" in a heredoc body, a
# path or a commit message.
#
# NOTE: writes are NOT handled here — see write_target() below. A write has to be
# resolved by its TARGET, which a flat rule list cannot express, and two bugs
# came from trying: `printf ... > /tmp/probe.c` (a throwaway file written to
# observe the reference) counted as delivered code, and `cat > src/parsers/c.c
# <<EOF` counted as *reading* because `cat` matched the read rule first.
_VERB_END = r"(?=[\s<>;&|)]|$)"   # `\b` never matches after `g++`
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
    # Unanchored on purpose: a harness script that drives the artifact names it
    # as an argument (`subprocess.run(['./executable', ...])`), not as a verb.
    ("run artifact", re.compile(r"\./executable\b|\bexecutable\s+--")),
    ("read code",    re.compile(r"^(cat|head|tail|less|sed -n|nl|wc|grep|rg|"
                                r"find|ls|tree|diff|file|stat|awk)\b")),
]

# A verb can stand at a line start or after an operator or an opening group, so
# `cd build && make`, `x | ./executable` and `(ulimit -v N; ./executable)` are
# all read by their verbs.
SEGMENT_SPLIT = re.compile(r"&&|\|\||\$\(|[;|&\n(){}`]")
# Words in front of the verb that are not it.
PREFIX = re.compile(r"^((\w+=\S*|sudo|time|nohup|exec|command|env|nice|if|then|elif|"
                    r"else|do|while|until|!|timeout(\s+-\S+)*\s+\S+)\s+)*")


def segments(text: str) -> list[str]:
    """The simple commands in `text`, each starting at its verb."""
    segs = (PREFIX.sub("", s.strip()) for s in SEGMENT_SPLIT.split(text))
    return [s for s in segs if s]


HEREDOC = re.compile(r"(?<!<)<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")
# A heredoc fed to an interpreter is code the command runs. One fed to cat, tee
# or git is data -- file contents, a commit message -- and its words are not
# commands.
INTERPRETER = re.compile(r"((ba|da|z)?sh|python\d*(\.\d+)?|node|perl|ruby|runghc|runhaskell)")


def command_text(cmd: str) -> str:
    """`cmd` without the bodies of its data heredocs."""
    out: list[str] = []
    pending: list[tuple[str, bool]] = []   # (delimiter, keep the body)
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

# A write is resolved by its TARGET, not by the presence of `>`.
WRITE_OP = re.compile(r"(>>?\s*(?P<redir>\S+))|(\b(?P<verb>tee|cp|mv)\b(?P<rest>[^|;&]*))"
                      r"|(<<\s*'?[A-Za-z_]*EOF)")
# Throwaway scratch space. Both arms write sample inputs here to observe the
# reference binary; that is observation, not delivery, and counting it as code
# inflated both arms unequally.
PROBE_PATH = re.compile(r"(/tmp/|/var/tmp/|\$\{?d\}?\b|\$TMPDIR|\$\{?TMP\w*\}?|"
                        r"mktemp|/dev/(null|stdout|stderr)|\.tmp\b)")


def write_target(cmd: str) -> str | None:
    """Return the path a command writes to, or None if it writes nothing.

    Handles `> path`, `>> path`, `tee path`, `cp/mv src dst` (dst is the LAST
    argument) and heredocs. Returns "" when a write is detected but no target
    could be extracted, so the caller can still count it as a write.
    """
    m = WRITE_OP.search(cmd)
    if not m:
        return None
    if m.group("redir"):
        return m.group("redir")
    if m.group("verb"):
        args = [a for a in (m.group("rest") or "").split() if not a.startswith("-")]
        return args[-1] if args else ""
    # A heredoc: the destination, if any, is on the same line before the `<<`.
    r = re.search(r">>?\s*(\S+)", cmd[: m.start()])
    return r.group(1) if r else ""

# Coordination is best identified by NAMESPACE, not by verb. Every tool served
# by the gitea / mattermost / board MCP servers is coordination infrastructure
# by construction, and enumerating verbs kept leaking: gitea-get_me (833 calls),
# list_my_repos (615), notification_read (231) and board-queue_status all fell
# into "other" and undercounted the copilot arm's coordination share. Both arms
# name these the same way modulo separator (mcp__gitea__x vs gitea-x).
COORD_NS = ("gitea", "mattermost", "board")
# Within a coordination namespace, these verbs mutate; everything else observes.
COORD_WRITE = ("write", "post_message", "create", "merge", "add_comment",
               "finalize", "unfold", "close", "update", "delete", "edit")

# Native (non-MCP) tools: local work on the actual program.
TOOL_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("planning",      ("todowrite", "toolsearch", "exitplanmode")),
    ("write code",    ("edit", "write_file", "apply_patch", "create_file",
                       "multiedit", "str_replace", "notebookedit")),
    ("read code",     ("read", "view", "grep", "glob", "rg", "search", "ls")),
]


def classify(name: str, args: dict) -> str:
    n = (name or "").lower()
    base = n.split("__")[-1] if "__" in n else n

    if base in ("bash", "shell", "run_command", "execute"):
        cmd = ""
        for k in ("command", "cmd", "script", "input"):
            v = args.get(k)
            if isinstance(v, str):
                cmd = v
                break
        # The command's PRIMARY action wins. Resolving writes first made every
        # redirect a write (`make -j8 > build.log`), collapsing build 1,386->97
        # and test 889->72. These four rules are the primary action; the read
        # rule is deliberately LAST, after writes, because a heredoc into a
        # source file starts with `cat`.
        segs = segments(command_text(cmd))
        for label, pat in BASH_RULES[:4]:
            if any(pat.search(s) for s in segs):
                return label
        tgt = write_target(cmd)
        if tgt is not None:
            return "probe/scaffold" if PROBE_PATH.search(tgt or cmd) else "write code"
        # A read is the command's first verb past any `cd`, not any verb in it.
        first = next((s for s in segs if not re.match(r"cd\b", s)), "")
        for label, pat in BASH_RULES[4:]:
            if pat.search(first):
                return label
        return "shell: other"

    # Namespace first. `mcp__gitea__issue_read` and `gitea-issue_read` both
    # start their server name at the head of a separator-split.
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
    """Header labels: unique, at most `width` characters.

    Neither end of a trajectory name tells columns apart on its own (see
    main()), so keep both ends and cut the middle; number the labels if that
    still collides.
    """
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
        # Key on the WHOLE path. Any fixed slice of the name collides: a task's
        # trajectories share their head, a run's (`<task>.single-node.<RUN_ID>`)
        # share their tail, and a collision silently overwrites one column with
        # another, reporting a single column that looks like a complete answer.
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

    # The three summary ratios worth reading off directly.
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
