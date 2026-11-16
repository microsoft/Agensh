"""Count14 scientific-runtime ports for the pinned native racing game.

No new HTTP/model client, retry loop, financial ledger, privileged reference,
official evaluator or scientific dispatcher. A cold owner must supply the
ORIGINAL charged ACP turn port and its pause-aware clock. This is a component;
its OWN qualification does not qualify an experiment launcher.
"""
from __future__ import annotations

from dataclasses import dataclass
import concurrent.futures as cf
import math
import threading
from types import FunctionType, MethodType, SimpleNamespace
import time

from nloop.game import Game, PhaseClock
from nloop.judge import NullJudge
from nloop.ledger import Stopped
from nloop.llm import CallDeadline
from nloop.parse import parse_phase, ParseError, CONTINUATION_SCHEMAS
from nloop.players import ThinkerPlayer
from nloop.prompts import Prompts
from count14_public_racing_judge import Count14PublicRacingJudge

COUNT14_RACING_CHARTER = (
    "Count14 test-development racing. Use only the same public task workspace and tools as the development team. "
    "Propose diverse, concrete regression or reproduction cases for distinct failure mechanisms, not just alternate "
    "wordings or input sizes. Cases are UNVERIFIED proposals; do not claim a private-reference or official verdict. "
    "No private evaluator, grading data, reference executable, hidden tests or official-test feedback is available. "
    "PROG denotes only the team's public task execution wrapper, never an evaluator or reference oracle. "
    "Retain the specified FINAL_OUTPUT schema.\n\n"
)


@dataclass(frozen=True)
class CompletedNativeTurn:
    # This field is consumed ONLY inside the scientific runtime, never emitted
    # to PUBLIC diagnostics. Tests use synthetic OWN text only.
    text: str
    original_relay_receipts_complete: bool
    physical_terminal: bool
    thinking: str = ""
    stop_reason: str = "UNAVAILABLE"  # Fixed control enum, never model text.
    native_session_uuid: str | None = None  # Private original identity, never PUBLIC.
    native_turn_id: str | None = None


class NativePhaseUnadmitted(RuntimeError):
    """Known original physical-custody hold, zero native/model admission."""


