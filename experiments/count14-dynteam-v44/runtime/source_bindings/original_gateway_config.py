"""Approved six never-started shells: real config proof, normal rm once.

No create/start, forced stop, volume/image/filesystem deletion or daemon edit.
The caller retains this exact job/Popen and supplies full current cold custody
and zero-request/held guards outside scientific locks. Failures never retry.
"""
from pathlib import Path
import json
import os
import stat
import subprocess
import time

PLAN_SHA = '1e74e0b2fa419253335d7fb070e08e28c03660590506c43d37c6d09d28e2cf41'
SIX = (
    ('tester-00', 'agent', 'd13a57a3406b6297dd406401e0f8e697bcc8f9c19e7970b5e200acf54a5ea47c',
     'sha256:db1d30832d9eda18256c6d22719053940be56c9a930f63be5eb5aa722a368ef7', 128),
    ('tester-00', 'router', '793a1565db5ca5737b85593821fc994f8c0e731b78d0e656119054592f8af515',
     'sha256:f7750b36ff9e664ffc1460db351b01967b377523b636a52f5c8069e05626c5cb', 0),
    ('checker-00', 'agent', '828f57a7947244603e531d922870211881b20d7af0aa2ffb918374bbb68758a6',
     'sha256:db1d30832d9eda18256c6d22719053940be56c9a930f63be5eb5aa722a368ef7', 128),
    ('checker-00', 'router', 'ec0f5c4a9d3c9af19e511f78ab0d2dbb3a2d64d2ba14907310825ceb19e3cd42',
     'sha256:f7750b36ff9e664ffc1460db351b01967b377523b636a52f5c8069e05626c5cb', 0),
    ('worker-00', 'agent', '3729b4bc577219cab08dc70dbfcc015c3679ec10937270ac53d00005f94f7f3e',
     'sha256:db1d30832d9eda18256c6d22719053940be56c9a930f63be5eb5aa722a368ef7', 128),
    ('worker-00', 'router', '8412686b1933232396ea03080bcf11e0c0522d07830262744d4cda527139a0a7',
     'sha256:f7750b36ff9e664ffc1460db351b01967b377523b636a52f5c8069e05626c5cb', 0),
)
FORMAT = ('{"id":{{json .Id}},"image":{{json .Image}},"status":{{json .State.Status}},'
          '"pid":{{json .State.Pid}},"running":{{json .State.Running}},'
          '"paused":{{json .State.Paused}},"restarting":{{json .State.Restarting}},'
          '"dead":{{json .State.Dead}},"exit_code":{{json .State.ExitCode}}}')
_SEAL = object()
_CONFIGS = {}


def need(condition, code):
    if not condition:
        raise ValueError(code)


def file_identity(path):
    path = Path(path); s = path.lstat()
    need(path.resolve() == path and not path.is_symlink() and stat.S_ISREG(s.st_mode) and
         s.st_uid == os.geteuid() and s.st_nlink == 1 and stat.S_IMODE(s.st_mode) == 0o400,
         'CURRENT240_NEW_GATEWAY_LAYER_EXACT_FILE_IDENTITY')
    return (s.st_dev, s.st_ino, s.st_uid, s.st_gid, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def held(core, trajectory):
    from original_relay_core import OriginalRelayCore
    need(type(core) is OriginalRelayCore and not core.closed and not core.scientific_activation_qualified and
         set(core.gate.startup_held) == set(core.rows) and trajectory in core.rows and
         core.rows[trajectory]['arm'] == 'DYNTEAM' and core.contract['mode'] == 'smoke' and
         not core.ledger.mutex._is_owned(), 'CURRENT240_ONLY_SAME_GENUINE_HELD_SMOKE_COLD_CORE')
    with core.ledger.mutex:
        for table in ('requests', 'unknown_charges', 'aux_scopes', 'aux_permits', 'snapshots', 'acks', 'unknown_stops'):
            need(core.ledger.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] == 0,
                 'CURRENT240_REMOVE_ONLY_ZERO_SCIENTIFIC_PREFIX')
        need(core.ledger.db.execute('SELECT paused FROM model_control WHERE singleton=1').fetchone()[0] == 1 and
             not core.ledger.memory_faults,
             'CURRENT240_NEW_COLD_RAM_AND_MODELS_PAUSED_NO_HOT_FAULT_CLEAR')
    registry = core.native_containers
    need(not registry.records and not registry.boot_plans and not core.peers._peers,
         'CURRENT240_CREATED_SHELLS_HAVE_NO_ADMITTED_PEERS_OR_BOOT_PLANS')


class ConfigMergeProof:
    __slots__ = ('_seal',)
    def __init__(self):
        raise ValueError('CURRENT240_CONFIG_PROOF_ONLY_REAL_CONFIG_COMPARISON')


