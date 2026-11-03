#!/usr/bin/env python3
# Drive the selected standalone harness through the container's stdio/socket adapter.
# Resume completed turns while more than 60 seconds remain; a pending prompt is
# bounded by the deadline. Reload sessions after transport/watchdog failures.

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

PROTOCOL_VERSION = 1
ACP_CHILD_CMD = ["python3", "/opt/single_agent_stdio.py"]


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    sys.stderr.write(f"[acp-driver {ts}] {msg}\n")
    sys.stderr.flush()


class ACPChild:
    # A reader thread multiplexes JSON-RPC replies, notifications and permission requests.
    def __init__(self, cmd: list[str], stderr_path: Optional[str] = None) -> None:
        self._cmd = cmd
        self._stderr_path = stderr_path
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._next_id = 0
        self._pending: dict[int, dict[str, Any]] = {}
        self._cond = threading.Condition()
        self._reader: Optional[threading.Thread] = None
        self._stopped = False
        self.on_notification = lambda method, params: None
        self.on_request = lambda method, params: {
            "error": {"code": -32601, "message": "method not found"}
        }

    def start(self) -> None:
        stderr_dst = open(self._stderr_path, "ab") if self._stderr_path else subprocess.DEVNULL
        log(f"spawning ACP child: {' '.join(self._cmd)}")
        try:
            self._proc = subprocess.Popen(
                self._cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr_dst,
            )
        finally:
            if self._stderr_path:
                stderr_dst.close()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def close(self) -> None:
        self._stopped = True
        if self._proc:
            try:
                if self._proc.stdin and not self._proc.stdin.closed:
                    self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                    self._proc.wait(timeout=5)
                except Exception:
                    pass
            if self._reader is not None and self._reader is not threading.current_thread():
                self._reader.join(timeout=5)
            if self._proc.stdout:
                self._proc.stdout.close()

    def _read_loop(self) -> None:
        assert self._proc is not None
        assert self._proc.stdout is not None
        buf = b""
        while not self._stopped:
            try:
                chunk = self._proc.stdout.read1(65536)
            except Exception as e:
                log(f"read error: {e}")
                break
            if not chunk:
                break
            buf += chunk
            while True:
                nl = buf.find(b"\n")
                if nl < 0:
                    break
                line = buf[:nl].strip()
                buf = buf[nl + 1 :]
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8", errors="replace"))
                except json.JSONDecodeError as e:
                    log(f"non-JSON line skipped ({e}): {line[:200]!r}")
                    continue
                self._dispatch(msg)
        log("reader thread exit (child closed stdout)")
        # Release blocked request callers when the transport disappears.
        with self._cond:
            for fut in self._pending.values():
                fut["error"] = {"code": -32000, "message": "child closed stdout"}
                fut["done"] = True
            self._pending.clear()
            self._cond.notify_all()

    def _dispatch(self, msg: dict[str, Any]) -> None:
        if "id" in msg and ("result" in msg or "error" in msg):
            mid = msg["id"]
            with self._cond:
                fut = self._pending.pop(mid, None)
                if fut is not None:
                    fut["result"] = msg.get("result")
                    fut["error"] = msg.get("error")
                    fut["done"] = True
                    self._cond.notify_all()
            return
        if "id" in msg and "method" in msg:
            method = msg["method"]
            params = msg.get("params") or {}
            try:
                reply = self.on_request(method, params)
            except Exception as e:
                reply = {"error": {"code": -32000, "message": f"handler crashed: {e}"}}
            resp: dict[str, Any] = {"jsonrpc": "2.0", "id": msg["id"]}
            if (
                reply is None
                or not isinstance(reply, dict)
                or ("result" not in reply and "error" not in reply)
            ):
                resp["error"] = {"code": -32603, "message": "internal: bad handler reply"}
            else:
                resp.update({k: v for k, v in reply.items() if k in ("result", "error")})
            self._send_raw(resp)
            return
        if "method" in msg:
            try:
                self.on_notification(msg["method"], msg.get("params") or {})
            except Exception as e:
                log(f"notification handler crashed: {e}")
            return
        log(f"unknown message shape: {msg}")

    def _send_raw(self, obj: dict[str, Any]) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            self._proc.stdin.write(data)
            self._proc.stdin.flush()
        except (BrokenPipeError, ValueError) as e:
            raise RuntimeError(f"write to child failed: {e}") from e

    def request(
        self, method: str, params: dict[str, Any], timeout: Optional[float] = None
    ) -> dict[str, Any]:
        with self._cond:
            self._next_id += 1
            mid = self._next_id
            fut = {"done": False, "result": None, "error": None}
            self._pending[mid] = fut
        self._send_raw({"jsonrpc": "2.0", "id": mid, "method": method, "params": params})
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._cond:
            while not fut["done"]:
                remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
                if remaining is not None and remaining <= 0:
                    self._pending.pop(mid, None)
                    raise TimeoutError(f"acp {method} timed out after {timeout}s")
                self._cond.wait(timeout=remaining)
        if fut["error"] is not None:
            raise RuntimeError(f"acp {method} error: {fut['error']}")
        return fut["result"] or {}