class NativeRacingLLM:
    """Use native CLI turns, hence the original Responses/GLM/header/budget.

    No upstream Anthropic HTTP retries, monetary estimates or cancellation.
    The 75%-quorum closes semantic admission only: already accepted native
    turns continue to their physical terminal and remain fully charged.
    """
    def __init__(self, *, turn, admission_open, retain_fault, continuation_template=None):
        if not all(callable(x) for x in (turn, admission_open, retain_fault)):
            raise ValueError("DYNTEAM_RACING_EXACT_ORIGINAL_NATIVE_PORTS")
        self.turn, self.admission_open, self.retain_fault = turn, admission_open, retain_fault
        self.continuation_template = None
        self.last_background_stop_reason = "UNAVAILABLE"
        self.first_background_native_turn = None
        if continuation_template is not None:
            self.bind_continuation_template(continuation_template)

    def bind_continuation_template(self, template):
        if not (type(template) is str and "{PARTIAL}" in template and "{SCHEMA}" in template and
                (self.continuation_template is None or self.continuation_template == template)):
            raise ValueError("DYNTEAM_RACING_PINNED_NATIVE_CONTINUATION_TEMPLATE")
        self.continuation_template = template

    def background(self, user_content):
        if not self.admission_open():
            raise CallDeadline([])
        result = self._completed("racing-background-00", user_content, "background")
        self.last_background_stop_reason = result.stop_reason
        if self.first_background_native_turn is None:
            self.first_background_native_turn = result
        return result.text

    def require_first_background_setup_anchor(self):
        result = self.first_background_native_turn
        if not (type(result) is CompletedNativeTurn and result.stop_reason == "end_turn" and
                result.original_relay_receipts_complete is True and result.physical_terminal is True and
                type(result.native_session_uuid) is str and result.native_session_uuid and
                type(result.native_turn_id) is str and 0 < len(result.native_turn_id) <= 256):
            raise ValueError("RACING_SETUP_COMPLETION_REQUIRES_ORIGINAL_NORMAL_PHYSICAL_SID_TURN")
        return result

    def complete_first_background_setup(self, instruction):
        original = self.require_first_background_setup_anchor()
        if not self.admission_open():
            raise CallDeadline([])  # Consumed once; never retry the intent.
        result = self._completed("racing-background-00",
            [{"type":"text","text":instruction}], "setup-completion")
        if (result.native_session_uuid, result.native_turn_id) != (original.native_session_uuid, original.native_turn_id):
            self.retain_fault("RACING_SETUP_COMPLETION_ORIGINAL_SID_TURN_CHANGED")
            raise Stopped("RACING_SETUP_COMPLETION_ORIGINAL_SID_TURN_CHANGED")
        return result.text

    def _completed(self, role, content, phase):
        if not (type(content) is list and all(type(x) is dict and
                set(x) <= {"type", "text", "cache_control"} and x.get("type") == "text" and
                type(x.get("text")) is str for x in content)):
            raise ValueError("DYNTEAM_RACING_OPAQUE_NATIVE_TEXT_PARTS")
        native_content = [{"type": "text", "text": COUNT14_RACING_CHARTER}, *content]
        try:
            result = self.turn(role, native_content, phase)
        except NativePhaseUnadmitted:
            # Ordinary guarded waiting/refusal is not a scientific/accounting
            # fault, UNKNOWN or model retry. The native prompt was never sent.
            raise CallDeadline([]) from None
        except Exception:
            self.retain_fault("DYNTEAM_RACING_NATIVE_TURN_FAILED_RETAIN_NO_REPLAY")
            raise Stopped("DYNTEAM_RACING_NATIVE_TURN_FAILED_RETAIN_NO_REPLAY") from None
        if not (type(result) is CompletedNativeTurn and type(result.text) is str and type(result.thinking) is str and
                result.original_relay_receipts_complete is True and result.physical_terminal is True):
            self.retain_fault("DYNTEAM_RACING_NATIVE_TURN_UNPROVEN_RETAIN_NO_REPLAY")
            raise Stopped("DYNTEAM_RACING_NATIVE_TURN_UNPROVEN_RETAIN_NO_REPLAY")
        return result

    def call_parse(self, user_content, phase, meta=None, *, cancel_event=None,
                   continuation_retries=2, **_native_unused):
        meta = meta or {}
        player = meta.get("player")
        if not (type(player) is str and player in {f"P{i}" for i in range(7)} and
                phase in ("submit", "review", "defend")):
            raise ValueError("DYNTEAM_RACING_PINNED_PLAYER_PHASE")
        if not self.admission_open() or (cancel_event is not None and cancel_event.is_set()):
            raise CallDeadline([])  # before native turn/reservation only
        role = f"racing-player-{int(player[1:]):02d}"
        # No model transport/cancel token/effort override is passed. The native
        # port supplies the same frozen CLI options as all other model roles.
        result = self._completed(role, user_content, phase)
        info = {"attempts": 1, "continuations": 0, "native_relay_accounted": True}
        try:
            return parse_phase(result.text, phase), info
        except ParseError as error:
            last_error = error
        partial = result.text or ("<thinking>\n" + result.thinking + "\n</thinking>" if result.thinking else "")
        # Preserve native parse-continuation behavior, but never its plain
        # empty-response retry. UNKNOWN/unproven work cannot reach this branch.
        if not partial or self.continuation_template is None:
            raise last_error
        if type(continuation_retries) is not int or not 0 <= continuation_retries <= 2:
            raise ValueError("DYNTEAM_RACING_AT_MOST_TWO_COMPLETED_PARSE_CONTINUATIONS")
        for ordinal in range(1, continuation_retries + 1):
            if not self.admission_open() or (cancel_event is not None and cancel_event.is_set()):
                raise CallDeadline([])
            continuation = self.continuation_template.replace("{PARTIAL}", partial).replace(
                "{SCHEMA}", CONTINUATION_SCHEMAS[phase])
            if ordinal > 1:
                # Latest completed partial plus an explicit ordinal makes the
                # second continuation a distinct request, never exact replay.
                continuation += "\n\n[completed parse continuation " + str(ordinal) + ": repair the previous completed output]"
            result = self._completed(role, [{"type": "text", "text": continuation}], phase)
            info["attempts"] += 1
            info["continuations"] = ordinal
            try:
                return parse_phase(result.text, phase), info
            except ParseError as error:
                last_error = error
            partial = result.text or ("<thinking>\n" + result.thinking + "\n</thinking>" if result.thinking else "")
            if not partial:
                break
        raise last_error


class ActivePhaseClock(PhaseClock):
    def __init__(self, *args, active_now, **kwargs):
        super().__init__(*args, **kwargs)
        self.active_now = active_now

    def _close(self, reason):
        self.closed = True
        self.close_reason = reason
        self.t_closed = self.active_now()
        # This is only a BEFORE-admission signal to NativeRacingLLM. There is
        # deliberately no post/send cancellation port anywhere in this adapter.
        self.cancel.set()