def verify_actual_compose(core, trajectory, *, fresh_guard):
    """Two normal read-only config invocations; raw output remains in RAM."""
    held(core, trajectory)
    need(callable(fresh_guard) and fresh_guard() is True,
         'CURRENT240_FULL_COLD_FRESH_GUARD_BEFORE_CONFIG')
    host = core.native_host_environment['trajectories'][trajectory]
    binding = host['current240_gateway_overlay']
    network = core.native_networks[trajectory]
    network.checked(contract=core.contract, row=core.rows[trajectory], qualification_only=core.qualification_only)
    need(core.servers[trajectory].server_address[0] == network.gateway and
         host['compose'] == binding['selected_compose'],
         'CURRENT240_CONFIG_SAME_ORIGINAL_RELAY_AND_NEW_OVERLAY_COMMAND')
    identity = file_identity(binding['path'])
    outputs = []
    docker = core.native_containers.docker
    for command in (binding['original_compose'], binding['selected_compose']):
        need(tuple(command[:3]) == tuple(docker.argv()) and command.count('compose') == 1,
             'CURRENT240_CONFIG_ONLY_ORIGINAL_PRIVATE_DOCKER_ROUTE')
        result = subprocess.run([*command, 'config', '--format', 'json'],
            cwd=host['project_root'], env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
                                        'HOME': str(core.pre_request_control_home)},
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
        need(result.returncode == 0 and 0 < len(result.stdout) <= 8 * 1024**2,
             'CURRENT240_ACTUAL_CONFIG_REFUSED_BEFORE_ANY_RM')
        value = json.loads(result.stdout)
        need(type(value) is dict and type(value.get('services')) is dict,
             'CURRENT240_ACTUAL_CONFIG_FIXED_OBJECT_SHAPE')
        outputs.append(value)
    before, after = outputs
    from native_beta_layout import native_aliases
    aliases = native_aliases(core.rows[trajectory]['arm'])
    names = {a[k] for a in aliases.values() for k in ('agent_service', 'router_service')}
    need(set(before) == set(after) and set(before['services']) == set(after['services']) and
         names <= set(before['services']), 'CURRENT240_CONFIG_SERVICE_OR_TOPLEVEL_SET_CHANGED')
    for name in before['services']:
        a, b = before['services'][name], after['services'][name]
        need(type(a) is dict and type(b) is dict, 'CURRENT240_CONFIG_SERVICE_OBJECTS')
        if name in names:
            old = a.pop('extra_hosts', None); new = b.pop('extra_hosts', None)
            need(old in (['host.docker.internal=host-gateway'], ['host.docker.internal:host-gateway']) and
                 new == ['host.docker.internal=' + network.gateway],
                 'CURRENT240_CONFIG_MUST_REMOVE_SENTINEL_AND_KEEP_EXACT_ONE_GATEWAY_ALIAS')
        need(a == b, 'CURRENT240_CONFIG_ANY_OTHER_RUNTIME_SETTING_CHANGED')
    need(before == after and file_identity(binding['path']) == identity and fresh_guard() is True,
         'CURRENT240_CONFIG_OTHER_FIELDS_OR_FRESH_IDENTITY_CHANGED')
    # Never hash, persist or export expanded config, environment or commands.
    del before, after, outputs, value, result
    proof = object.__new__(ConfigMergeProof); proof._seal = _SEAL
    _CONFIGS[id(proof)] = dict(proof=proof, core=core, trajectory=trajectory,
        binding=binding, identity=identity, at=time.monotonic_ns(), network=network)
    return proof


def check_config(proof, core, trajectory):
    need(type(proof) is ConfigMergeProof and proof._seal is _SEAL and id(proof) in _CONFIGS,
         'CURRENT240_GENUINE_REGISTERED_ACTUAL_CONFIG_PROOF_REQUIRED')
    record = _CONFIGS[id(proof)]
    host = core.native_host_environment['trajectories'][trajectory]
    need(record['proof'] is proof and record['core'] is core and record['trajectory'] == trajectory and
         host['current240_gateway_overlay'] is record['binding'] and
         host['compose'] == record['binding']['selected_compose'] and
         core.native_networks[trajectory] is record['network'] and
         file_identity(record['binding']['path']) == record['identity'] and
         0 <= time.monotonic_ns() - record['at'] <= 3600 * 10**9,
         'CURRENT240_CONFIG_PROOF_SAME_NEW_CORE_FILE_NETWORK_AND_FRESH60MIN_WITH_EACH_ACTION_RECHECK')
    held(core, trajectory)
    return True


