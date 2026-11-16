"""Original-owner whole execution-domain park, not a per-PID SIGSTOP scheme.

Existing, pre-exec OWN cgroup-v2 domains only: no mkdir/migration/controller or
host configuration changes, Docker calls, signals, CLI disconnects or restarts.
ALL workers AND original native SDK processes must be inside registered domains.
A host-side SDK sharing the control owner's cgroup therefore cannot qualify.
The actual launcher must supply trustworthy pre-exec domain bindings; this code
and OWN synthetic cgroup fixtures alone are NOT native runtime qualification.
"""
from contextlib import ExitStack
import ctypes
import json
import os
from pathlib import Path, PurePosixPath
import stat
from common import need, digest, wire, sha, strict
from bridge import process_identity

CGROUP2_SUPER_MAGIC = 0x63677270


def _cgroup2_filesystem(fd):
    # Linux fstatfs: f_type is the first native long; ample aligned backing.
    data = (ctypes.c_long * 64)()
    libc = ctypes.CDLL(None, use_errno=True)
    need(libc.fstatfs(fd, ctypes.byref(data)) == 0, 'WRITER_FENCE_FSTATFS')
    return data[0] == CGROUP2_SUPER_MAGIC


def process_cgroup_v2(identity):
    need(type(identity) is dict and set(identity) == {'pid','start_ticks','boot_id'}
         and type(identity['pid']) is int and identity['pid'] > 0
         and type(identity['start_ticks']) is int and identity['start_ticks'] > 0,
         'WRITER_FENCE_PROCESS_IDENTITY')
    need(process_identity(identity['pid']) == identity, 'WRITER_FENCE_PROCESS_CHANGED')
    rows = Path('/proc', str(identity['pid']), 'cgroup').read_text().splitlines()
    groups = [line[3:] for line in rows if line.startswith('0::')]
    need(len(groups) == 1, 'WRITER_FENCE_CGROUP2_REQUIRED')
    relative = PurePosixPath(groups[0])
    need(relative.is_absolute() and '..' not in relative.parts
         and str(relative) == groups[0], 'WRITER_FENCE_CGROUP_PATH')
    need(process_identity(identity['pid']) == identity, 'WRITER_FENCE_PROCESS_CHANGED')
    return relative


