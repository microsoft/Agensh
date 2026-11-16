"""One ORIGINAL owner-loop step for native-session metadata publication.

No extra scientific dispatcher/thread/model loop. HTTP receipt threads enqueue
and wait with deadlines; the existing owner loop calls poll_once(). Original
budget/control projection is read BEFORE metadata I/O, with its locks released.
Only after durable anonymous metadata is committed is the native UUID mapping
made available and the original router allowed to call prompt().
"""
from __future__ import annotations

from dynteam_metadata import BudgetAnchor, catalogue, need
from dynteam_sessions import CohortSessions
from anonymous_roster_journal import AnonymousRosterJournal
from native_session_control import NativeSessionInbox


class NativeMetadataPublisher:
    def __init__(self, *, inbox, sessions, journals, bindings, original_control_projection,
                 qualification_only=False):
        need(type(inbox) is NativeSessionInbox and type(sessions) is CohortSessions and
             type(qualification_only) is bool, "DYNTEAM_ORIGINAL_OWNER_METADATA_COMPONENTS")
        need(set(journals) == set(sessions.tracks) and
             all(type(j) is AnonymousRosterJournal for j in journals.values()),
             "DYNTEAM_THREE_SEPARATE_ANONYMOUS_JOURNALS")
        need(qualification_only or not any(j.qualification_only for j in journals.values()),
             "DYNTEAM_OWN_FIXTURE_JOURNAL_CANNOT_ACTIVATE")
        complete = {(t, role) for t, track in sessions.tracks.items() for role in track.roles}
        need(all(journals[t].projection.roles == track.roles for t, track in sessions.tracks.items()),
             "DYNTEAM_NATIVE_FINANCIAL_SESSION_METADATA_CATALOGUES_MATCH")
        need(set(bindings) <= complete and (qualification_only or set(bindings) == complete),
             "DYNTEAM_FULL_THREE_BY34_NATIVE_CONTROL_BINDINGS")
        need(callable(original_control_projection), "DYNTEAM_ORIGINAL_CONTROL_PROJECTION_REQUIRED")
        self.inbox, self.sessions, self.journals = inbox, sessions, dict(journals)
        self.bindings = dict(bindings)
        self.project = original_control_projection
        self.qualification_only = qualification_only
        self.component_bindings_complete = not qualification_only
        # Cardinality alone is never whole-runtime/activation qualification.
        self.qualified_for_model_activation = False
        self.last_failures = []

    def poll_once(self):
        done = 0
        for ticket in self.inbox.drain():
            accepted = False
            row = ticket.envelope
            try:
                t, role = row["trajectory_id"], row["role_slot"]
                need(self.bindings.get((t, role)) == row["block"], "DYNTEAM_ACTUAL_CONTROL_BLOCK_ROLE_BINDING")
                custody=getattr(self,'native_kernel_tool_custody',None)
                if custody is not None:
                    from smoke_racing_tools_kernel_custody import NativeKernelToolCustody
                    need(type(custody) is NativeKernelToolCustody,
                         'DYNTEAM_TYPED_FRESH_NATIVE_SESSION_STARTUP_CUSTODY')
                    need(custody.core.peers.validate(row,ticket.peer) is True,
                         'DYNTEAM_SESSION_READY_CURRENT_REGISTERED_PEER_BEFORE_DURABLE_BIND')
                    custody.observe_first_native_session(t,role,row=row)
                anchor, physical_clear = self.project(t, role)
                need(type(anchor) is BudgetAnchor and type(physical_clear) is bool,
                     "DYNTEAM_TYPED_ORIGINAL_CONTROL_PROJECTION")
                anchor.checked()
                journal = self.journals[t]
                birth = journal.projection._identity(role, row["logical_birth_sha256"])
                sid = row["native_session_uuid"]
                track = self.sessions.tracks[t]
                # Pure preflight with the SAME lock order as DynamicSessions.bind.
                # No SQL, filesystem, waits or callbacks occur in these locks.
                with track._lock:
                    old = track._current.get((t, role))
                    if old != (birth, sid):
                        need(physical_clear is True, "DYNTEAM_OLD_ROLE_PHYSICAL_INFLIGHT_RETAIN")
                        with track.domain.lock:
                            need(sid not in track.domain.used, "DYNTEAM_SESSION_REUSE_REFUSED")
                birth, _records = journal.record_native_session(row, anchor)
                track.bind(role, birth, sid, previous_physical_clear=physical_clear)
                if custody is not None:custody.commit_native_session(t,role,row)
                accepted = True
                done += 1
            except Exception as error:
                self.last_failures.append({"exception_type": type(error).__name__,
                                           "PUBLIC_code": "DYNTEAM_NATIVE_METADATA_RETAIN_NO_PROMPT"})
                # Metadata-only evidence for a failed original handler. Never
                # read/log args, locals, envelope, SID, account or model data.
                try:
                    import re
                    code = str(error)
                    locations = []
                    tb = error.__traceback__
                    while tb is not None and len(locations) < 16:
                        frame = tb.tb_frame.f_code
                        locations.append(dict(file=frame.co_filename.rsplit('/', 1)[-1],
                                              function=frame.co_name, line=tb.tb_lineno))
                        tb = tb.tb_next
                    self.last_failures[-1].update(
                        fixed_guard_code=code if re.fullmatch(r'DYNTEAM_[A-Z0-9_]{1,240}', code) else None,
                        locations=locations)
                except Exception:
                    pass  # Observation must never affect the original false ACK.
                self.last_failures = self.last_failures[-128:]
            self.inbox.resolve(ticket, durable=accepted)
        return done