class Session:
    def __init__(self) -> None:
        self.session_id: Optional[str] = None
        self.last_update_at = time.monotonic()
        self.update_count = 0

    def on_notification(self, method: str, params: dict[str, Any]) -> None:
        self.last_update_at = time.monotonic()
        if method == "session/update":
            self.update_count += 1

    def on_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.last_update_at = time.monotonic()
        if method == "session/request_permission":
            options = params.get("options") or []
            picked = ""
            for o in options:
                if o.get("kind") == "allow_once":
                    picked = o.get("optionId", "")
                    break
            if not picked and options:
                picked = options[0].get("optionId", "")
            return {"result": {"outcome": {"outcome": "selected", "optionId": picked}}}
        return {"error": {"code": -32601, "message": f"method not implemented: {method}"}}


def cat_in_container(container: str, docker_bin: list[str], path: str) -> str:
    cmd = docker_bin + ["exec", container, "cat", path]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(
            f"cat {path} in container failed: {p.stderr.decode(errors='replace')}"
        )
    return p.stdout.decode("utf-8", errors="replace")


def check_prompt_files(container: str, docker_bin: list[str], paths: list[str]) -> None:
    script = " && ".join(f"test -f {shlex.quote(p)}" for p in paths)
    cmd = docker_bin + ["exec", container, "sh", "-lc", script]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise SystemExit(
            "[acp-driver] FATAL: prompt files missing inside container: "
            f"rc={p.returncode} stderr={p.stderr.decode(errors='replace')}"
        )


def build_initial_prompt(brief_txt: str, rules_txt: str) -> str:
    return (
        "IMPORTANT — these are hard rules for the entire session (they would "
        "be the --append-system-prompt in the CLI baseline; you must follow "
        "them on every turn, not just the first):\n\n"
        f"{rules_txt}\n\n"
        "---\n\n"
        f"{brief_txt}"
    )


DEADLINE_NOTICE_SECS = 15 * 60


def _resume_text(resume_txt: str, silent_s: int, stuck_secs: int) -> str:
    if silent_s <= 0:
        return resume_txt
    return (
        f"[system] Previous turn was force-cancelled after ~{silent_s}s of no "
        f"ACP output (driver watchdog, stuck_secs={stuck_secs}). Session was "
        f"reloaded from disk; workspace files at /workspace and "
        f"/opt/pbench/executable are unchanged. If you were running a long "
        f"tool call, launch it in the background next time (& or nohup) so "
        f"events keep flowing.\n\n---\n\n"
        f"{resume_txt}"
    )


def _deadline_text(text: str, remaining: float) -> str:
    if remaining > DEADLINE_NOTICE_SECS:
        return text
    return (
        "[system] About 15 minutes left in this run. You will be stopped "
        "without warning and only committed work is graded. Stop starting new "
        "work now: make sure root `compile.sh` builds `./executable` from a "
        "clean checkout, then commit everything. Anything uncommitted at the "
        "cutoff is lost.\n\n---\n\n"
        f"{text}"
    )


