"""Prospective protected full SID-domain producer, NOT a cold owner restorer.

Original classes/claim/bind code remain unchanged. The sole metadata owner calls
the bound instance wrapper. All disk work is outside original science/session/
domain locks. Raw SIDs occur only in private control, never public().
"""
from contextlib import contextmanager
from pathlib import Path
from types import MethodType
import fcntl
import hashlib
import json
import os
import stat
import threading
import uuid

from dynteam_sessions import AffinityDomain, CohortSessions, DynamicSessions

SESSION_SOURCE_SHA256 = 'c80000d66a4958a3c2d5854d188242806ef305aaee73d2be879571e31c3909dd'
SCHEMA = 'count14-formal-protected-full-used-domain-v1'
SIDECAR = 'count14-formal-protected-full-used-domain-cut-v1'


class WaitForFullUsedDomain(RuntimeError):
    """Fixed PUBLIC code only; no input, exception message or SID interpolation."""


def need(ok, code):
    if not ok:
        raise WaitForFullUsedDomain(code)


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(wire(value)).hexdigest()


def sha(value):
    need(type(value) is str and len(value) == 64 and
         all(c in '0123456789abcdef' for c in value), 'FULL_USED_SHA256_BINDING')
    return value


def verify_session_source():
    import dynteam_sessions
    path = Path(dynteam_sessions.__file__)
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
         hashlib.sha256(path.read_bytes()).hexdigest() == SESSION_SOURCE_SHA256,
         'FULL_USED_EXACT_ORIGINAL_SESSION_SOURCE')
    return SESSION_SOURCE_SHA256