class CgroupV2Domain:
    """Pinned existing host-owned execution boundary. Never creates/moves PIDs.

    expected_binding_sha256 is from trusted original bootstrap, not worker JSON.
    The launch receipt must attest assignment BEFORE exec/fork. Merely observing
    a process currently below a cgroup cannot prove that pre-exec provenance.
    """
    def __init__(self, directory, *, launch_receipt_sha256, expected_binding_sha256):
        sha(launch_receipt_sha256);sha(expected_binding_sha256)
        p = Path(directory)
        root = Path('/sys/fs/cgroup')
        need(p.is_absolute() and p.resolve() == p and p != root
             and p.is_relative_to(root) and not p.is_symlink(), 'WRITER_FENCE_OWN_CGROUP_PATH')
        self.path = p;self.fd = os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.closed = False
        try:
            st = os.fstat(self.fd)
            need(_cgroup2_filesystem(self.fd), 'WRITER_FENCE_REAL_CGROUP2_FILESYSTEM')
            need(st.st_uid in (0, os.geteuid()) and st.st_uid != 10000
                 and not st.st_mode & 0o022, 'WRITER_FENCE_TRUSTED_CGROUP_OWNER')
            self.inode = (st.st_dev, st.st_ino)
            self.relative = PurePosixPath('/') / p.relative_to(root).as_posix()
            self.binding = {'schema':'agensh-native-owned-writer-cgroup-v1',
                            'relative':str(self.relative), 'device':st.st_dev, 'inode':st.st_ino,
                            'owner_uid':st.st_uid, 'launch_receipt_sha256':launch_receipt_sha256}
            self.binding_sha = digest(self.binding)
            need(self.binding_sha == expected_binding_sha256, 'WRITER_FENCE_ORIGINAL_DOMAIN_PIN')
            need(self.read('cgroup.type').strip() == 'domain', 'WRITER_FENCE_NONTHREADED_DOMAIN')
            need(self.read('cgroup.freeze').strip() == '0' and not self.frozen(),
                 'WRITER_FENCE_NEW_SCOPE_ALREADY_FROZEN')
            need(not self.contains(process_identity(os.getpid())), 'WRITER_FENCE_CONTROL_OWNER_INSIDE_SCOPE')
        except BaseException:
            os.close(self.fd);self.closed = True;raise

    def current(self):
        need(not self.closed, 'WRITER_FENCE_DOMAIN_CLOSED')
        st = os.fstat(self.fd);p = self.path.lstat()
        need((st.st_dev, st.st_ino) == (p.st_dev, p.st_ino) == self.inode
             and stat.S_ISDIR(p.st_mode) and not self.path.is_symlink()
             and self.path.resolve() == self.path, 'WRITER_FENCE_DOMAIN_REPLACED')
        need(not self.contains(process_identity(os.getpid())), 'WRITER_FENCE_CONTROL_OWNER_INSIDE_SCOPE')

    def read(self, name):
        need(name in ('cgroup.type','cgroup.freeze','cgroup.events'), 'WRITER_FENCE_FIXED_KERNEL_FILE')
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
        try:
            need(stat.S_ISREG(os.fstat(fd).st_mode), 'WRITER_FENCE_KERNEL_REGULAR_FILE')
            raw = os.read(fd, 8193);need(len(raw) <= 8192, 'WRITER_FENCE_KERNEL_METADATA_BOUND')
            return raw.decode('ascii')
        finally:
            os.close(fd)

    def contains(self, identity):
        return process_cgroup_v2(identity).is_relative_to(self.relative)

    def frozen(self):
        rows = {}
        for line in self.read('cgroup.events').splitlines():
            pair = line.split();need(len(pair) == 2 and pair[0] not in rows,
                                    'WRITER_FENCE_KERNEL_EVENTS')
            rows[pair[0]] = pair[1]
        need(rows.get('frozen') in ('0','1') and rows.get('populated') in ('0','1'),
             'WRITER_FENCE_KERNEL_EVENTS')
        return rows['frozen'] == '1'

    def request(self, parked):
        need(type(parked) is bool, 'WRITER_FENCE_FIXED_FREEZE_VALUE');self.current()
        fd = os.open('cgroup.freeze', os.O_WRONLY | os.O_NOFOLLOW, dir_fd=self.fd)
        try:
            need(stat.S_ISREG(os.fstat(fd).st_mode), 'WRITER_FENCE_KERNEL_REGULAR_FILE')
            need(os.write(fd, b'1' if parked else b'0') == 1, 'WRITER_FENCE_KERNEL_SHORT_WRITE')
        finally:
            os.close(fd)
        self.current()

    def close_unparked(self):
        self.current();need(not self.frozen() and self.read('cgroup.freeze').strip() == '0',
                            'WRITER_FENCE_PARKED_DOMAIN_RETAIN_CONTROL')
        os.close(self.fd);self.closed = True


def registered_participants(owner):
    """Original owner objects, never shell.pending/worker supplied PID lists."""
    from native_team_owner import NativeTeamOwner
    from native_mcp_config import PURPOSES
    need(type(owner) is NativeTeamOwner and owner.started and not owner.closed
         and owner._stage_owner_identity == process_identity(os.getpid()),
         'WRITER_FENCE_ORIGINAL_SAME_LIVE_OWNER')
    roles = owner.ledger.frontier(owner.t)['roles']
    need(owner.roles == roles == [f'worker-{i:02d}' for i in range(len(roles))]
         and len(roles) in (1,2,16) and set(owner.peers) == set(roles),
         'WRITER_FENCE_COMPLETE_TEAM_ROSTER')
    rows = owner._stage_registry
    expected = {(r,p) for r in roles for p in PURPOSES}
    need(type(rows) is tuple and len(rows) == 4*len(roles)
         and {(r.role,r.purpose) for r in rows if r.kind == 'MCP'} == expected
         and {r.role for r in rows if r.kind == 'GIT'} == set(roles)
         and set(owner.sessions) == expected and set(owner.git) == set(roles),
         'WRITER_FENCE_ORIGINAL_COMPLETE_PORT_REGISTRY')
    participants = {}
    for role in roles:
        p = owner.peers[role]
        identity = {'pid':p['pid'], 'start_ticks':p['start_ticks'],
                    'boot_id':owner._stage_owner_identity['boot_id']}
        need(process_identity(p['pid']) == identity, 'WRITER_FENCE_WORKER_SAME_LIVE')
        participants['worker:'+role] = identity
    for row in rows:
        if row.kind != 'MCP':
            continue
        need(owner.sessions[(row.role,row.purpose)] is row.port
             and tuple(sorted(row.port.process_identity.items())) == row.process,
             'WRITER_FENCE_ORIGINAL_SDK_CHANGED')
        identity = dict(row.process)
        need(process_identity(identity['pid']) == identity, 'WRITER_FENCE_SDK_SAME_LIVE')
        participants['sdk:'+row.role+':'+row.purpose] = identity
    return participants