class Count14RacingPrompts(Prompts):
    """Keep the phase schemas, adapt m7 feedback to public count14 tools."""
    def defend_run_only(self):
        text = self.phase["defend"]
        replacement = (
            "The original public task-tool execution did not reproduce your proposed failure reliably. "
            "You may rebut or revise the case once. This is public execution evidence only, not an official verdict."
        )
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith(self.run_only_replaces):
                lines[i] = replacement
                return "\n".join(lines)
        raise ValueError("DYNTEAM_RACING_NATIVE_DEFEND_OPENING_PIN")

    def run_result_section(self, tier):
        rows = {
            "fail": "Two original public-tool runs reproduced the same public failure signature.",
            "pass": "Two original public-tool runs did not exhibit the proposed public failure.",
            "invalid": "The original public-tool run was unavailable, invalid, or not reproducible; do not infer success or failure.",
        }
        if tier not in rows:
            raise ValueError("DYNTEAM_RACING_PUBLIC_RESULT_ENUM")
        return "PUBLIC TASK-TOOL EVIDENCE (NOT AN OFFICIAL VERDICT):\n" + rows[tier]


class Count14RacingGame(Game):
    """Preserve native submit/review/defend/pool mechanics, never cancel tails.

    m7 uses the original public task-tool judge, never an official/reference
    oracle. m4/none remains an explicit legacy OWN component fixture, NOT the
    planned formal racing treatment. K3 stays isolated in original AUX.
    """
    def __init__(self, *args, active_now, **kwargs):
        super().__init__(*args, **kwargs)
        native_judge = ((self.cfg.get("method") == "m4" and type(self.judge) is NullJudge) or
                        (self.cfg.get("method") == "m7" and type(self.judge) is Count14PublicRacingJudge and
                         type(self.pr) is Count14RacingPrompts))
        if not native_judge or self.transport is not None:
            self.player_pool.shutdown(wait=False)
            self.exec_pool.shutdown(wait=False)
            raise ValueError("DYNTEAM_RACING_COUNT14_NO_REFERENCE_NO_ALTERNATE_TRANSPORT")
        if not (callable(active_now) and self.cfg.get("P") == 7 and type(self.llm) is NativeRacingLLM and
                len(self.players) == 7 and {p.pid for p in self.players} == {f"P{i}" for i in range(7)} and
                all(type(p) is ThinkerPlayer and p.llm is self.llm for p in self.players)):
            self.player_pool.shutdown(wait=False)
            self.exec_pool.shutdown(wait=False)
            raise ValueError("DYNTEAM_RACING_NATIVE_SEVEN_PLAYERS_PAUSE_CLOCK")
        self.active_now = active_now
        self.llm.bind_continuation_template(self.pr.continuation_tpl)
        # Per-object original method globals, not a global time monkeypatch:
        # each block retains its OWN original pause-aware clock. No source
        # method body, other Game object or Python time module is changed.
        active_time = SimpleNamespace(time=active_now, sleep=time.sleep)
        for name in ("_ask", "_schedule_exec", "_exec_result", "_merge_existing", "_run_tiers", "_drop", "play_round", "summary"):
            original = getattr(Game, name)
            scope = dict(original.__globals__, time=active_time)
            rebound = FunctionType(original.__code__, scope, original.__name__, original.__defaults__, original.__closure__)
            rebound.__kwdefaults__ = original.__kwdefaults__
            setattr(self, name, MethodType(rebound, self))
        self.natural_tail_retained = False
        self._closed_pools = False

    def _start_watchdog(self):
        # No diagnostic thread holding scientific locks, no abort_all(). The
        # existing owner supplies admission/stop and calls its normal poll loop.
        self._watch = None

    def _clock(self, phase):
        now = self.active_now()
        policy = self.cfg.get("phase_policy", {})
        cap = policy.get("caps", {}).get(phase)
        if cap is None:
            cap = 1e9
        return ActivePhaseClock(phase, now, min(now + cap, self.ledger.deadline), n=0,
                                close_frac=policy.get("close_frac", 0.75), lead=policy.get("lead", 0.0),
                                active_now=self.active_now)

    def _run_parallel(self, tasks, clock=None, rnd=None):
        if clock is not None:
            clock.set_n(len(tasks), self.cfg.get("phase_policy", {}).get("close_frac", 0.75))
        futures = {self.player_pool.submit(fn): (key, pid) for key, pid, fn in tasks}
        pending, out = set(futures), {}
        while pending:
            done, pending = cf.wait(pending, timeout=0.05, return_when=cf.FIRST_COMPLETED)
            for future in done:
                try:
                    out[futures[future][0]] = future.result()
                except BaseException as error:
                    out[futures[future][0]] = error
            if clock is not None and not clock.closed and self.active_now() >= clock.cap:
                clock.close("cap")
            if pending and ((clock is not None and clock.closed) or self.ledger.stopping()):
                # Native admission can precede small file publication. Preserve
                # already-admitted results, with the original finite 30s bound.
                admitted = [f for f in pending if clock is not None and futures[f][0] in clock.admitted]
                if admitted:
                    done_admitted, _ = cf.wait(admitted, timeout=30)
                    for future in done_admitted:
                        try:
                            out[futures[future][0]] = future.result()
                        except BaseException as error:
                            out[futures[future][0]] = error
                    pending -= done_admitted
                for future in pending:
                    key, pid = futures[future]
                    # Preserve every pending native future, including STOP (the
                    # upstream hard-stop path omitted some from busy custody).
                    self.busy[pid] = future
                    out[key] = CallDeadline([])
                    if clock is not None:
                        self._drop(clock, rnd, pid, "native physical tail retained", key=key)
                self.natural_tail_retained = True
                break
        return out

    def _shutdown(self):
        # Do not call upstream cleanup, player.close/abort, cancel_futures=True
        # or shutil.rmtree. Owner must poll exact physical custody first.
        if not self._closed_pools:
            self.player_pool.shutdown(wait=False, cancel_futures=False)
            self.exec_pool.shutdown(wait=False, cancel_futures=False)
            self._closed_pools = True

    def physical_tail_done(self):
        # Pure future control flags, not response inspection. Owner additionally
        # verifies original ledger/model/tool/native process custody before any
        # retirement or approved temporary cleanup.
        models_done = all(f is None or f.done() for f in self.busy.values())
        public_tools_done = all(f is None or f.done() for sub in self.subs for f in sub.exec_futs)
        return (models_done and public_tools_done and
                (type(self.judge) is NullJudge or self.judge.physical_clear()))


