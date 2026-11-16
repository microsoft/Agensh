"""Append-only writer adoption for the EXACT original full-used producer.

Component custody only: no whole-owner boundary authority, quarantine removal,
gate release, process signal, fresh producer constructor, ledger/SDK/task read.
Original origin binding/history and original bind/claim/I/O bodies stay intact.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
from types import CodeType
import copy
import fcntl
import hashlib
import importlib
import json
import os
import re
import stat
import threading
import uuid

from formal_full_used_domain import FullUsedDomainProducer, digest, wire
from dynteam_sessions import AffinityDomain, CohortSessions, DynamicSessions
from native_peer_registry import ProcessBirth, process_birth
from native_metadata_publisher import NativeMetadataPublisher
from native_session_control import NativeSessionInbox, NativeSessionControl, SessionTicket, checked

PINS = dict(formal_full_used_domain='cd980946aa14ad3105372c65a1d76a04a1ba1cca6be5b93d376b4a173b839dee',
    dynteam_sessions='c80000d66a4958a3c2d5854d188242806ef305aaee73d2be879571e31c3909dd',
    native_peer_registry='0986b61a7c71b6745442b9c71dfc67d79eebf960a50523ea1e2b5ee0f37d019d',
    native_metadata_publisher='a0e2fe4a193a25333424c7c4c723714bb1f2aa6b7b352c811421f59ffa9e4bdb',
    native_session_control='cba05b39fb3231f5791ba7421bf2b6a8487d081df6016885ab7f291b326cd370')
PARENT = '68985fc4c4967ad6efd967a9b188c299bb6f2d690fdfa6cd10d548275436bc92'
HSCHEMA = 'count14-full-used-writer-handoff-v1'
ESCHEMA = 'count14-full-used-writer-epoch-v1'
NUMBER = re.compile(r'[0-9]{12}\.json\Z')
SEAL = re.compile(r'WRITER_HANDOFF_([0-9]{12})\.json\Z')
EPOCH = re.compile(r'WRITER_EPOCH_([0-9]{12})\.json\Z')
RETAINED_ADOPTION = None
_TOKEN = object()


class AdoptionWait(RuntimeError):
    """Fixed PUBLIC code only; no protected SID/control interpolation."""


def need(ok, code):
    if not ok:
        raise AdoptionWait(code)


def sha(raw): return hashlib.sha256(raw).hexdigest()


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'PAID_ADOPT_DUPLICATE_CONTROL_KEY')
            result[key] = value
        return result
    def bad(_): raise AdoptionWait('PAID_ADOPT_FINITE_CONTROL_JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, uid=s.st_uid, gid=s.st_gid, mode=stat.S_IMODE(s.st_mode))


def stable(s): return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def private_read(path, pin=None, *, dir_fd=None):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink(),
         'PAID_ADOPT_CANONICAL_PROTECTED_CONTROL')
    before = path.lstat()
    fd = os.open(path.name if dir_fd is not None else path,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    with os.fdopen(fd, 'rb') as f:
        opened = os.fstat(f.fileno())
        need(stat.S_ISREG(opened.st_mode) and opened.st_uid == os.geteuid() and
             stat.S_IMODE(opened.st_mode) == 0o600 and opened.st_nlink == 1 and
             0 < opened.st_size <= 16 * 1024 * 1024 and stable(before) == stable(opened),
             'PAID_ADOPT_PRIVATE_SINGLE_LINK_STABLE_CONTROL')
        raw = f.read(16 * 1024 * 1024 + 1)
        after = os.fstat(f.fileno())
    need(stable(before) == stable(after) == stable(path.lstat()) and len(raw) == before.st_size,
         'PAID_ADOPT_NO_CONTROL_REPLACEMENT_OR_PARTIAL_READ')
    need(pin is None or sha(raw) == pin, 'PAID_ADOPT_PROTECTED_CONTROL_PIN')
    return strict(raw), sha(raw)


def verify_sources():
    for name, pin in PINS.items():
        module = importlib.import_module(name); p = Path(module.__file__)
        need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and sha(p.read_bytes()) == pin,
             'PAID_ADOPT_EXACT_ORIGINAL_SOURCE_PINS')
    module = importlib.import_module('formal_full_used_domain')
    root = compile(Path(module.__file__).read_bytes(), module.__file__, 'exec', dont_inherit=True)
    cls = next(c for c in root.co_consts if isinstance(c, CodeType) and c.co_name == 'FullUsedDomainProducer')
    methods = {c.co_name: c for c in cls.co_consts if isinstance(c, CodeType)}
    for name in ('__init__', '_bind', '_append', '_install_hooks', '_check_hooks', '_write_new',
                 '_io_guard', '_outside_locks', '_domain_values', '_require_saved', '_operation'):
        actual = getattr(FullUsedDomainProducer, name)
        actual = getattr(actual, '__wrapped__', actual)
        need(actual.__code__ == methods[name] and actual.__globals__ is vars(module),
             'PAID_ADOPT_ORIGINAL_PRODUCER_METHOD_CODE_AND_NAMESPACE')
    for module_name, class_name, names in (
            ('dynteam_sessions', 'AffinityDomain', ('claim',)),
            ('dynteam_sessions', 'DynamicSessions', ('bind', 'end')),
            ('native_metadata_publisher', 'NativeMetadataPublisher', ('poll_once',)),
            ('native_session_control', 'NativeSessionInbox', ('receive', 'drain', 'resolve')),
            ('native_session_control', 'NativeSessionControl', ('start', 'close'))):
        source = importlib.import_module(module_name)
        compiled = compile(Path(source.__file__).read_bytes(), source.__file__, 'exec', dont_inherit=True)
        class_code = next(c for c in compiled.co_consts if isinstance(c, CodeType) and c.co_name == class_name)
        codes = {c.co_name: c for c in class_code.co_consts if isinstance(c, CodeType)}
        for name in names:
            actual = getattr(getattr(source, class_name), name)
            need(actual.__code__ == codes[name] and actual.__globals__ is vars(source),
                 'PAID_ADOPT_ORIGINAL_SESSION_PUBLISHER_INBOX_CONTROL_METHODS')
    return dict(PINS)


def birth(value):
    fields = {'pid', 'start_ticks', 'boot_id', 'uid', 'gid', 'pid_namespace', 'network_namespace', 'mount_namespace'}
    need(type(value) is dict and set(value) == fields and type(value['boot_id']) is str and
         all(type(value[k]) is int and value[k] >= (0 if k in ('uid', 'gid') else 1)
             for k in fields - {'boot_id'}), 'PAID_ADOPT_EXACT_PROCESS_BIRTH')
    need(str(uuid.UUID(value['boot_id'])) == value['boot_id'], 'PAID_ADOPT_BOOT_UUID')
    return ProcessBirth(**value)


def nonexecuting(old, current):
    """Original pilot semantics: absence/Z/X/reuse, NOT an exit0 assertion."""
    need(type(old) is ProcessBirth and type(current) is ProcessBirth and old != current and
         old.uid == current.uid and old.boot_id == current.boot_id and
         old.pid_namespace == current.pid_namespace, 'PAID_ADOPT_SAME_BOOT_NAMESPACE_UID_NEW_BIRTH')
    try:
        raw = Path('/proc', str(old.pid), 'stat').read_bytes()
        fields = raw[raw.rfind(b')') + 2:].split()
        return fields[0] in (b'Z', b'X') or process_birth(old.pid) != old
    except FileNotFoundError:
        return True  # PermissionError/other errors are NOT absence.


def affinity(sessions):
    result = {}
    for name, track in sessions.tracks.items():
        with track._lock:
            result[name] = {r: list(v) for (t, r), v in sorted(track._current.items()) if t == name}
            need(len(result[name]) == len(track._current), 'PAID_ADOPT_NO_FOREIGN_TRACK_MAPPING')
    return result


def inbox_state(publisher):
    """Only native-affinity control tickets; NEVER scientific collaboration."""
    inbox = publisher.inbox
    need(type(inbox) is NativeSessionInbox, 'PAID_ADOPT_ORIGINAL_NATIVE_AFFINITY_INBOX')
    with inbox.lock:
        pending = list(inbox.pending)
        need(len({id(t) for t in pending}) == len(pending) and
             all(inbox.tickets.get(t.key) is t for t in pending), 'PAID_ADOPT_EXACT_PENDING_TICKET_IDENTITIES')
        tickets = {}
        for key, ticket in inbox.tickets.items():
            need(type(ticket) is SessionTicket and ticket.key == key and
                 checked(dict(ticket.envelope)) == ticket.envelope and
                 sha(json.dumps(ticket.envelope, sort_keys=True, separators=(',', ':')).encode()) == key and
                 type(ticket.peer) is tuple and len(ticket.peer) == 3 and
                 all(type(v) is int and v >= 0 for v in ticket.peer) and
                 type(ticket.complete) is threading.Event and
                 (ticket.accepted is None or type(ticket.accepted) is bool) and
                 ticket.complete.is_set() == (ticket.accepted is not None),
                 'PAID_ADOPT_ORIGINAL_NATIVE_TICKET_KEY_PEER_ONCE_STATE')
            tickets[key] = dict(envelope=copy.deepcopy(ticket.envelope), peer=list(ticket.peer), accepted=ticket.accepted)
        unresolved = {key for key, t in inbox.tickets.items() if t.accepted is None}
        need(set(t.key for t in pending) == unresolved and inbox.unresolved == len(unresolved),
             'PAID_ADOPT_DOMAIN_PUBLISHER_DRAINED_BUT_UNRESOLVED_WRITE_WINDOW')
        return dict(timeout=inbox.timeout, maximum_pending=inbox.maximum_pending,
            unresolved=inbox.unresolved, pending=[t.key for t in pending], tickets=tickets)


def closed_native_ingress(control, publisher):
    """Observe an EXISTING normal close; never stop a live service here."""
    import native_session_control as source
    need(type(control) is NativeSessionControl and type(control.server) is source._Server and
         getattr(control.server.receiver, '__self__', None) is publisher.inbox and
         getattr(control.server.receiver, '__func__', None) is NativeSessionInbox.receive and
         control.server.socket.fileno() == -1 and not control.thread.is_alive(),
         'PAID_ADOPT_EXISTING_ORIGINAL_NATIVE_AFFINITY_INGRESS_CLOSED_NOT_CALLER_BOOL')
    with control.server.control_slots._cond:
        need(control.server.control_slots._value == 16,
             'PAID_ADOPT_OLD_NATIVE_RECEIPT_HANDLER_CAN_STILL_PUBLISH_METADATA')
    s = control.path.lstat()
    need(stat.S_ISSOCK(s.st_mode) and control.path.resolve() == control.path,
         'PAID_ADOPT_ORIGINAL_RETAINED_CONTROL_SOCKET_INODE')
    return dict(path=str(control.path), **identity(s))


def validate_inbox_state(state):
    need(type(state) is dict and set(state) == {'timeout', 'maximum_pending', 'unresolved', 'pending', 'tickets'} and
         type(state['timeout']) in (int, float) and 0 < state['timeout'] <= 2.5 and
         type(state['maximum_pending']) is int and state['maximum_pending'] >= 1 and
         type(state['unresolved']) is int and state['unresolved'] >= 0 and
         type(state['tickets']) is dict and type(state['pending']) is list and
         len(set(state['pending'])) == len(state['pending']), 'PAID_ADOPT_TYPED_NATIVE_INBOX_CONTROL')
    unresolved = set()
    for key, item in state['tickets'].items():
        need(type(item) is dict and set(item) == {'envelope', 'peer', 'accepted'} and
             type(item['peer']) is list and len(item['peer']) == 3 and
             all(type(v) is int and v >= 0 for v in item['peer']) and
             (item['accepted'] is None or type(item['accepted']) is bool) and
             checked(dict(item['envelope'])) == item['envelope'] and
             sha(json.dumps(item['envelope'], sort_keys=True, separators=(',', ':')).encode()) == key,
             'PAID_ADOPT_NATIVE_METADATA_KEY_ENVELOPE_PEER_ONCE_BINDING')
        if item['accepted'] is None: unresolved.add(key)
    need(unresolved == set(state['pending']) and len(unresolved) == state['unresolved'] and
         len(unresolved) <= state['maximum_pending'], 'PAID_ADOPT_NATIVE_PENDING_NOT_DROPPED_OR_FABRICATED_ZERO')


def check_components(sessions, science_mutex, publisher):
    need(type(sessions) is CohortSessions and sessions.tracks and type(science_mutex) is type(threading.RLock()) and
         not science_mutex._is_owned() and type(publisher) is NativeMetadataPublisher and
         publisher.sessions is sessions and publisher.poll_once.__func__ is NativeMetadataPublisher.poll_once,
         'PAID_ADOPT_EXACT_SESSIONS_RLOCK_PUBLISHER_NOT_UNHYDRATED_SHELL')
    tracks = dict(sessions.tracks); domain = next(iter(tracks.values())).domain
    need(type(domain) is AffinityDomain and type(domain.used) is set and
         all(type(t) is DynamicSessions and t.domain is domain and type(t._current) is dict and
             type(t._lock) is type(threading.Lock()) and not t._lock.locked() for t in tracks.values()) and
         not domain.lock.locked() and getattr(sessions._request_scope, 'value', None) is None,
         'PAID_ADOPT_ORIGINAL_SHARED_DOMAIN_NO_ACTIVE_REQUEST_SCOPE_OR_LOCK')
    if publisher.qualification_only:
        need(all(t.startswith('OWN-') for t in tracks), 'PAID_ADOPT_OWN_PUBLISHER_NEVER_REAL_TRAJECTORIES')
    return tracks, domain


def check_cut(path, pin, directory, directory_identity, binding, sequence, record_sha, values, writer):
    row, actual = private_read(path, pin)
    need(Path(path).parent == directory.parent and row['schema'] == 'count14-paid-cold-held-control-candidate-v1' and
         row['whole_cohort_cut_qualified'] is False and row['old_owner_sha256'] == digest(writer) and
         row['contract_sha256'] == binding['contract_sha256'] and
         row['full_used_log_directory'] == dict(path=str(directory), **directory_identity) and
         row['full_used_record_sequence'] == sequence and row['full_used_record_sha256'] == record_sha and
         digest(sorted(row['tracks'])) == binding['cohort_sha256'],
         'PAID_ADOPT_EXISTING_COMPLETE_PROTECTED_SOURCE_CUT_BINDING_NOT_WHOLE_COLD_AUTHORITY')
    mappings = {}
    active = set()
    for t, track in row['tracks'].items():
        sidecar = track['full_used_sidecar']
        need(sidecar['schema'] == 'count14-formal-protected-full-used-domain-cut-v1' and
             sidecar['source_binding'] == binding and sidecar['record_sequence'] == sequence and
             sidecar['record_sha256'] == record_sha and sidecar['full_used'] == list(values) and
             sidecar['full_used_sha256'] == digest(list(values)) and sidecar['used_count'] == len(values) and
             sidecar['shared_domain_history'] is True and sidecar['whole_cohort_frozen'] is False and
             sidecar['whole_paid_restore_implemented'] is False and sidecar['original_L1_cold_supported'] is False and
             sidecar['cut_binding']['trajectory_sha256'] == digest(t), 'PAID_ADOPT_ALL_ORIGINAL_PER_TRACK_CUT_OBSERVATIONS')
        for key in ('cut_sha256', 'membership_sha256'):
            need(type(sidecar['cut_binding'][key]) is str and re.fullmatch('[0-9a-f]{64}', sidecar['cut_binding'][key]),
                 'PAID_ADOPT_TYPED_ORIGINAL_CUT_HASHES')
        mapping = track['session_affinity']
        need(type(mapping) is dict, 'PAID_ADOPT_ORIGINAL_SESSION_AFFINITY_CONTROL')
        for role, value in mapping.items():
            need(type(role) is str and type(value) is list and len(value) == 2 and
                 type(value[0]) is str and re.fullmatch('[0-9a-f]{64}', value[0]) and
                 value[1] in values and value[1] not in active, 'PAID_ADOPT_EXACT_UNIQUE_CURRENT_SID_FROM_HISTORY')
            active.add(value[1])
        mappings[t] = mapping
    return mappings, actual


@dataclass(frozen=True, init=False)
class VerifiedHistory:
    """Produced only by the actual private FD/chain verifier, never caller bool."""
    def __init__(self, token, **fields):
        need(token is _TOKEN, 'PAID_ADOPT_VERIFIED_HISTORY_NOT_CALLER_PROOF')
        for key, value in fields.items(): object.__setattr__(self, key, value)


def verify_history(directory, fd):
    directory = Path(directory); opened = os.fstat(fd); current = directory.lstat()
    need(directory.is_absolute() and directory.resolve() == directory and not directory.is_symlink() and
         stat.S_ISDIR(opened.st_mode) and identity(opened) == identity(current) and
         opened.st_uid == os.geteuid() and stat.S_IMODE(opened.st_mode) == 0o700,
         'PAID_ADOPT_EXACT_ORIGINAL_PRIVATE_DIRECTORY_FD')
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # real kernel custody, not caller true
    names = os.listdir(fd); numbers = sorted(n for n in names if NUMBER.fullmatch(n))
    seals = {int(SEAL.fullmatch(n).group(1)): n for n in names if SEAL.fullmatch(n)}
    epochs = {int(EPOCH.fullmatch(n).group(1)): n for n in names if EPOCH.fullmatch(n)}
    need(len(names) == len(numbers) + len(seals) + len(epochs) and numbers and
         numbers == [str(i).zfill(12) + '.json' for i in range(1, len(numbers) + 1)],
         'PAID_ADOPT_NO_UNDECLARED_PARTIAL_GAPPED_OR_FOREIGN_HISTORY')
    binding, prior, values, pending, tips = None, None, (), False, {}
    for i, name in enumerate(numbers, 1):
        row, pin = private_read(directory / name, dir_fd=fd)
        need(set(row) == {'schema', 'sequence', 'kind', 'previous_record_sha256', 'source_binding', 'full_used',
                         'full_used_sha256', 'used_count', 'whole_paid_restore_implemented'} and
             row['schema'] == 'count14-formal-protected-full-used-domain-v1' and row['sequence'] == i and
             row['previous_record_sha256'] == prior and row['whole_paid_restore_implemented'] is False,
             'PAID_ADOPT_ORIGINAL_NUMERIC_HISTORY_SCHEMA_AND_CHAIN')
        b = row['source_binding']
        need(type(b) is dict and set(b) == {'contract_sha256', 'cohort_sha256', 'owner_sha256',
             'factory_parent_sha256', 'producer_source_sha256', 'session_source_sha256'} and
             all(type(v) is str and re.fullmatch('[0-9a-f]{64}', v) for v in b.values()) and
             b['factory_parent_sha256'] == PARENT and b['producer_source_sha256'] == PINS['formal_full_used_domain'] and
             b['session_source_sha256'] == PINS['dynteam_sessions'] and (binding is None or b == binding),
             'PAID_ADOPT_IMMUTABLE_ORIGIN_SOURCE_BINDING_NEVER_NEW_OWNER_REWRITE')
        binding = b; new = row['full_used']
        need(type(new) is list and all(type(v) is str and str(uuid.UUID(v)) == v for v in new) and
             new == sorted(set(new)) and row['full_used_sha256'] == digest(new) and row['used_count'] == len(new),
             'PAID_ADOPT_CANONICAL_COMPLETE_FULL_USED_VALUES')
        new = tuple(new); kind = row['kind']
        if i == 1:
            need(kind == 'INITIAL_EMPTY' and not new, 'PAID_ADOPT_ORIGINAL_GENESIS_ONLY_ONCE')
        elif kind == 'BIND_INTENT':
            need(not pending and new == values, 'PAID_ADOPT_ONE_ORIGINAL_PRECLAIM_INTENT'); pending = True
        else:
            need(pending and kind in ('BIND_APPLIED', 'BIND_IDEMPOTENT', 'BIND_REFUSED_UNCHANGED') and
                 set(values) <= set(new) and len(new) - len(values) == int(kind == 'BIND_APPLIED'),
                 'PAID_ADOPT_ORIGINAL_MONOTONIC_BIND_TERMINAL'); pending = False
        values, prior = new, pin; tips[i] = (pin, values, pending)
    need(not pending and values, 'PAID_ADOPT_FINAL_BIND_INTENT_OR_EMPTY_FRESH_HISTORY_REFUSED')
    epoch = len(epochs) + 1
    need(set(epochs) == set(range(2, epoch + 1)) and
         set(seals) in (set(range(1, epoch)), set(range(1, epoch + 1))), 'PAID_ADOPT_CONTIGUOUS_ORIGIN_TO_WRITER_EPOCHS')
    origin, writer, previous_epoch, lower, last_seal = None, None, None, 1, None
    for e in range(1, epoch + 1):
        if e not in seals: break
        seal, seal_sha = private_read(directory / seals[e], dir_fd=fd)
        old = birth(seal['writer_birth']); publisher = birth(seal['publisher_birth'])
        tip = seal['tip']; seq = tip['sequence']
        need(seal['schema'] == HSCHEMA and seal['writer_epoch'] == e and seal['source_binding'] == binding and
             seal['source_pins'] == PINS and seal['directory_identity'] == identity(current) and
             seal['previous_epoch_sha256'] == previous_epoch and publisher == old and
             seal['publisher_scope'] == 'EXACT_ORIGINAL_SAME_OWNER_LOOP_ONLY' and
             type(seq) is int and lower <= seq <= len(numbers) and not tips[seq][2] and
             tip == dict(sequence=seq, record_sha256=tips[seq][0], full_used_sha256=digest(list(tips[seq][1])),
                         used_count=len(tips[seq][1])), 'PAID_ADOPT_IMMUTABLE_TYPED_OLD_WRITER_PUBLISHER_CUT')
        if e == 1:
            origin = old
            need(digest(asdict(origin)) == binding['owner_sha256'], 'PAID_ADOPT_ORIGIN_OWNER_MATCHES_ORIGINAL_BINDING')
        else:
            need(old == writer, 'PAID_ADOPT_CURRENT_WRITER_FOLLOWS_PREVIOUS_EPOCH')
        control = seal['protected_control']
        mappings, _ = check_cut(control['path'], control['sha256'], directory, identity(current), binding,
            seq, tips[seq][0], tips[seq][1], asdict(old))
        need(mappings == seal['session_affinity'], 'PAID_ADOPT_SEALED_MAPPING_AND_ORIGINAL_CONTROL_EQUAL')
        validate_inbox_state(seal['native_affinity_inbox'])
        ingress = seal['closed_native_affinity_ingress']; socket = Path(ingress['path'])
        need(socket.resolve() == socket and not socket.is_symlink() and
             stat.S_ISSOCK(socket.lstat().st_mode) and identity(socket.lstat()) ==
             {k: ingress[k] for k in ('device', 'inode', 'uid', 'gid', 'mode')},
             'PAID_ADOPT_RETAINED_ORIGINAL_NATIVE_INGRESS_SOCKET_EVIDENCE')
        writer = old; last_seal = (seal, seal_sha)
        if e < epoch:
            transition, transition_sha = private_read(directory / epochs[e + 1], dir_fd=fd)
            new_writer = birth(transition['new_writer_birth'])
            need(transition == dict(schema=ESCHEMA, writer_epoch=e + 1, previous_epoch_sha256=previous_epoch,
                 handoff_sha256=seal_sha, old_writer_birth=asdict(old), new_writer_birth=asdict(new_writer),
                 old_publisher_birth=seal['publisher_birth'], new_publisher_birth=asdict(new_writer),
                 origin_owner_sha256=binding['owner_sha256'], source_binding_sha256=digest(binding),
                 source_pins=PINS, adopter_source_sha256=sha(Path(__file__).read_bytes()),
                 directory_identity=identity(current), old_tip=tip,
                 whole_paid_restore_implemented=False, models_released=False) and new_writer != old,
                 'PAID_ADOPT_APPEND_ONLY_WRITER_EPOCH_CHAIN_NOT_ORIGIN_BINDING_REWRITE')
            previous_epoch, writer, lower = transition_sha, new_writer, seq
    if epoch not in seals and epoch > 1:
        need(last_seal is not None, 'PAID_ADOPT_MISSING_PREVIOUS_EPOCH_HANDOFF')
    return VerifiedHistory(_TOKEN, binding=binding, sequence=len(numbers), record_sha256=prior, values=values,
        epoch=epoch, writer=writer, origin=origin, previous_epoch_sha256=previous_epoch,
        sealed=(last_seal if epoch in seals else None), directory_identity=identity(current))


def seal_writer_control(producer, publisher, *, native_control, protected_control_path, protected_control_sha256):
    """Capture writer-only custody at an ALREADY existing boundary, not create it.

    Pending native affinity metadata is retained verbatim; scientific collab is
    not inspected. A currently drained/unresolved publication window is WAIT.
    """
    verify_sources()
    need(type(producer) is FullUsedDomainProducer, 'PAID_ADOPT_EXACT_ORIGINAL_PRODUCER_NOT_PROXY')
    check_components(producer.sessions, producer.science_mutex, publisher)
    ingress = closed_native_ingress(native_control, publisher)
    with producer._operation():
        need(not producer.pending and not producer.in_bind and producer.failure is None,
             'PAID_ADOPT_NO_ACTIVE_OR_FAILED_DOMAIN_PUBLICATION')
        values = producer._domain_values(); producer._require_saved(values)
        history = verify_history(producer.directory, producer.fd)
        current = process_birth(os.getpid())
        need(producer.pid == current.pid and producer.thread == threading.get_ident() and history.sealed is None and
             history.sequence == producer.sequence and history.record_sha256 == producer.record_sha256 and
             history.values == values and history.binding == producer.binding and
             (history.writer == current if history.epoch > 1 else digest(asdict(current)) == history.binding['owner_sha256']),
             'PAID_ADOPT_ACTUAL_CURRENT_WRITER_BIRTH_AND_UNSEALED_TIP')
        mappings, pin = check_cut(protected_control_path, protected_control_sha256, producer.directory,
            history.directory_identity, producer.binding, producer.sequence, producer.record_sha256, values, asdict(current))
        need(mappings == affinity(producer.sessions), 'PAID_ADOPT_CURRENT_MAPPING_MATCHES_ORIGINAL_CONTROL')
        state = inbox_state(publisher)
        validate_inbox_state(state)
        row = dict(schema=HSCHEMA, writer_epoch=history.epoch, writer_birth=asdict(current),
            publisher_birth=asdict(current), publisher_scope='EXACT_ORIGINAL_SAME_OWNER_LOOP_ONLY',
            source_binding=dict(producer.binding), source_pins=PINS,
            directory_identity=history.directory_identity, previous_epoch_sha256=history.previous_epoch_sha256,
            tip=dict(sequence=producer.sequence, record_sha256=producer.record_sha256,
                full_used_sha256=digest(list(values)), used_count=len(values)), session_affinity=mappings,
            native_affinity_inbox=state, closed_native_affinity_ingress=ingress,
            protected_control=dict(path=str(protected_control_path), sha256=pin),
            whole_owner_boundary_authority=False, whole_paid_restore_implemented=False)
        name = 'WRITER_HANDOFF_' + str(history.epoch).zfill(12) + '.json'
        producer._write_new(name, wire(row))  # ORIGINAL protected IO/FD/locks/fsync code
        need(inbox_state(publisher) == state, 'PAID_ADOPT_AFFINITY_METADATA_CHANGED_DURING_SEAL_RETAIN_WAIT')
        need(closed_native_ingress(native_control, publisher) == ingress,
             'PAID_ADOPT_NATIVE_INGRESS_CUSTODY_CHANGED_DURING_SEAL')
        return dict(path=str(producer.directory / name), sha256=sha(wire(row)))


def _restore_inbox(publisher, state):
    original = inbox_state(publisher)
    if original == state: return
    need(not original['tickets'] and not original['pending'] and original['unresolved'] == 0 and
         original['timeout'] == state['timeout'] and original['maximum_pending'] == state['maximum_pending'],
         'PAID_ADOPT_NEVER_CLEAR_OR_OVERWRITE_DIFFERENT_CURRENT_NATIVE_INBOX')
    inbox = publisher.inbox
    with inbox.lock:
        need(not inbox.tickets and not inbox.pending and inbox.unresolved == 0,
             'PAID_ADOPT_PRISTINE_TARGET_NATIVE_INBOX_RECHECK')
        for key, item in state['tickets'].items():
            event = threading.Event()
            if item['accepted'] is not None: event.set()
            inbox.tickets[key] = SessionTicket(key, copy.deepcopy(item['envelope']), tuple(item['peer']), event,
                accepted=item['accepted'])
        inbox.pending.extend(inbox.tickets[key] for key in state['pending'])
        inbox.unresolved = state['unresolved']
    need(inbox_state(publisher) == state, 'PAID_ADOPT_ORIGINAL_NATIVE_ONCE_PENDING_STATE_PRESERVED')


def adopt_existing_writer(sessions, science_mutex, publisher, *, directory, handoff_path, handoff_sha256):
    """Hydrate exact original producer; NO fresh ctor, model authority or replay."""
    global RETAINED_ADOPTION
    need(RETAINED_ADOPTION is None, 'PAID_ADOPT_ONE_RETAINED_COMPONENT_ATTEMPT_NO_REPLAY')
    verify_sources(); tracks, domain = check_components(sessions, science_mutex, publisher)
    need(domain.claim.__func__ is AffinityDomain.claim and
         all(t.bind.__func__ is DynamicSessions.bind for t in tracks.values()),
         'PAID_ADOPT_ORIGINAL_UNQUARANTINED_METHODS_REQUIRED_NOT_STUB_REPAIR')
    directory = Path(directory); parent = directory.parent.lstat()
    need(parent.st_uid == os.geteuid() and stat.S_IMODE(parent.st_mode) == 0o700 and
         Path(handoff_path).parent == directory, 'PAID_ADOPT_ORIGINAL_PRIVATE_OWNER_AND_HANDOFF_PATH')
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    producer = None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        history = verify_history(directory, fd)
        need(history.sealed is not None, 'PAID_ADOPT_COMPLETE_LATEST_WRITER_HANDOFF_REQUIRED')
        seal, pin = history.sealed
        need(Path(handoff_path).name == 'WRITER_HANDOFF_' + str(history.epoch).zfill(12) + '.json' and
             pin == handoff_sha256 and seal['tip']['sequence'] == history.sequence and
             seal['tip']['record_sha256'] == history.record_sha256,
             'PAID_ADOPT_LATEST_SEALED_TIP_NOT_STALE_OR_LATER_WRITE')
        current = process_birth(os.getpid())
        need(nonexecuting(birth(seal['writer_birth']), current) and
             nonexecuting(birth(seal['publisher_birth']), current), 'PAID_ADOPT_OLD_WRITER_OR_PUBLISHER_STILL_EXECUTING')
        with domain.lock: values = tuple(sorted(domain.used))
        need(values == history.values and digest(sorted(tracks)) == history.binding['cohort_sha256'] and
             affinity(sessions) == seal['session_affinity'] and
             all(set(seal['session_affinity'][t]) <= set(track.roles) for t, track in tracks.items()),
             'PAID_ADOPT_ALREADY_HYDRATED_EXACT_USED_AND_MAPPING_NO_CLEAR_OR_SID_CHANGE')
        producer = FullUsedDomainProducer.__new__(FullUsedDomainProducer)
        producer.sessions, producer.science_mutex = sessions, science_mutex
        producer.pid, producer.thread = current.pid, threading.get_ident()
        producer.serial = threading.Lock(); producer.failure = None
        producer.pending = producer.in_bind = False
        producer.sequence, producer.record_sha256 = history.sequence, history.record_sha256
        producer.saved = history.values; producer.fd = fd
        producer.tracks, producer.domain, producer.used_object = tracks, domain, domain.used
        producer.binding = copy.deepcopy(history.binding); producer.binding_sha256 = digest(producer.binding)
        producer.directory, producer.directory_identity = directory, (history.directory_identity['device'], history.directory_identity['inode'])
        producer.original_claim = domain.claim
        producer.original_binds = {name: track.bind for name, track in tracks.items()}
        producer._outside_locks(); producer._io_guard()
        # Recheck source/control/physical identity AFTER exclusive lock and all
        # reads. No caller true, PID-only receipt or waitid/exit0 production gate.
        need(nonexecuting(birth(seal['writer_birth']), current) and
             nonexecuting(birth(seal['publisher_birth']), current), 'PAID_ADOPT_OLD_IDENTITY_RECHECK_AFTER_CUSTODY')
        RETAINED_ADOPTION = producer  # partial O_EXCL/fsync/hooks failure remains retained
        transition = dict(schema=ESCHEMA, writer_epoch=history.epoch + 1,
            previous_epoch_sha256=history.previous_epoch_sha256, handoff_sha256=pin,
            old_writer_birth=seal['writer_birth'], new_writer_birth=asdict(current),
            old_publisher_birth=seal['publisher_birth'], new_publisher_birth=asdict(current),
            origin_owner_sha256=history.binding['owner_sha256'], source_binding_sha256=digest(history.binding),
            source_pins=PINS, adopter_source_sha256=sha(Path(__file__).read_bytes()),
            directory_identity=history.directory_identity, old_tip=seal['tip'],
            whole_paid_restore_implemented=False, models_released=False)
        producer._write_new('WRITER_EPOCH_' + str(history.epoch + 1).zfill(12) + '.json', wire(transition))
        _restore_inbox(publisher, seal['native_affinity_inbox'])
        producer._install_hooks()  # EXACT original instance hook assembly
        producer._check_hooks(); producer._require_saved(producer._domain_values())
        producer._paid_writer_epoch = history.epoch + 1
        producer._paid_writer_epoch_sha256 = sha(wire(transition))
        return producer
    except BaseException:
        if RETAINED_ADOPTION is not None:
            RETAINED_ADOPTION.failure = 'PAID_ADOPT_PARTIAL_TRANSITION_RETAINED_NO_RETRY'
        else:
            os.close(fd)
        raise


def public_writer_epoch(producer):
    need(type(producer) is FullUsedDomainProducer, 'PAID_ADOPT_EXACT_ORIGINAL_PRODUCER_PUBLIC_ONLY')
    return dict(schema='count14-full-used-paid-writer-epoch-PUBLIC-v1',
        origin_binding_sha256=digest(producer.binding), writer_birth_sha256=digest(asdict(process_birth(os.getpid()))),
        writer_epoch=getattr(producer, '_paid_writer_epoch', 1),
        writer_epoch_sha256=getattr(producer, '_paid_writer_epoch_sha256', None),
        record_sequence=producer.sequence, record_sha256=producer.record_sha256,
        full_used_sha256=digest(list(producer.saved)), used_count=len(producer.saved),
        whole_owner_boundary_authority=False, whole_paid_restore_implemented=False,
        models_released=False, actual_cold_qualified=False)