class NativeWriterFence:
    """Single cut, all registered workers+SDKs. Poll same handle, never retry.

    Persistent CLI/background writers need NOT exit. Domains preserve original
    processes/memory/connections. External service domains need their separate
    consistent-backup ports; this is not a SQL snapshot implementation.
    """
    def __init__(self, owner, domains, *, expected_domains_sha256, whole_team=None):
        self.owner = owner;self.ledger = owner.ledger;self.t = owner.t
        self.whole_team = whole_team
        self.participants = registered_participants(owner)
        if whole_team is not None:
            from native_whole_team import NativeWholeTeamRegistration
            need(type(whole_team) is NativeWholeTeamRegistration and whole_team.owner is owner,
                 'WRITER_FENCE_ORIGINAL_WHOLE_TEAM_REGISTRATION')
            self.participants.update(whole_team.current())
        need(type(domains) is tuple and domains and all(type(x) is CgroupV2Domain for x in domains),
             'WRITER_FENCE_TRUSTED_KERNEL_DOMAINS')
        self.domains = domains
        paths = [d.relative for d in domains]
        need(len({d.inode for d in domains}) == len(domains)
             and all(a == b or not a.is_relative_to(b) for a in paths for b in paths),
             'WRITER_FENCE_DISTINCT_NONNESTED_DOMAINS')
        self.domains_sha = digest(sorted(d.binding_sha for d in domains))
        need(self.domains_sha == sha(expected_domains_sha256), 'WRITER_FENCE_ALL_ORIGINAL_DOMAIN_PINS')
        self.state = 'REGISTERED';self.cut = None;self.receipt = None;self.role_acks = {}
        self._coverage()

    def _coverage(self):
        current = registered_participants(self.owner)
        if self.whole_team is not None:
            current.update(self.whole_team.current())
        need(current == self.participants,
             'WRITER_FENCE_REGISTERED_PROCESSES_CHANGED')
        covered = set()
        for key, identity in self.participants.items():
            matches = []
            for index, domain in enumerate(self.domains):
                domain.current()
                if domain.contains(identity):
                    matches.append(index)
            need(len(matches) == 1, 'WRITER_FENCE_EVERY_WORKER_AND_SDK_EXACTLY_ONE_DOMAIN')
            covered.update(matches)
        need(covered == set(range(len(self.domains))), 'WRITER_FENCE_NO_UNRELATED_DOMAIN')

    def _locks(self):
        stack = ExitStack()
        try:
            for row in sorted(self.owner._stage_registry,
                              key=lambda x:(0 if x.kind=='MCP' else 1,x.role,x.purpose)):
                stack.enter_context(row.port.lock)
            return stack
        except BaseException:
            stack.close();raise

    def _control_drained(self):
        from native_control_custody import require_control_drained
        values=[require_control_drained(row.listener,
                'WRITER_FENCE_ACCEPTED_CONTROL_NOT_DRAINED')
                for row in self.owner._stage_registry]
        bridge=getattr(self.owner,'bridge_backup',None)
        if bridge is not None:
            need(bridge.controls_ready(),'WRITER_FENCE_CLI_ACCEPTED_CONTROL_NOT_DRAINED')
        return values

    def _drained(self):
        f = self.ledger.frontier(self.t)
        need(not self.ledger.admission_fault(self.t) and f['state'] == 'DRAINING'
             and f['unresolved'] == f['reserved'] == f['active_operations'] == 0,
             'WRITER_FENCE_FULL_ACCEPTED_WORK_DRAIN_FIRST')
        if getattr(self.ledger,'native_unmanaged_cli',False):
            # Native tools have no custody/closure state. Their pending RPCs,
            # sockets and backend writers are frozen together, NOT drained or
            # fabricated terminal. Real model accounting above still drains.
            need(self.whole_team is not None,'WRITER_FENCE_UNMANAGED_REQUIRES_WHOLE_TEAM_FREEZE')
            return f
        if self.whole_team is None:self._control_drained()
        for row in self.owner._stage_registry:
            if row.kind == 'MCP':
                need(not row.port.pending and not row.port.broken and not row.port.closing
                     and not row.port.closed and row.port.child.poll() is None,
                     'WRITER_FENCE_SDK_CUSTODY_NOT_DRAINED')
            else:
                need(not row.port.children and not row.port.closing,
                     'WRITER_FENCE_GIT_HTTP_CUSTODY_NOT_DRAINED')
        return f

    def request_park(self, cut):
        from native_service_cut import NativeServiceCut
        need(type(cut) is NativeServiceCut and cut.ledger is self.ledger and cut.t == self.t,
             'WRITER_FENCE_ORIGINAL_SERVICE_CUT')
        need(self.state == 'REGISTERED', 'WRITER_FENCE_SINGLE_PARK_ATTEMPT')
        with self._locks():
            with self.ledger.tx():
                cut.current({'DRAINING'});self._drained();self._coverage()
                previous = self.ledger.db.execute(
                    "SELECT metadata FROM events WHERE trajectory=? AND kind='NATIVE_WRITER_PARK_REQUESTED'",
                    (self.t,)).fetchall()
                need(not any(strict(row[0])['cut_sha256'] == cut.cut_sha for row in previous),
                     'WRITER_FENCE_DURABLE_ONE_CUT_ATTEMPT')
                cut.bind_writer_fence(self)
                need(all(not d.frozen() and d.read('cgroup.freeze').strip() == '0'
                         for d in self.domains), 'WRITER_FENCE_ALL_DOMAINS_INITIALLY_RUNNING')
                self.cut = cut
                self.ledger.event(self.t,'NATIVE_WRITER_PARK_REQUESTED',
                    {'cut_sha256':cut.cut_sha,'domains_sha256':self.domains_sha,
                     'participants_sha256':digest(self.participants),'domains':len(self.domains)})
                self.state = 'PARK_REQUESTED'
            # NEVER wait for physical freeze while holding the ledger mutex.
            try:
                for domain in self.domains:
                    domain.request(True)
            except BaseException:
                self.state = 'PARK_INCOMPLETE'
                self.ledger.latch_fault(self.t,'NATIVE_WRITER_PARK_INCOMPLETE_RETAIN_NO_RETRY')
                raise
        return {'state':self.state,'domains':len(self.domains),'automatically_retried':False}

    def poll_park(self):
        need(self.state in ('PARK_REQUESTED','PARKED'), 'WRITER_FENCE_ORIGINAL_PARK_HANDLE')
        with self._locks():
            try:
                self.cut.current({'DRAINING'});self._drained();self._coverage()
                if not all(d.frozen() and d.read('cgroup.freeze').strip() == '1'
                           for d in self.domains):
                    need(self.state != 'PARKED', 'WRITER_FENCE_PARK_LOST')
                    return False  # Observation is pending, NOT terminal/retry.
                if self.state == 'PARKED':
                    return True
                receipt = {'schema':'agensh-native-writer-park-proof-v1',
                           'cut':self.cut.cut,'cut_sha256':self.cut.cut_sha,
                           'roles':self.owner.roles,'participants':sorted(self.participants),
                           'domains_sha256':self.domains_sha,
                           'participants_sha256':digest(self.participants),
                           'domain_bindings':[d.binding_sha for d in self.domains],
                           'kernel_frozen_all':True,'signals_cancel_restart_or_migration':False}
                if self.whole_team is not None:
                    receipt.update(schema='agensh-native-whole-team-park-proof-v1',
                        whole_team_inventory_sha256=self.whole_team.inventory_sha,
                        backend_services=sorted(self.whole_team.current()))
                self.receipt = self.cut.cas.store_bytes(wire(receipt))
                with self.ledger.mutex:
                    self.cut.current({'DRAINING'});self._coverage()
                    need(all(d.frozen() for d in self.domains), 'WRITER_FENCE_PARK_LOST')
                    for role in self.owner.roles:
                        reference = digest({'writer_receipt':self.receipt,'role':role,
                                            'generation':self.cut.cut['generation']})
                        self.ledger.ack(self.t,role,self.cut.cut['generation'],reference)
                        self.role_acks[role] = reference
                    with self.ledger.tx():
                        self.ledger.event(self.t,'NATIVE_WRITER_ALL_DOMAINS_PARKED',
                            {'cut_sha256':self.cut.cut_sha,'receipt_sha256':self.receipt['sha256']})
                self.state = 'PARKED'
                return True
            except BaseException:
                self.state = 'PARK_INCOMPLETE'
                self.ledger.latch_fault(self.t,'NATIVE_WRITER_PARK_PROOF_INCOMPLETE_RETAIN_NO_RETRY')
                raise

    def verify_capture(self, cut, roles):
        need(cut is self.cut and self.state == 'PARKED' and set(roles) == set(self.owner.roles),
             'WRITER_FENCE_CAPTURE_REQUIRES_ORIGINAL_ALL_PARKED')
        self._coverage()
        if self.whole_team is None:self._control_drained()
        need(all(d.frozen() and d.read('cgroup.freeze').strip() == '1' for d in self.domains),
             'WRITER_FENCE_CAPTURE_PARK_LOST')
        self.cut.cas.resolve(self.receipt)
        with self.ledger.mutex:
            acks = {r['component']:r['receipt_sha'] for r in self.ledger.db.execute(
                'SELECT component,receipt_sha FROM acks WHERE trajectory=? AND generation=?',
                (self.t,self.cut.cut['generation'])) if r['component'] in self.owner.roles}
        need(acks == self.role_acks, 'WRITER_FENCE_ORIGINAL_ROLE_PROOF_ACKS')
        # Exact workspace roots come from original trusted owner binding. The
        # launcher's session/HOME layout remains a separately qualified input.
        for role in roles:
            need(Path(roles[role]['workspace']) == Path(self.owner.gb['workspace_roots'][role]['path']),
                 'WRITER_FENCE_ORIGINAL_WORKSPACE_SOURCE')
        return self.receipt

    def request_release(self, stage, gate):
        """Prepare ALL original ports; existing gate resumes; thaw same domains.

        Original parked host HTTP calls may be admitted after gate release;
        already-SENT work still retains its normal custody if a thaw fails.
        This does not establish native router/CLI watchdog park compatibility.
        At20M there is no successor, so it rejects before ANY thaw/port change.
        """
        from native_stage_binding import NativeStageBinding
        from admission_gate import AdmissionGate
        need(type(stage) is NativeStageBinding and type(gate) is AdmissionGate
             and stage.ledger is self.ledger and gate.ledger is self.ledger
             and stage.trajectory == self.t and stage.old == self.cut.cut['generation'],
             'WRITER_FENCE_ORIGINAL_STAGE_AND_GATE')
        need(self.state == 'PARKED', 'WRITER_FENCE_RELEASE_ONCE_FROM_PARKED')
        # Stage constructor has verified committed snapshot and actual successor.
        row = self.ledger.db.execute('SELECT ref_sha FROM snapshots WHERE trajectory=? AND generation=?',
                                     (self.t,self.cut.cut['generation'])).fetchone()
        need(row is not None and row[0] == stage.ref, 'WRITER_FENCE_ORIGINAL_COMMITTED_REFERENCE')
        self._coverage();need(all(d.frozen() for d in self.domains), 'WRITER_FENCE_PARK_LOST')
        try:
            stage.prepare_team(self.owner)
            stage.resume_team(gate,self.owner)
            self.state = 'RELEASE_REQUESTED'
            with self.ledger.tx():
                self.ledger.event(self.t,'NATIVE_WRITER_SAME_LIVE_RELEASE_REQUESTED',
                    {'cut_sha256':self.cut.cut_sha,'snapshot_sha256':stage.ref,
                     'domains_sha256':self.domains_sha})
            for domain in self.domains:
                domain.request(False)
        except BaseException:
            self.state = 'RELEASE_INCOMPLETE'
            self.ledger.latch_fault(self.t,'NATIVE_WRITER_RELEASE_INCOMPLETE_RETAIN_NO_RETRY')
            raise

    def poll_release(self):
        need(self.state in ('RELEASE_REQUESTED','RELEASED'), 'WRITER_FENCE_ORIGINAL_RELEASE_HANDLE')
        try:
            self._coverage()
            if any(d.frozen() or d.read('cgroup.freeze').strip() != '0' for d in self.domains):
                need(self.state != 'RELEASED', 'WRITER_FENCE_RELEASE_LOST')
                return False
            self.state = 'RELEASED'
            return True
        except BaseException:
            self.state = 'RELEASE_INCOMPLETE'
            self.ledger.latch_fault(self.t,'NATIVE_WRITER_RELEASE_PROOF_INCOMPLETE_RETAIN_NO_RETRY')
            raise

    def request_final_retirement_thaw(self):
        """Final committed cut only: seal tool admission, thaw for native close.

        This is NOT20M->another search stage. Ledger stays COMMITTED_PARKED;
        final model admission stays closed. Immutable snapshot precedes any
        retirement writes. CLI/archive shutdown remains original OPS custody.
        """
        from snapshot import reference_path
        need(self.state == 'PARKED', 'WRITER_FENCE_RETIREMENT_FROM_FINAL_PARK_ONLY')
        self.cut.current({'COMMITTED_PARKED'})
        account = self.ledger.account(self.t)
        need(account['stage'] + 1 == len(json.loads(account['targets'])),
             'WRITER_FENCE_NO_RETIREMENT_THAW_AT_INTERMEDIATE_CUT')
        self._coverage()
        if self.whole_team is None:self._control_drained()
        need(all(d.frozen() and d.read('cgroup.freeze').strip() == '1' for d in self.domains),
             'WRITER_FENCE_PARK_LOST')
        reference = strict(reference_path(self.cut.cas,self.ledger.frontier(self.t)).read_bytes())
        snap = self.cut.cas.verify_snapshot(reference,expected=self.ledger.frontier(self.t))
        need(snap['pins'].get('native_writer_fence') == self.receipt['sha256'],
             'WRITER_FENCE_FINAL_RETIREMENT_ORIGINAL_SNAPSHOT')
        with self._locks():
            with self.ledger.tx():
                self.cut.current({'COMMITTED_PARKED'})
                row = self.ledger.db.execute('SELECT ref_sha FROM snapshots WHERE trajectory=? AND generation=?',
                    (self.t,self.cut.cut['generation'])).fetchone()
                need(row is not None and row[0] == reference['sha256'],
                     'WRITER_FENCE_FINAL_RETIREMENT_ORIGINAL_SNAPSHOT')
                self._coverage()
                for registration in self.owner._stage_registry:
                    registration.port.closing = True
                self.ledger.event(self.t,'NATIVE_WRITER_FINAL_RETIREMENT_THAW_REQUESTED',
                    {'cut_sha256':self.cut.cut_sha,'snapshot_sha256':reference['sha256'],
                     'domains_sha256':self.domains_sha,'model_admission_reopened':False})
                self.state = 'RETIREMENT_RELEASE_REQUESTED'
            try:
                for domain in self.domains:
                    domain.request(False)
            except BaseException:
                self.state = 'RETIREMENT_RELEASE_INCOMPLETE'
                self.ledger.latch_fault(self.t,'NATIVE_WRITER_RETIREMENT_THAW_INCOMPLETE_NO_RETRY')
                raise

    def poll_final_retirement_thaw(self):
        need(self.state in ('RETIREMENT_RELEASE_REQUESTED','RETIREMENT_RELEASED'),
             'WRITER_FENCE_ORIGINAL_RETIREMENT_HANDLE')
        try:
            # During retirement original SDKs may naturally exit; do not turn
            # their real exit into restart or require them alive indefinitely.
            for domain in self.domains:
                domain.current()
            if any(d.frozen() or d.read('cgroup.freeze').strip() != '0' for d in self.domains):
                need(self.state != 'RETIREMENT_RELEASED','WRITER_FENCE_RETIREMENT_THAW_LOST')
                return False
            self.state = 'RETIREMENT_RELEASED'
            return True
        except BaseException:
            self.state = 'RETIREMENT_RELEASE_INCOMPLETE'
            self.ledger.latch_fault(self.t,'NATIVE_WRITER_RETIREMENT_PROOF_INCOMPLETE_NO_RETRY')
            raise

    def next_cut(self):
        """Reuse exact original domains/processes for20M, never a new launch."""
        need(self.state == 'RELEASED' and self.owner.writer_fence is self,
             'WRITER_FENCE_NEXT_CUT_ORIGINAL_RELEASED_OWNER')
        f = self.ledger.frontier(self.t)
        need(f['state'] == 'RUNNING' and f['generation'] == self.cut.cut['generation'] + 1,
             'WRITER_FENCE_NEXT_CUT_SAME_LIVE_SUCCESSOR')
        self._coverage()
        need(all(not d.frozen() and d.read('cgroup.freeze').strip() == '0' for d in self.domains),
             'WRITER_FENCE_NEXT_CUT_ALL_DOMAINS_RUNNING')
        following = NativeWriterFence(self.owner,self.domains,
                                      expected_domains_sha256=self.domains_sha, whole_team=self.whole_team)
        self.owner.writer_fence = following
        return following