class BottleneckSchedule:
    """PUBLIC-control-only trigger, preregistered before any model result.

    Original accepted-claim/merged-public-test progress ordinal + active clock;
    no candidate/source/content, verdict or private logs. One open round, no
    catch-up loop or overlap. Original checkpoints close the outer admission.
    """
    def __init__(self, *, active_seconds=600):
        if active_seconds != 600:
            raise ValueError("DYNTEAM_RACING_PREREGISTERED_600_ACTIVE_SECONDS")
        self.interval = active_seconds
        self.last_progress = None
        self.last_progress_at = None
        self.last_round_at = None
        self.open_round = None
        self.ordinal = 0
        self.previous_time = None

    def observe(self, *, active_now, progress_ordinal, original_admission_open, physical_previous_clear):
        if not (type(active_now) in (int, float) and math.isfinite(active_now) and active_now >= 0 and
                type(progress_ordinal) is int and progress_ordinal >= 0 and
                type(original_admission_open) is bool and type(physical_previous_clear) is bool):
            raise ValueError("DYNTEAM_RACING_TYPED_PUBLIC_PROGRESS")
        if ((self.previous_time is not None and active_now < self.previous_time) or
                (self.last_progress is not None and progress_ordinal < self.last_progress)):
            raise ValueError("DYNTEAM_RACING_CONTROL_REGRESSION_RETAIN")
        self.previous_time = active_now
        if progress_ordinal != self.last_progress:
            self.last_progress, self.last_progress_at = progress_ordinal, active_now
        anchor = max(self.last_progress_at, self.last_round_at or 0)
        if (self.open_round is not None or not original_admission_open or not physical_previous_clear or
                active_now - anchor < self.interval):
            return None
        self.ordinal += 1
        self.open_round = self.ordinal
        self.last_round_at = active_now
        return self.ordinal

    def close(self, ordinal, *, physical_terminal):
        if ordinal != self.open_round or physical_terminal is not True:
            raise ValueError("DYNTEAM_RACING_NATURAL_ROUND_TERMINAL_REQUIRED")
        self.open_round = None


class RoundControl:
    """Scheduling only, NEVER financial accounting or model reservation.

    Original ledger/AdmissionGate handles every model call. No $4/estimated
    Anthropic prices are imported into experiment accounting. A closed gate
    stops NEW scientific work; accepted requests retain their original custody.
    """
    def __init__(self, *, active_now, admission_open, duration=600):
        if not (callable(active_now) and callable(admission_open) and duration == 600):
            raise ValueError("DYNTEAM_RACING_ORIGINAL_PAUSE_CLOCK_GATE")
        self.clock, self.admission_open = active_now, admission_open
        self.deadline = active_now() + duration
        self.stop_event = threading.Event()
        self.reason = None

    def stopping(self):
        if self.clock() >= self.deadline:
            self.reason = "ROUND_ACTIVE_DEADLINE_DRAIN_NATURALLY"
            self.stop_event.set()
        elif not self.admission_open():
            self.reason = "ORIGINAL_GATE_CLOSED_DRAIN_NATURALLY"
            self.stop_event.set()
        return self.stop_event.is_set()

    def end_reason(self):
        return self.reason

    def remaining_s(self):
        return max(0, self.deadline - self.clock())
