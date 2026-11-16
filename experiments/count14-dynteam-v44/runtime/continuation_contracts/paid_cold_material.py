"""Read-only protected metadata validation for a HELD paid-cold candidate.

No original snapshot capability upgrade, opaque SDK decoding, filesystem tree
walk, PKL loading, model request, process signal or boundary creation.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import stat
import uuid

SCHEMA = 'count14-paid-cold-held-candidate-handoff-v1'
PRODUCER_SHA256 = 'cd980946aa14ad3105372c65a1d76a04a1ba1cca6be5b93d376b4a173b839dee'
SESSION_SHA256 = 'c80000d66a4958a3c2d5854d188242806ef305aaee73d2be879571e31c3909dd'


class PaidColdWait(RuntimeError):
    """Fixed PUBLIC code only, never interpolate protected values."""


def need(ok, code):
    if not ok:
        raise PaidColdWait(code)


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(wire(value)).hexdigest()


def sha(value):
    need(type(value) is str and len(value) == 64 and
         all(c in '0123456789abcdef' for c in value), 'PAID_COLD_SHA256_BINDING')
    return value


def strict(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'PAID_COLD_NO_DUPLICATE_CONTROL_KEY')
            result[k] = v
        return result
    def nonfinite(_):
        raise PaidColdWait('PAID_COLD_FINITE_CONTROL_JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def stamp(s):
    return dict(device=s.st_dev, inode=s.st_ino, uid=s.st_uid, gid=s.st_gid,
                mode=stat.S_IMODE(s.st_mode))


def descriptor(path):
    """Metadata helper for trusted producers/OWN, not a seal or authorization."""
    path = Path(path)
    return dict(path=str(path), **stamp(path.lstat()))


def existing(row, *, directory=False, private=False):
    need(type(row) is dict and set(row) == {'path', 'device', 'inode', 'uid', 'gid', 'mode'},
         'PAID_COLD_EXACT_EXISTING_IDENTITY_DESCRIPTOR')
    need(type(row['path']) is str and all(type(row[k]) is int and row[k] >= 0
         for k in ('device','inode','uid','gid','mode')), 'PAID_COLD_TYPED_EXISTING_IDENTITY_DESCRIPTOR')
    p = Path(row['path'])
    s = p.lstat()
    need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and
         (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)) and
         stamp(s) == {k: row[k] for k in stamp(s)}, 'PAID_COLD_EXISTING_PATH_INODE_OWNER_MODE')
    if private:
        need(s.st_uid == os.geteuid() and stat.S_IMODE(s.st_mode) == (0o700 if directory else 0o600)
             and (directory or s.st_nlink == 1), 'PAID_COLD_ORIGINAL_PRIVATE_CONTROL_ONLY')
    return p


def private_read(path, pin=None, *, limit=16*1024*1024):
    p = Path(path)
    s = p.lstat()
    need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and
         stat.S_ISREG(s.st_mode) and s.st_uid == os.geteuid() and
         stat.S_IMODE(s.st_mode) == 0o600 and s.st_nlink == 1 and s.st_size <= limit,
         'PAID_COLD_PROTECTED_CONTROL_REGULAR_PRIVATE_BOUNDED')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        before = os.fstat(f.fileno())
        need((s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns) ==
             (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns),
             'PAID_COLD_CONTROL_OPEN_EXACT_INODE')
        raw = f.read(limit + 1)
        after = os.fstat(f.fileno())
    end = p.lstat()
    need(len(raw) <= limit and stamp(s) == stamp(after) == stamp(end) and
         (s.st_size, s.st_mtime_ns, s.st_ctime_ns) ==
         (after.st_size, after.st_mtime_ns, after.st_ctime_ns) ==
         (end.st_size, end.st_mtime_ns, end.st_ctime_ns), 'PAID_COLD_CONTROL_STABLE_READ')
    if pin is not None:
        need(hashlib.sha256(raw).hexdigest() == sha(pin), 'PAID_COLD_PROTECTED_CONTROL_PIN')
    return strict(raw), hashlib.sha256(raw).hexdigest()


def birth(row):
    from native_peer_registry import ProcessBirth
    fields = {'pid', 'start_ticks', 'boot_id', 'uid', 'gid', 'pid_namespace',
              'network_namespace', 'mount_namespace'}
    need(type(row) is dict and set(row) == fields and type(row['boot_id']) is str and
         all(type(row[k]) is int and row[k] >= (0 if k in ('uid', 'gid') else 1)
             for k in fields - {'boot_id'}), 'PAID_COLD_EXACT_ORIGINAL_PROCESS_BIRTH')
    try:
        need(str(uuid.UUID(row['boot_id'])) == row['boot_id'], 'PAID_COLD_BOOT_UUID')
    except ValueError:
        raise PaidColdWait('PAID_COLD_BOOT_UUID') from None
    return ProcessBirth(**row)


def nonexecuting(old, current):
    """Pilot handoff semantics, explicitly SAME BOOT/PIDNS phase-1 scope.

    Only exact /proc absence, Z/X or demonstrated PID reuse discharge the old
    identity. Permission/other errors propagate, never become absence.
    """
    from native_peer_registry import process_birth
    need(old.boot_id == current.boot_id and old.pid_namespace == current.pid_namespace,
         'PAID_COLD_SAME_BOOT_AND_PID_NAMESPACE_ONLY')
    try:
        raw = Path('/proc', str(old.pid), 'stat').read_bytes()
        fields = raw[raw.rfind(b')') + 2:].split()
        if fields[0] in (b'Z', b'X'):
            return True
        return process_birth(old.pid) != old
    except FileNotFoundError:
        return True


def verify_ended(handoff, current):
    from dataclasses import asdict
    old = birth(handoff['old_owner'])
    need(old != current and old.uid == current.uid and nonexecuting(old, current),
         'PAID_COLD_OLD_OWNER_STILL_EXECUTING_OR_NOT_SAME_UID')
    identities = handoff['children'] + handoff['publishers']
    need(type(handoff['children']) is list and type(handoff['publishers']) is list,
         'PAID_COLD_EXPLICIT_CHILD_AND_PUBLISHER_INVENTORIES')
    for row in identities:
        need(nonexecuting(birth(row), current), 'PAID_COLD_OLD_CHILD_OR_PUBLISHER_EXECUTING')
    need(type(handoff['old_epoch']) is int and handoff['old_epoch'] >= 1 and
         type(handoff['new_epoch']) is int and handoff['new_epoch'] == handoff['old_epoch'] + 1,
         'PAID_COLD_APPEND_ONLY_OWNER_EPOCH_SUCCESSOR')
    return old


@dataclass(frozen=True)
class ColdScope:
    contract: dict
    canonical_sha256: str
    qualification_only: bool = False

    @property
    def rows(self):
        return {r['trajectory_id']: r for r in self.contract['trajectories']}


def registered_scope(contract, canonical_sha256):
    need(digest(contract) == sha(canonical_sha256), 'PAID_COLD_ORIGINAL_CONTRACT_CANONICAL_PIN')
    if contract['mode'] == 'production':
        from formal_scope import validate_contract
        validate_contract(contract, canonical_sha256)
    elif contract['mode'] == 'smoke':
        from smoke_checkpoint_final_scope import SmokeCheckpointFinalScope
        SmokeCheckpointFinalScope(contract, contract_sha256=canonical_sha256)
    else:
        raise PaidColdWait('PAID_COLD_REGISTERED_FORMAL_OR_SMOKE_SCOPE_ONLY')
    return ColdScope(contract, canonical_sha256)


def verify_full_domain(owner_home, control, scope, old_owner):
    """Verify the complete protected append chain, reject any final INTENT."""
    log = existing(control['full_used_log_directory'], directory=True, private=True)
    need(log == owner_home / 'full-affinity-domain-control-v1', 'PAID_COLD_EXACT_ORIGINAL_FULL_DOMAIN_LOG')
    sequence = control['full_used_record_sequence']
    need(type(sequence) is int and sequence >= 1, 'PAID_COLD_NONEMPTY_FULL_DOMAIN_RECORD_CHAIN')
    need(set(p.name for p in log.iterdir()) == {str(i).zfill(12) + '.json' for i in range(1, sequence+1)},
         'PAID_COLD_NO_UNDECLARED_OR_PARTIAL_OR_NEWER_DOMAIN_RECORD')
    prior, values, pending = None, (), False
    expected_binding = None
    for i in range(1, sequence+1):
        row, row_sha = private_read(log / (str(i).zfill(12) + '.json'))
        need(row['schema'] == 'count14-formal-protected-full-used-domain-v1' and
             row['sequence'] == i and row['previous_record_sha256'] == prior,
             'PAID_COLD_ORIGINAL_FULL_DOMAIN_SEQUENCE_CHAIN')
        binding = row['source_binding']
        need(set(binding) == {'contract_sha256','cohort_sha256','owner_sha256','factory_parent_sha256',
                             'producer_source_sha256','session_source_sha256'} and
             binding['contract_sha256'] == scope.canonical_sha256 and
             binding['cohort_sha256'] == digest(sorted(scope.rows)) and
             binding['owner_sha256'] == digest(old_owner) and
             binding['producer_source_sha256'] == PRODUCER_SHA256 and
             binding['session_source_sha256'] == SESSION_SHA256 and
             binding['factory_parent_sha256'] == '68985fc4c4967ad6efd967a9b188c299bb6f2d690fdfa6cd10d548275436bc92',
             'PAID_COLD_FULL_DOMAIN_SOURCE_OWNER_COHORT_BINDING')
        need(expected_binding is None or binding == expected_binding, 'PAID_COLD_FULL_DOMAIN_BINDINGS_IMMUTABLE')
        expected_binding = binding
        raw_used = row['full_used']
        try:
            good = (type(raw_used) is list and raw_used == sorted(set(raw_used)) and
                    all(type(v) is str and str(uuid.UUID(v)) == v for v in raw_used))
        except (ValueError, TypeError, AttributeError):
            good = False
        need(good and row['full_used_sha256'] == digest(raw_used) and
             row['used_count'] == len(raw_used), 'PAID_COLD_COMPLETE_CANONICAL_USED_DOMAIN')
        new = tuple(raw_used)
        kind = row['kind']
        if i == 1:
            need(kind == 'INITIAL_EMPTY' and not new, 'PAID_COLD_DOMAIN_ORIGINAL_EMPTY_GENESIS')
        elif kind == 'BIND_INTENT':
            need(not pending and new == values, 'PAID_COLD_DOMAIN_SINGLE_PRECLAIM_INTENT')
            pending = True
        else:
            need(pending and kind in ('BIND_APPLIED', 'BIND_IDEMPOTENT', 'BIND_REFUSED_UNCHANGED') and
                 set(values) <= set(new) and len(new)-len(values) == int(kind == 'BIND_APPLIED'),
                 'PAID_COLD_DOMAIN_ORIGINAL_MONOTONIC_CLAIM_TERMINAL')
            pending = False
        values, prior = new, row_sha
    need(not pending and prior == control['full_used_record_sha256'],
         'PAID_COLD_PENDING_OR_FAILED_DOMAIN_INTENT_RETAIN_WAIT')
    return values, expected_binding


def verify_tracks(control, scope, used, binding):
    from dynteam_sessions import CohortSessions
    from native_layout import native_names
    from native_beta_layout import native_aliases
    rows = scope.rows
    need(set(control['tracks']) == set(rows), 'PAID_COLD_ALL_ORIGINAL_TRAJECTORIES_NOT_FINAL_ONLY')
    candidate = CohortSessions(list(rows), racing_trajectories=[t for t, r in rows.items() if r['arm'] == 'DYNTEAM_RACING'])
    active = set()
    for t, row in rows.items():
        track = control['tracks'][t]
        need(list(row['roles']) == list(candidate.tracks[t].roles), 'PAID_COLD_EXACT_ORIGINAL_ROLE_CATALOGUE')
        sidecar = track['full_used_sidecar']
        need(sidecar['schema'] == 'count14-formal-protected-full-used-domain-cut-v1' and
             sidecar['source_binding'] == binding and sidecar['record_sequence'] == control['full_used_record_sequence'] and
             sidecar['record_sha256'] == control['full_used_record_sha256'] and
             sidecar['full_used'] == list(used) and sidecar['full_used_sha256'] == digest(list(used)) and
             sidecar['used_count'] == len(used) and sidecar['shared_domain_history'] is True and
             sidecar['whole_paid_restore_implemented'] is False and
             sidecar['whole_cohort_frozen'] is False and sidecar['original_L1_cold_supported'] is False,
             'PAID_COLD_EXACT_PROTECTED_DOMAIN_OBSERVATION_NOT_GLOBAL_CUT')
        sha(sidecar['cut_binding']['cut_sha256'])
        need(sidecar['cut_binding']['trajectory_sha256'] == digest(t), 'PAID_COLD_PER_TRACK_CUT_IDENTITY')
        sha(sidecar['cut_binding']['membership_sha256'])
        affinity = track['session_affinity']
        need(set(affinity) <= set(row['roles']) and set(track['role_births']) <= set(row['roles']) and
             set(track['held_roles']) <= set(row['roles']), 'PAID_COLD_BOUND_LOGICAL_ROSTER')
        for role, value in affinity.items():
            need(type(value) is list and len(value) == 2 and value[1] in used and value[1] not in active and
                 track['role_births'].get(role) == sha(value[0]), 'PAID_COLD_ORIGINAL_LOGICAL_BIRTH_SID_AFFINITY')
            active.add(value[1])
        need(set(track['directories']) == set(row['roles']), 'PAID_COLD_ALL_ORIGINAL_ROLE_DIRECTORIES')
        profile, org = native_names(t)
        aliases = native_aliases(row['arm'])
        for role, directories in track['directories'].items():
            need(set(directories) == {'workspace', 'agent_state', 'archive_root', 'acp_root'},
                 'PAID_COLD_EXACT_ORIGINAL_ROLE_DIRECTORY_KINDS')
            account = org + '-' + aliases[role]['native_short']
            for kind, prefix in (('workspace', 'workspaces'), ('agent_state', 'agents'),
                                 ('archive_root', 'trajectories'), ('acp_root', 'acp')):
                path = existing(directories[kind], directory=True)
                need(path == Path(row['root'])/'native-data'/profile/prefix/account,
                     'PAID_COLD_ORIGINAL_LAYOUT_PATH_NO_SUBSTITUTE_ROOT')
    return candidate