class FullUsedDomainProducer:
    """Component interface; production entry is install_before_formal(owner).

    No attach/reopen/replay/repair API exists. An interrupted intent is WAIT, not
    a reconstructed domain. Existing or nonempty domains cannot be installed.
    """
    def __init__(self, sessions, directory, *, science_mutex, source_binding):
        self.sessions, self.science_mutex = sessions, science_mutex
        self.pid, self.thread = os.getpid(), threading.get_ident()
        self.serial = threading.Lock()
        self.failure = None
        self.pending = False
        self.in_bind = False
        self.sequence, self.record_sha256 = 0, None
        self.saved = ()
        self.fd = None
        need(type(sessions) is CohortSessions and sessions.tracks and
             all(type(t) is DynamicSessions for t in sessions.tracks.values()),
             'FULL_USED_EXACT_ORIGINAL_SESSION_TYPES')
        self.tracks = dict(sessions.tracks)
        self.domain = next(iter(self.tracks.values())).domain
        need(type(self.domain) is AffinityDomain and
             all(t.domain is self.domain for t in self.tracks.values()) and
             self.domain.claim.__func__ is AffinityDomain.claim and
             all(t.bind.__func__ is DynamicSessions.bind for t in self.tracks.values()),
             'FULL_USED_ONE_UNMODIFIED_SHARED_DOMAIN')
        self.used_object = self.domain.used
        need(type(self.used_object) is set, 'FULL_USED_ORIGINAL_USED_SET_IDENTITY')
        self._outside_locks()
        verify_session_source()
        need(type(source_binding) is dict and set(source_binding) ==
             {'contract_sha256', 'cohort_sha256', 'owner_sha256',
              'factory_parent_sha256'}, 'FULL_USED_EXACT_SOURCE_BINDINGS')
        self.binding = {k: sha(v) for k, v in source_binding.items()}
        self.binding.update(session_source_sha256=SESSION_SOURCE_SHA256,
            producer_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        self.binding_sha256 = digest(self.binding)
        need(self.binding['cohort_sha256'] == digest(sorted(self.tracks)),
             'FULL_USED_COMPLETE_COHORT_BINDING')
        # Pure memory under original locks; never copy/reassign/clear used.
        need(not self._domain_values(), 'FULL_USED_INSTALL_BEFORE_ANY_SID_CLAIM')
        for track in self.tracks.values():
            with track._lock:
                need(not track._current, 'FULL_USED_INSTALL_BEFORE_ANY_SESSION_BIND')
        self.directory = Path(directory)
        self._outside_locks()
        need(self.directory.is_absolute() and self.directory.resolve() == self.directory and
             not self.directory.is_symlink(), 'FULL_USED_CANONICAL_FRESH_CONTROL_DIRECTORY')
        parent = self.directory.parent.lstat()
        need(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.geteuid() and
             stat.S_IMODE(parent.st_mode) == 0o700, 'FULL_USED_EXISTING_PRIVATE_OWNER_HOME')
        self.directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        self.fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        s = os.fstat(self.fd)
        self.directory_identity = (s.st_dev, s.st_ino)
        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.original_claim = self.domain.claim
        self.original_binds = {t: track.bind for t, track in self.tracks.items()}
        try:
            self._append('INITIAL_EMPTY', ())
            self._install_hooks()
        except BaseException:
            self.failure = 'FULL_USED_INSTALL_PARTIAL_RETAINED_NO_RETRY'
            raise WaitForFullUsedDomain(self.failure) from None

    def _outside_locks(self):
        need(os.getpid() == self.pid and threading.get_ident() == self.thread,
             'FULL_USED_SAME_ORIGINAL_METADATA_OWNER_THREAD')
        need(not self.science_mutex._is_owned() and not self.domain.lock.locked() and
             all(not t._lock.locked() for t in self.tracks.values()),
             'FULL_USED_NO_ORIGINAL_LOCK_DURING_CONTROL_IO_OR_SERIAL_WAIT')

    def _domain_values(self):
        try:
            with self.domain.lock:
                result = tuple(sorted(self.domain.used))
            need(all(type(v) is str and str(uuid.UUID(v)) == v for v in result),
                 'FULL_USED_CANONICAL_FRAMEWORK_SID_VALUES')
        except Exception:
            self.failure = 'FULL_USED_DOMAIN_CORRUPT_RETAIN_WAIT'
            raise WaitForFullUsedDomain(self.failure) from None
        return result

    def _install_hooks(self):
        producer = self
        def claim(domain, canonical):
            # Called INSIDE original bind's session lock: pure checks + original
            # claim only. No producer lock, callbacks, filesystem or other I/O.
            if not (domain is producer.domain and producer.in_bind and producer.pending and
                    producer.failure is None and os.getpid() == producer.pid and
                    threading.get_ident() == producer.thread):
                producer.failure = 'FULL_USED_CLAIM_OUTSIDE_DURABLE_BIND_REFUSED'
                raise WaitForFullUsedDomain(producer.failure)
            return producer.original_claim(canonical)
        self.claim_hook = claim
        self.domain.claim = MethodType(claim, self.domain)
        self.bind_hooks = {}
        for trajectory, track in self.tracks.items():
            def bind(bound, role, birth_sha256, native_session_uuid, *, previous_physical_clear):
                return producer._bind(bound, role, birth_sha256, native_session_uuid,
                    previous_physical_clear=previous_physical_clear)
            self.bind_hooks[trajectory] = bind
            track.bind = MethodType(bind, track)

    def _check_hooks(self):
        ok = (set(self.sessions.tracks) == set(self.tracks) and
             all(self.sessions.tracks[k] is t for k, t in self.tracks.items()) and
             self.domain.used is self.used_object and digest(self.binding) == self.binding_sha256 and
             self.domain.claim.__func__ is self.claim_hook and
             all(t.domain is self.domain and t.bind.__func__ is self.bind_hooks[k]
                 for k, t in self.tracks.items()))
        if not ok:
            self.failure = 'FULL_USED_EXACT_INSTANCE_HOOK_CUSTODY_LOST_WAIT'
            raise WaitForFullUsedDomain(self.failure)

    def _require_saved(self, values):
        if values != self.saved:
            self.failure = 'FULL_USED_UNPUBLISHED_DOMAIN_MUTATION_WAIT'
            raise WaitForFullUsedDomain(self.failure)

    @contextmanager
    def _operation(self):
        self._outside_locks()
        need(self.failure is None and not self.pending, 'FULL_USED_FAILED_OR_PENDING_RETAIN_WAIT')
        need(self.serial.acquire(blocking=False), 'FULL_USED_NO_REENTRANT_OR_CONCURRENT_PRODUCER')
        try:
            self._check_hooks()
            yield
        finally:
            self.serial.release()

    def _io_guard(self):
        self._outside_locks()
        s, opened = self.directory.lstat(), os.fstat(self.fd)
        need(self.directory.resolve() == self.directory and not self.directory.is_symlink() and
             stat.S_ISDIR(s.st_mode) and s.st_uid == os.geteuid() and
             stat.S_IMODE(s.st_mode) == 0o700 and
             (s.st_dev, s.st_ino) == (opened.st_dev, opened.st_ino) == self.directory_identity,
             'FULL_USED_SAME_PRIVATE_DIRECTORY_CUSTODY')

    def _write_new(self, name, raw):
        self._io_guard()
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.fd)
        with os.fdopen(fd, 'wb') as f:
            s = os.fstat(f.fileno())
            need(stat.S_ISREG(s.st_mode) and s.st_uid == os.geteuid() and
                 stat.S_IMODE(s.st_mode) == 0o600 and s.st_nlink == 1,
                 'FULL_USED_PRIVATE_SINGLE_LINK_CONTROL_FILE')
            f.write(raw)
            f.flush()
            self._outside_locks()
            os.fsync(f.fileno())
        self._io_guard()
        os.fsync(self.fd)

    def _append(self, kind, values):
        self._outside_locks()
        body = dict(schema=SCHEMA, sequence=self.sequence + 1, kind=kind,
            previous_record_sha256=self.record_sha256, source_binding=self.binding,
            full_used=list(values), full_used_sha256=digest(list(values)),
            used_count=len(values), whole_paid_restore_implemented=False)
        raw = wire(body)
        self._write_new(str(body['sequence']).zfill(12) + '.json', raw)
        self.sequence, self.record_sha256 = body['sequence'], hashlib.sha256(raw).hexdigest()
        self.saved = tuple(values)

    def _bind(self, track, *args, **kwargs):
        with self._operation():
            need(self.tracks.get(track.trajectory) is track, 'FULL_USED_EXACT_BOUND_TRACK')
            before = self._domain_values()
            self._require_saved(before)
            # An intent is durable BEFORE normal claim. A crash anywhere after
            # it is an unresolved intent, not an apparently complete history.
            self.pending = True
            try:
                self._append('BIND_INTENT', before)
                self.in_bind = True
                try:
                    result = self.original_binds[track.trajectory](*args, **kwargs)
                except Exception:
                    self.in_bind = False
                    need(self._domain_values() == before,
                         'FULL_USED_ORIGINAL_BIND_PARTIAL_RETAIN_WAIT')
                    self._append('BIND_REFUSED_UNCHANGED', before)
                    self.pending = False
                    raise
                finally:
                    self.in_bind = False
                after = self._domain_values()
                need(type(result) is bool and set(before) <= set(after) and
                     len(after) - len(before) == int(result),
                     'FULL_USED_ORIGINAL_MONOTONIC_CLAIM_SEMANTICS')
                self._append('BIND_APPLIED' if result else 'BIND_IDEMPOTENT', after)
                self.pending = False
                return result
            except BaseException:
                if self.pending:
                    self.failure = 'FULL_USED_DURABILITY_UNKNOWN_RETAIN_NO_ACK_NO_RETRY'
                    raise WaitForFullUsedDomain(self.failure) from None
                raise # unchanged original rejection, no retry/reclassification

    def protected_for_cut(self, cut_binding):
        """Only a protected per-track writer sidecar; NOT a whole-cohort cut."""
        with self._operation():
            need(type(cut_binding) is dict and set(cut_binding) ==
                 {'cut_sha256', 'trajectory_sha256', 'membership_sha256'},
                 'FULL_USED_EXACT_PER_TRACK_CUT_BINDING')
            binding = {k: sha(v) for k, v in cut_binding.items()}
            self._require_saved(self._domain_values())
            return dict(schema=SIDECAR, source_binding=dict(self.binding), cut_binding=binding,
                record_sequence=self.sequence, record_sha256=self.record_sha256,
                full_used=list(self.saved), full_used_sha256=digest(list(self.saved)),
                used_count=len(self.saved), shared_domain_history=True,
                whole_cohort_frozen=False, whole_paid_restore_implemented=False,
                original_L1_cold_supported=False)

    def public(self):
        # In-memory hash/count/status only. No raw SID, path, roster or private log.
        return dict(schema='count14-formal-full-used-domain-PUBLIC-v1',
            source_binding_sha256=digest(self.binding), record_sha256=self.record_sha256,
            full_used_sha256=digest(list(self.saved)), used_count=len(self.saved),
            record_sequence=self.sequence, pending=self.pending, failure_code=self.failure,
            whole_cohort_frozen=False, whole_paid_restore_implemented=False,
            actual_cold_qualified=False)

    def public_for_cut(self, cut_binding):
        protected = self.protected_for_cut(cut_binding)
        return {**self.public(), 'cut_binding': protected['cut_binding']}