class CreatedSixRemoval:
    def __init__(self, core, trajectory, *, config_proof, approved_plan_sha256, fresh_guard, save_receipt):
        from native_docker_scope import ScopedDocker
        from native_peer_registry import process_birth
        need(approved_plan_sha256 == PLAN_SHA and callable(fresh_guard) and callable(save_receipt),
             'CURRENT240_EXACT_APPROVED_SIX_SCOPE_AND_ORIGINAL_RECEIPT_WRITER')
        held(core, trajectory)
        need(type(core.native_containers.docker) is ScopedDocker,
             'CURRENT240_ONLY_ORIGINAL_SCOPED_DOCKER_NORMAL_MUTATIONS')
        self.core, self.t, self.docker = core, trajectory, core.native_containers.docker
        self.proof, self.guard, self.save = config_proof, fresh_guard, save_receipt
        self.birth = process_birth(os.getpid())
        self.index, self.sequence, self.child = 0, 0, None
        self.phase, self.failure_type, self.warning120 = 'BEFORE', None, False
        self.started_ns = None
        check_config(self.proof, self.core, self.t)
        need(self.guard() is True, 'CURRENT240_FRESH_SERIAL_CUSTODY_BEFORE_SIX_SNAPSHOT')
        rows = [self.inspect_one(i) for i in range(len(SIX))]
        self.receipt('BEFORE_PUBLIC_SIX_CREATED_AND_ORIGINAL_FAILURE_PRESERVED', rows=rows,
                     approved_plan_sha256=PLAN_SHA)

    @property
    def remaining(self):
        return {r[2] for r in SIX[self.index:]}

    def receipt(self, kind, **metadata):
        self.sequence += 1
        self.save('CREATED_SIX_' + str(self.sequence).zfill(4) + '_' + kind + '_PUBLIC.json',
            dict(schema='count14-current240-exact-created-six-normal-removal-v1', kind=kind,
                 sequence=self.sequence, owner_pid=self.birth.pid, owner_start_ticks=self.birth.start_ticks,
                 index=self.index, phase=self.phase, at_mono_ns=time.monotonic_ns(),
                 requests_replayed=0, fees_changed=0, files_volumes_images_or_roots_deleted=False, **metadata))

    def inspect_one(self, index):
        from native_docker_scope import scope_labels
        role, component, cid, image, exit_code = SIX[index]
        labels = scope_labels(self.core.contract, self.core.rows[self.t], role, component)
        need(self.docker.list_scope_ids(labels) == [cid],
             'CURRENT240_ONLY_ONE_ORIGINAL_EXACT_ROLE_COMPONENT_SCOPE')
        row = self.docker._project('inspect', '--type', 'container', '--format', FORMAT, cid)
        expected = dict(id=cid, image=image, status='created', pid=0, running=False,
                        paused=False, restarting=False, dead=False, exit_code=exit_code)
        need(row == expected and set(row) == set(expected) and
             all(type(row[k]) is type(v) for k, v in expected.items()),
             'CURRENT240_ONLY_EXACT_NEVER_STARTED_CREATED_PID0_IMAGE_SCOPE')
        return dict(role=role, component=component, **row)

    def step(self):
        if self.phase == 'DONE' or self.failure_type is not None:
            return self.phase
        try:
            return self._step()
        except Exception as error:
            self.failure_type = type(error).__name__
            self.phase = 'PARTIAL_RETAINED_NO_RETRY'
            self.receipt('FAILURE', exception_type=self.failure_type)
            return self.phase

    def _step(self):
        from native_peer_registry import process_birth
        need(process_birth(os.getpid()) == self.birth and self.guard() is True,
             'CURRENT240_SAME_NEW_OWNER_AND_FRESH_CUSTODY_BEFORE_EACH_CONSUMPTION')
        held(self.core, self.t)
        if self.child is not None:
            code = self.child.poll()
            if code is None:
                if time.monotonic_ns() - self.started_ns >= 120 * 10**9 and not self.warning120:
                    self.warning120 = True
                    self.receipt('OBSERVATION120_SAME_CHILD_NO_SIGNAL', child_pid=self.child.pid)
                return self.phase
            self.receipt('NORMAL_RM_CHILD_EXIT', actual_exit_code=code, child_pid=self.child.pid)
            need(code == 0, 'CURRENT240_NORMAL_RM_FAILED_NO_AUTORETRY')
            cid = SIX[self.index][2]
            need(not self.docker.exists(cid), 'CURRENT240_OLD_CID_NOT_PHYSICALLY_ABSENT')
            self.receipt('EXACT_OLD_CID_PHYSICALLY_ABSENT', container_id=cid)
            self.child = None
            self.index += 1
            if self.index == len(SIX):
                need(all(not self.docker.exists(row[2]) for row in SIX),
                     'CURRENT240_ALL_SIX_OLD_SHELLS_ABSENT_BEFORE_NEW_CREATE')
                self.phase = 'DONE'
                self.receipt('DONE_EXACT_SIX_NORMAL_RM_NO_REPLACEMENTS_STARTED', containers=6)
                return self.phase
        check_config(self.proof, self.core, self.t)
        row = self.inspect_one(self.index)
        # Preserve a second exact before receipt and durable action intent.
        self.phase = 'NORMAL_RM_PENDING'
        self.receipt('NORMAL_RM_ONCE_INTENT', row=row)
        self.child = self.docker.mutate_once('REMOVE_STOPPED', row['id'])
        self.started_ns = time.monotonic_ns()
        self.receipt('NORMAL_RM_STARTED', container_id=row['id'], child_pid=self.child.pid)
        return self.phase