def verify_sealed_writer_proof(cas, snapshot):
    """Historical sealed artifact identity, NOT a fresh physical freezer proof."""
    value = sha(snapshot['pins']['native_writer_fence'])
    path = cas.objects / value
    need(path.stat().st_size <= 65536, 'WRITER_FENCE_SEALED_PROOF_BOUND')
    proof = strict(cas.resolve({'size':path.stat().st_size,'sha256':value}).read_bytes())
    fields = {'schema','cut','cut_sha256','roles','participants','domains_sha256',
              'participants_sha256','domain_bindings','kernel_frozen_all',
              'signals_cancel_restart_or_migration'}
    whole = type(proof) is dict and proof.get('schema') == 'agensh-native-whole-team-park-proof-v1'
    if whole: fields |= {'whole_team_inventory_sha256','backend_services'}
    need(type(proof) is dict and set(proof) == fields
         and proof['schema'] in ('agensh-native-writer-park-proof-v1','agensh-native-whole-team-park-proof-v1'),
         'WRITER_FENCE_SEALED_PROOF_SCHEMA')
    cut = proof['cut']
    need(type(cut) is dict and set(cut) == {'trajectory','generation','manifest_sha256',
         'target_tokens','admission_closed_sequence'} and digest(cut) == proof['cut_sha256']
         and type(cut['generation']) is int and cut['generation'] == snapshot['generation']
         and type(cut['target_tokens']) is int and cut['target_tokens'] == snapshot['target_tokens']
         and type(cut['admission_closed_sequence']) is int and cut['admission_closed_sequence'] > 0
         and cut['trajectory'] == snapshot['trajectory']
         and cut['manifest_sha256'] == snapshot['pins']['manifest'], 'WRITER_FENCE_SEALED_CUT_IDENTITY')
    roles = sorted(snapshot['roles'])
    expected = ['worker:'+r for r in roles] + ['sdk:'+r+':'+p for r in roles
                                             for p in ('gitea','mattermost','board')]
    if whole:
        sha(proof['whole_team_inventory_sha256'])
        backends = proof['backend_services']
        need(type(backends) is list and backends == sorted(set(backends))
             and {'service:gitea','service:mattermost'} < set(backends)
             and all(n in ('service:gitea','service:mattermost') or n.startswith('service:backend-')
                     for n in backends), 'WRITER_FENCE_SEALED_WHOLE_TEAM_BACKENDS')
        expected += backends
    need(proof['roles'] == roles and proof['participants'] == sorted(expected),
         'WRITER_FENCE_SEALED_ALL_WORKER_AND_SDK_ROSTER')
    domains = proof['domain_bindings']
    need(type(domains) is list and 1 <= len(domains) <= len(expected)
         and len(set(domains)) == len(domains)
         and digest(sorted(domains)) == sha(proof['domains_sha256']),
         'WRITER_FENCE_SEALED_DOMAIN_PINS')
    for item in domains:
        sha(item)
    sha(proof['participants_sha256'])
    need(proof['kernel_frozen_all'] is True and proof['signals_cancel_restart_or_migration'] is False,
         'WRITER_FENCE_SEALED_NO_CANCEL_OR_MIGRATION')
    return proof