def run(args: argparse.Namespace) -> int:
    docker_bin = shlex.split(args.docker)

    check_prompt_files(args.container, docker_bin, [args.brief, args.rules, args.resume])

    brief_txt = cat_in_container(args.container, docker_bin, args.brief)
    rules_txt = cat_in_container(args.container, docker_bin, args.rules)
    resume_txt = cat_in_container(args.container, docker_bin, args.resume)
    initial_prompt = build_initial_prompt(brief_txt, rules_txt)

    child_cmd = docker_bin + ["exec", "-i", args.container] + ACP_CHILD_CMD
    session = Session()

    child_ref: dict[str, Optional[ACPChild]] = {"child": None}
    spawn_seq = {"n": 0}

    def spawn_and_init(load_sid: Optional[str]) -> tuple[ACPChild, bool]:
        # Return whether a new session needs the complete initial rules and brief.
        spawn_seq["n"] += 1
        n = spawn_seq["n"]
        log(f"--- spawn #{n} (load_sid={load_sid[:8] + '...' if load_sid else 'None'}) ---")
        c = ACPChild(child_cmd, stderr_path=args.child_stderr)
        c.on_notification = session.on_notification
        c.on_request = session.on_request
        c.start()
        c.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}},
            },
            timeout=60,
        )
        if load_sid:
            try:
                c.request(
                    "session/load",
                    {"sessionId": load_sid, "cwd": args.workspace_cwd, "mcpServers": []},
                    timeout=180,
                )
                log(f"session/load ok, reused sid={load_sid[:8]}")
                session.last_update_at = time.monotonic()
                return c, False
            except Exception as e:
                log(f"session/load failed ({e}); falling back to session/new")
        ns = c.request(
            "session/new",
            {"cwd": args.workspace_cwd, "mcpServers": []},
            timeout=120,
        )
        new_sid = ns.get("sessionId")
        if not new_sid:
            raise RuntimeError(f"session/new returned no sessionId: {ns}")
        session.session_id = new_sid
        if args.session_state:
            Path(args.session_state).write_text(new_sid)
        log(f"session/new sid={new_sid[:8]}")
        session.last_update_at = time.monotonic()
        return c, True

    watchdog_stop = threading.Event()

    def watchdog_loop() -> None:
        # Only pending requests count as stalled; an idle client is not a stuck turn.
        tick = max(30.0, args.stuck_secs / 4.0)
        while not watchdog_stop.is_set():
            if watchdog_stop.wait(tick):
                return
            if args.stuck_secs <= 0:
                continue
            c = child_ref["child"]
            if c is None or c._stopped:
                continue
            with c._cond:
                has_pending = bool(c._pending)
            if not has_pending:
                continue
            silent = time.monotonic() - session.last_update_at
            if silent >= args.stuck_secs:
                log(
                    f"watchdog: silence {silent:.0f}s >= stuck_secs "
                    f"{args.stuck_secs}s; closing child"
                )
                try:
                    c.close()
                except Exception as e:
                    log(f"watchdog close raised: {e}")

    wd_thread: Optional[threading.Thread] = None
    if args.stuck_secs > 0:
        wd_thread = threading.Thread(target=watchdog_loop, daemon=True)
        wd_thread.start()

    try:
        child_ref["child"], send_initial = spawn_and_init(load_sid=None)
        deadline = time.monotonic() + args.deadline_secs
        iter_no = 0
        last_silent_s = 0
        stuck_restarts = 0
        deadline_warned = False
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 60:
                log(f"budget exhausted (remaining={remaining:.0f}s); stopping resume loop")
                break
            iter_no += 1
            if send_initial:
                mode = "initial" if iter_no == 1 else "initial-new-session"
                text = initial_prompt
                send_initial = False
            elif last_silent_s > 0:
                mode = "resume-after-stuck"
                text = _resume_text(resume_txt, last_silent_s, args.stuck_secs)
            else:
                # The loop permits another prompt only with more than 60 seconds left.
                mode = "resume"
                text = resume_txt
            if not deadline_warned and remaining <= DEADLINE_NOTICE_SECS:
                text = _deadline_text(text, remaining)
                deadline_warned = True
                mode += "+deadline"
                log(f"deadline notice attached (remaining={remaining:.0f}s)")
            log(
                f"iter={iter_no} mode={mode} remaining={remaining:.0f}s "
                f"update_count={session.update_count} restarts={stuck_restarts}"
            )
            iter_start = time.monotonic()
            session.last_update_at = iter_start
            try:
                res = child_ref["child"].request(
                    "session/prompt",
                    {
                        "sessionId": session.session_id,
                        "prompt": [{"type": "text", "text": text}],
                    },
                    timeout=remaining,
                )
            except TimeoutError:
                log(f"iter={iter_no} wall-clock timeout at session/prompt — done")
                break
            except RuntimeError as e:
                silent_s = int(time.monotonic() - session.last_update_at)
                log(
                    f"iter={iter_no} child closed (silent={silent_s}s): {e}; "
                    f"respawning"
                )
                stuck_restarts += 1
                last_silent_s = max(silent_s, 1)
                child_ref["child"].close()
                try:
                    child_ref["child"], send_initial = spawn_and_init(load_sid=session.session_id)
                except Exception as e2:
                    log(f"respawn failed: {e2}; aborting resume loop")
                    break
                continue
            last_silent_s = 0
            stop = res.get("stopReason") or "?"
            elapsed = time.monotonic() - iter_start
            log(
                f"iter={iter_no} stopReason={stop} elapsed={elapsed:.0f}s "
                f"update_count={session.update_count} restarts={stuck_restarts}"
            )

        return 0
    finally:
        watchdog_stop.set()
        c = child_ref["child"]
        if c is not None:
            c.close()


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description='\nacp_driver.py — minimal Python ACP client for the single-agent ProgramBench\nbaseline, using the selected Pi, Copilot or Codex runtime.\n\nDrives one native harness session through the release ACP bridge over\n    docker exec -i <container> python3 /opt/single_agent_stdio.py\nspeaking JSON-RPC 2.0 (NDJSON framing) on stdio.\n\nProtocol shape (verified against mini-router/src/acp_socket_channel.ts):\n\n    → initialize {protocolVersion: 1, clientCapabilities.fs.{read,write}TextFile: false}\n    ← result {protocolVersion: 1, ...}\n    → session/new {cwd, mcpServers: []}\n    ← result {sessionId}\n    → session/prompt {sessionId, prompt: [{type:"text", text}]}\n    ← notifications session/update ...\n    ← request  session/request_permission   → we reply "allow_once"\n    ← result   {stopReason: "end_turn" | ...}\n\nAn explicit resume loop on the same sessionId, starting another prompt only\nwhile more than 60 seconds remain. First prompt = rules + brief;\nsubsequent prompts = the resume kicker text.\n\nStdlib only.\n')
    ap.add_argument("--container", required=True,
                    help="cc-agent container name (from `compose ps -q`)")
    ap.add_argument("--workspace-cwd", default="/workspace")
    ap.add_argument("--deadline-secs", type=int, required=True,
                    help="wall-clock budget for the ACP session")
    ap.add_argument("--brief", required=True,
                    help="in-container path to brief.txt")
    ap.add_argument("--rules", required=True,
                    help="in-container path to rules.txt")
    ap.add_argument("--resume", required=True,
                    help="in-container path to resume.txt")
    ap.add_argument("--docker",
                    default=os.environ.get("PBENCH_DOCKER", "sudo -E docker"),
                    help="docker command (whitespace-split, e.g. 'sudo -E docker')")
    ap.add_argument("--session-state", default=None,
                    help="optional file to persist sessionId (host side)")
    ap.add_argument("--child-stderr", default=None,
                    help="optional file to capture ACP child stderr")
    ap.add_argument("--stuck-secs", type=int, default=600,
                    help="silence-watchdog threshold in seconds; if no ACP RX "
                         "for this long while a request is pending, close the "
                         "child and respawn (0 disables). Default 600.")
    return ap.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))
