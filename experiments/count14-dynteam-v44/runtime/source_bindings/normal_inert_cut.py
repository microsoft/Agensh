"""Normal-source INERT reference/capability boundary, never runnable authority.

A path/hash reference alone is NOT authority. A verified capability also needs
the fixed metadata-only receiver's old-ended/new-birth/original-lock proof.
The explicit OWN namespace cannot be consumed by the production verifier.
"""
from dataclasses import asdict
from pathlib import Path
import copy
import hashlib
import importlib
import os
import stat
import threading

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget

SCHEMA = 'count14-normal-source-INERT-only-cut-ticket-v1'
OWN_SCHEMA = 'count14-OWN-INERT-only-component-ticket-v1'
LEAF = 'normal-inert-cut-control-v1'
OWN_LEAF = 'OWN-normal-inert-cut-control-v1'
COMPONENTS = frozenset(('native_SDK_epoch_controls', 'paid_FINAL_controls', 'normal_clock_controls',
                        'native_peer_birth_controls', 'financial', 'original_storage_identities', 'cuts',
                        'fullused_public_tip'))
_SEAL = object()
_ISSUERS = {}
SOURCE_PINS = dict(
    complete_source_control='67ccae6cd502738934aa942fa1ea078c1a030d2d53ffe258fdc763151f81332b',
    paid_final_source_capture='ed981d7d293e2a6a0d7f8c35f01fda697d570ae563a681b613cb8b3c0f5b5e64',
    fixed_queue_control_projection='8a53553c125a72c23c3aa5a118e9bb7ceec8ef27ff133f1ae622e46084962015',
    observed_cut_control_witness='f220d6591dc09c4bc831dfb3f79ae45db8dae99b3f33d6f5cc279b181469f7a7',
    native_sdk_epoch_control_v2='2f7ab34a1a1a89b39bba94ee0c8801b0cac48d811b95dc51e5961b755e9bb417',
    clock_controls_cold='395a5ad1edaf8f622f5a88d87a2cffb2bef22003bcdcb28a08b03dc9835baa29',
    normal_transport_retirement='51774562e2c0f6d26b90f2b307ec265a1da11c06553c7965535cdbddd827f9c2')


class InertTicketInspection:
    """Fixed parsed metadata, explicitly NOT source/receiver authority."""
    __slots__ = ('material', 'source_controls', 'ticket_sha256', 'path')


class NormalInertTicket:
    __slots__ = ('_path', '_pin', '_seal')
    def __init__(self, *args, **kwargs):
        raise M.PaidColdWait('NORMAL_INERT_REFERENCE_ONLY_FIXED_LOADER')
    def __setattr__(self, name, value):
        M.need(not hasattr(self, '_seal'), 'NORMAL_INERT_REFERENCE_IMMUTABLE')
        object.__setattr__(self, name, value)
    @property
    def path(self): return self._path
    @property
    def sha256(self): return self._pin


class OWNNormalInertTicket(NormalInertTicket):
    __slots__ = ()


class VerifiedNormalInertCut:
    __slots__ = ('_body', '_seal', 'old_owner_birth', 'new_owner_birth', 'contract_sha256',
                 'source_control_sha256', 'owner_home', 'ledger_database', 'queue_database',
                 'control_locks', 'full_used_directory', 'OWN', 'full_used_fd')
    def __init__(self, *args, **kwargs):
        raise M.PaidColdWait('NORMAL_INERT_CAPABILITY_ONLY_FIXED_VERIFIER')
    def __setattr__(self, name, value):
        M.need(not hasattr(self, '_seal'), 'NORMAL_INERT_VERIFIED_CAPABILITY_IMMUTABLE')
        object.__setattr__(self, name, value)
    @property
    def safe_to_TERM(self): return False
    @property
    def paid_activation_authorized(self): return False
    @property
    def whole_runnable_ready(self): return False
    def component(self, name):
        M.need(self._seal is _SEAL and name in COMPONENTS and name in self._body['source_controls'],
               'NORMAL_INERT_FIXED_CAPTURED_COMPONENT_ONLY')
        return copy.deepcopy(self._body['source_controls'][name])
    def has_component(self, name):
        M.need(self._seal is _SEAL and name in COMPONENTS, 'NORMAL_INERT_FIXED_COMPONENT_NAME')
        return name in self._body['source_controls']
    @property
    def available_components(self):
        M.need(self._seal is _SEAL, 'NORMAL_INERT_FIXED_VERIFIER_CAPABILITY')
        return frozenset(self._body['source_controls']) & COMPONENTS


def verify_source_components():
    for name, pin in SOURCE_PINS.items():
        path = Path(importlib.import_module(name).__file__)
        M.need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
               hashlib.sha256(path.read_bytes()).hexdigest() == pin,
               'NORMAL_INERT_FIXED_SAFE_SOURCE_COMPONENT_PIN')
    import complete_source_control as C
    C.verify_sources()
    return dict(SOURCE_PINS)


def _reference(path, pin, cls):
    value = object.__new__(cls)
    value._path, value._pin, value._seal = str(Path(path)), M.sha(pin), _SEAL
    return value


def _read_reference(ticket, *, own, read_budget):
    M.need(type(read_budget) is ReadBudget and
           type(ticket) is (OWNNormalInertTicket if own else NormalInertTicket) and ticket._seal is _SEAL,
           'NORMAL_INERT_EXACT_REFERENCE_TYPE_NOT_DICT_BOOL_OR_FACTORY')
    read_budget.check()
    body, pin = M.private_read(ticket.path, ticket.sha256, limit=16*1024*1024)
    schema, leaf = (OWN_SCHEMA, OWN_LEAF) if own else (SCHEMA, LEAF)
    M.need(type(body) is dict and body['schema'] == schema and body['OWN'] is own and
           body['inert_only'] is True and body['safe_to_TERM'] is False and
           body['paid_activation_authorized'] is False and body['whole_runnable_ready'] is False,
           'NORMAL_INERT_EXACT_NAMESPACE_AND_PERMANENT_NONRUNNABLE_SCOPE')
    home = M.existing(body['owner_home'], directory=True, private=True)
    parent = M.existing(body['ticket_directory'], directory=True, private=True)
    M.need(parent == home/leaf and Path(ticket.path) == parent/'TICKET.json' and
           body['source_control_sha256'] == M.digest(body['source_controls']) and
           M.birth(body['old_owner_birth']).uid == os.geteuid(),
           'NORMAL_INERT_FIXED_ORIGINAL_HOME_AND_PROTECTED_CONTROL_BINDING')
    commit, _ = M.private_read(parent/'ISSUED.json', limit=16384)
    M.need(commit == dict(schema='count14-normal-INERT-source-publication-complete-v1',
                          ticket_sha256=ticket.sha256, ticket_identity=M.descriptor(ticket.path),
                          OWN=own, inert_only=True, safe_to_TERM=False,
                          paid_activation_authorized=False, whole_runnable_ready=False),
           'NORMAL_INERT_WAIT_REAL_SOURCE_POSTCHECK_AND_O_EXCL_ISSUED_RECEIPT')
    M.sha(body['contract_sha256'])
    if not own:
        M.need(body['producer_scope'] == 'EXACT_REGISTERED_NORMAL_SOURCE_INERT_ONLY' and
               body['actual_production_six_source_guard_used'] is True and
               body['producer_source_pins'] == SOURCE_PINS and
               M.digest(body['contract']) == body['contract_sha256'],
               'NORMAL_INERT_FIXED_NORMAL_SOURCE_PRODUCER_NOT_CALLER_FLAGS')
        original_ref = body['original_source_reference']
        original_path = M.existing(original_ref['identity'], private=True)
        M.need(original_path.parent == home/'normal-cold-candidate-control-v1' and
               original_path.name.startswith('CONTROL_') and original_path.name.endswith('.json'),
               'NORMAL_INERT_FIXED_ORIGINAL_DURABLE_CONTROL_REFERENCE')
        original, _ = M.private_read(original_path, original_ref['sha256'])
        M.need(original['schema'] == 'count14-normal-cold-whole-graph-control-CANDIDATE-v1' and
               original['authority']['original_owner_birth'] == body['old_owner_birth'] and
               original['authority']['contract_sha256'] == body['contract_sha256'] and
               original['metadata_capture'] == body['source_controls'] and
               original['candidate_notready'] is True and original['authority']['safe_to_TERM'] is False,
               'NORMAL_INERT_EXACT_PRESERVED_SOURCE_CONTROL_NOT_SIX_SNAPSHOTS_AS_RUNTIME')
        _bind_pre_post(body['source_controls'], body['post_retirement_controls'])
        M.need(body['financial_metadata'] == body['post_retirement_controls']['financial'],
               'NORMAL_INERT_SOURCE_POST_FINANCIAL_BINDING')
        storage = body['source_controls']['original_storage_identities']
        M.need(all(body[k] == storage[k] for k in ('owner_home', 'ledger_home', 'queue_home')) and
               body['ledger_database'] == storage['ledger_database'] and
               body['queue_database'] == storage['queue_database'] and
               body['full_used_directory'] == body['source_controls']['native_SDK_epoch_controls']['full_used_domain']['directory'] and
               Path(body['owner_home']['path']) == Path(body['contract']['arms'][0]['root'])/'owner',
               'NORMAL_INERT_SAME_SOURCE_STORAGE_AND_FULLUSED_DIRECTORY_REFERENCES')
    read_budget.check()
    return body


def load_inert_ticket(path, sha256):
    """Produce an UNVERIFIED reference; not permission to attach/TERM/activate."""
    value = _reference(path, sha256, NormalInertTicket)
    _read_reference(value, own=False, read_budget=ReadBudget())
    return value


def load_OWN_inert_ticket(path, sha256):
    value = _reference(path, sha256, OWNNormalInertTicket)
    _read_reference(value, own=True, read_budget=ReadBudget())
    return value


def inspect_inert_reference(ticket, *, read_budget):
    """Untrusted fixed metadata input for a separate, fixed RO pair verifier."""
    own = type(ticket) is OWNNormalInertTicket
    body = _read_reference(ticket, own=own, read_budget=read_budget)
    value = InertTicketInspection()
    names = ('contract', 'contract_sha256', 'owner_home', 'ledger_home', 'ledger_database',
             'queue_home', 'queue_database', 'full_used_directory', 'financial_metadata')
    M.need(all(name in body for name in names) and 'locks' in body,
           'NORMAL_INERT_MATERIAL_COMPLETE_NO_FAULT_OR_FINANCE_DEFAULTS')
    value.material = {k: copy.deepcopy(body[k]) for k in names}
    value.material.update(source_birth=M.birth(body['old_owner_birth']),
                          locks=tuple((kind, copy.deepcopy(row)) for kind, row in body['locks']),
                          qualification_only=own)
    if own:
        M.need(body.get('OWN_scope') in ('OWN_REAL_QUEUE_INERT_LINEAGE_MATERIAL_V1', 'OWN_NATIVE_METADATA_ONLY'),
               'NORMAL_INERT_EXPLICIT_OWN_FIXTURE_SCOPE_NOT_MIXED')
        value.material['OWN_scope'] = body['OWN_scope']
    value.source_controls, value.ticket_sha256, value.path = copy.deepcopy(body['source_controls']), ticket.sha256, ticket.path
    return value


def _save(home, body, *, own):
    """Original private O_EXCL metadata publication, never an old-file rewrite."""
    from normal_cold_sealer import save_candidate
    home = M.existing(M.descriptor(home), directory=True, private=True)
    leaf = home/(OWN_LEAF if own else LEAF)
    leaf.mkdir(mode=0o700, parents=False, exist_ok=False)
    body = dict(body, schema=OWN_SCHEMA if own else SCHEMA, OWN=own,
                owner_home=M.descriptor(home), ticket_directory=M.descriptor(leaf),
                source_control_sha256=M.digest(body['source_controls']),
                inert_only=True, safe_to_TERM=False,
                paid_activation_authorized=False, whole_runnable_ready=False)
    ref = save_candidate(leaf/'TICKET.json', body)
    # Original save_candidate fsyncs leaf; persist its link in existing home too.
    fd = os.open(home, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)
    ticket = _reference(ref['identity']['path'], ref['sha256'], OWNNormalInertTicket if own else NormalInertTicket)
    if own:
        _commit_publication(ticket, own=True)
    return ticket


def _commit_publication(ticket, *, own):
    from normal_cold_sealer import save_candidate
    body = dict(schema='count14-normal-INERT-source-publication-complete-v1',
                ticket_sha256=ticket.sha256, ticket_identity=M.descriptor(ticket.path),
                OWN=own, inert_only=True, safe_to_TERM=False,
                paid_activation_authorized=False, whole_runnable_ready=False)
    return save_candidate(Path(ticket.path).parent/'ISSUED.json', body)


def _has_write_flock(fd):
    # Own framework descriptor control only, not a process stack/log/body.
    return any(s.startswith('lock:') and ' FLOCK ' in s and ' WRITE ' in s
               for s in Path('/proc/self/fdinfo', str(fd)).read_text().splitlines())


def _validate_owned_locks(fds, descriptors):
    M.need(type(fds) in (list, tuple) and len(fds) == len(descriptors),
           'NORMAL_INERT_COMPLETE_ALREADY_HELD_LOCK_INVENTORY')
    for fd, row in zip(fds, descriptors):
        M.need(type(fd) is int and fd >= 0, 'NORMAL_INERT_EXACT_REGISTERED_LOCK_FD')
        p = Path(row['path']); st = p.lstat(); opened = os.fstat(fd)
        M.need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and
               M.stamp(st) == {k: row[k] for k in M.stamp(st)} and
               (st.st_dev, st.st_ino) == (opened.st_dev, opened.st_ino) and _has_write_flock(fd),
               'NORMAL_INERT_SAME_INODE_AND_EXISTING_EXCLUSIVE_FLOCK_CUSTODY')


# Bound once to ROOT's fixed metadata-only pair before this leaf is frozen.
PAIR_SOURCE_SHA256 = '83b2662daef394a6c3bb9cbfa46fc15a49c4382df7db5c963ec89a1f61b853da'


def _pair_api():
    module = importlib.import_module('metadata_inert_pair')
    path = Path(module.__file__)
    M.need(len(PAIR_SOURCE_SHA256) == 64 and path.is_absolute() and path.resolve() == path and
           not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == PAIR_SOURCE_SHA256,
           'NORMAL_INERT_WAIT_FIXED_METADATA_ONLY_PAIR_SOURCE_PIN')
    return module


def _material_body(material):
    names = ('contract', 'contract_sha256', 'owner_home', 'ledger_home', 'ledger_database',
             'queue_home', 'queue_database', 'full_used_directory', 'financial_metadata')
    M.need(all(k in material for k in names), 'NORMAL_INERT_COMPLETE_TYPED_PAIR_MATERIAL_REQUIRED')
    body = {k: copy.deepcopy(material[k]) for k in names}
    body['old_owner_birth'] = asdict(material['source_birth'])
    body['locks'] = [[kind, copy.deepcopy(row)] for kind, row in material['locks']]
    body['control_locks'] = [copy.deepcopy(row) for kind, row in material['locks']]
    if material['qualification_only']:
        body['OWN_scope'] = material['OWN_scope']
    return body


def _own_pair(owner, read_budget):
    from native_peer_registry import process_birth
    api = _pair_api()
    proof = api.verify_OWN_registered_pair(owner, read_budget=read_budget)
    M.need(type(proof) is api.VerifiedMetadataPair and proof.owner is owner and
           proof.qualification_only is True and proof.new_owner_birth == process_birth(os.getpid()),
           'NORMAL_INERT_EXACT_OWN_METADATA_PAIR_PROOF')
    return proof


def issue_OWN_inert_ticket(owner, *, source_controls, read_budget):
    """Explicit OWN receipt port. Caller controls NEVER authorize production.

    Material and existing FD/birth custody come from the fixed ROOT pair, not a
    caller dict, bool, or old broad PaidColdCustody constructor. Actual native
    and raw4 queue fixtures remain distinct allowed-component namespaces.
    """
    proof = _own_pair(owner, read_budget)
    M.need(type(source_controls) is dict and source_controls and
           set(source_controls) <= set(proof.allowed_components) <= COMPONENTS and
           source_controls == owner.core.metadata_inert_pair.source_controls,
           'NORMAL_INERT_OWN_ONLY_ACTUAL_TYPED_PAIR_COMPONENT_SCOPE')
    material = _material_body(proof.material)
    return _save(Path(material['owner_home']['path']), dict(material,
        source_controls=copy.deepcopy(source_controls), allowed_components=sorted(proof.allowed_components),
        producer_scope='OWN_RECEIPT_COMPONENT_NOT_PRODUCTION_ISSUER',
        actual_production_six_source_guard_used=False), own=True)


def _cap(body, current, *, own, full_used_fd):
    value = object.__new__(VerifiedNormalInertCut)
    value._body = copy.deepcopy(body)
    value.old_owner_birth, value.new_owner_birth = M.birth(body['old_owner_birth']), current
    for name in ('contract_sha256', 'source_control_sha256', 'owner_home', 'ledger_database',
                 'queue_database', 'control_locks', 'full_used_directory'):
        setattr(value, name, copy.deepcopy(body[name]))
    value.OWN, value.full_used_fd = own, full_used_fd
    value._seal = _SEAL
    return value


def _bind_cap(body, proof, *, own):
    material = _material_body(proof.material)
    M.need(all(body[k] == v for k, v in material.items()),
           'NORMAL_INERT_TICKET_EQUALS_EXACT_CURRENT_SOURCE_BOUND_RO_PAIR_MATERIAL')
    pair = proof.owner.core.metadata_inert_pair
    records = pair.control_lock_records
    M.need(len(records) == len(pair.lock_fds), 'NORMAL_INERT_FULL_REGISTERED_PAIR_LOCKS')
    matches = [(fd, row) for (kind, row), fd in zip(records, pair.lock_fds) if kind == 'fullused']
    M.need(len(matches) == 1 and matches[0][1] == body['full_used_directory'],
           'NORMAL_INERT_SOURCE_FULLUSED_DIRECTORY_AND_REGISTERED_FD')
    full_used_fd = matches[0][0]
    _validate_owned_locks([full_used_fd], [body['full_used_directory']])
    return _cap(body, proof.new_owner_birth, own=own, full_used_fd=full_used_fd)


def verify_OWN_inert_ticket(ticket, *, owner, read_budget):
    body = _read_reference(ticket, own=True, read_budget=read_budget)
    proof = _own_pair(owner, read_budget)
    M.need(body['producer_scope'] == 'OWN_RECEIPT_COMPONENT_NOT_PRODUCTION_ISSUER' and
           body['actual_production_six_source_guard_used'] is False and
           set(body['source_controls']) <= set(proof.allowed_components) and
           body['allowed_components'] == sorted(proof.allowed_components),
           'NORMAL_INERT_OWN_TICKET_SCOPE_CANNOT_BECOME_PRODUCTION')
    return _bind_cap(body, proof, own=True)


def verify_inert_ticket(ticket, *, owner, read_budget):
    from native_peer_registry import process_birth
    body = _read_reference(ticket, own=False, read_budget=read_budget)
    api = _pair_api()
    proof = api.verify_registered_pair(owner, ticket=ticket, read_budget=read_budget)
    M.need(type(proof) is api.VerifiedMetadataPair and proof.owner is owner and
           proof.qualification_only is False and proof.new_owner_birth == process_birth(os.getpid()) and
           proof.source_birth == M.birth(body['old_owner_birth']),
           'NORMAL_INERT_EXACT_NEW_BIRTH_SOURCE_BOUND_METADATA_ONLY_PAIR_PROOF')
    return _bind_cap(body, proof, own=False)


def _retired_transport(owner, read_budget):
    """Existing physical terminal handles only. NEVER call server.current()."""
    from normal_transport_retirement import NormalTransportRetirement, original_handler_threads_clear
    from bounded_metadata_ro import ram_lock
    transport = owner.normal_transport_retirement
    M.need(type(transport) is NormalTransportRetirement and transport.owner is owner and
           transport.core is owner.core and transport.barrier is owner.normal_cold_barrier,
           'NORMAL_INERT_SAME_ORIGINAL_TRANSPORT_RETIREMENT_OBJECT')
    transport._current()
    expected = {id(s) for s in transport.servers}
    M.need(transport.requested and transport.failure is None and transport.gate_shutdown_done and
           transport.state == 'OLD_HTTP_TRANSPORTS_RETIRED_NO_SDK_CLAIM' and
           transport.stopped == transport.closed == expected and len(expected) == 6 and
           transport.gate is owner.core.gate and transport.gate.closed and not transport.gate.waiters and
           transport.protected_control is not None, 'NORMAL_INERT_WAIT_TRUE_ORIGINAL_TRANSPORT_RETIREMENT')
    listeners = []
    for server in transport.servers:
        read_budget.check()
        M.need(server.closed and server.network_closed and server.listener_stopped and server.retire_attempted and
               server.loop_finished.is_set() and server.thread is not None and not server.thread.is_alive() and
               server.socket.fileno() == -1 and not server.lifecycle_storage_unknown and
               original_handler_threads_clear(server), 'NORMAL_INERT_WAIT_PHYSICAL_HTTP_SOCKET_LOOP_HANDLERS_ENDED')
        with ram_lock(server.registry_lock, read_budget):
            M.need(not server.requests and not server.accepted_sockets and not server.retained,
                   'NORMAL_INERT_WAIT_ZERO_ACTUAL_HTTP_REQUEST_SOCKET_CUSTODY')
        listeners.append(server.listener_identity_sha256)
    ref = transport.protected_control
    path = Path(ref['path']); st = path.lstat()
    M.need(path == owner.core.home/'normal-transport-retirement-control-v1/ORIGINAL_UNSENT_CONTROL.json' and
           path.resolve() == path and not path.is_symlink() and stat.S_ISREG(st.st_mode) and
           st.st_uid == os.geteuid() and stat.S_IMODE(st.st_mode) == 0o400 and st.st_nlink == 1,
           'NORMAL_INERT_ORIGINAL_UNSENT_CONTROL_REFERENCE_RETAINED')
    M.sha(ref['sha256'])
    # Do NOT decode/hash its request-id-bearing original transport control body.
    return dict(state=transport.state, protected_control=dict(ref),
                protected_control_identity=M.descriptor(path), listeners=listeners,
                original_closed_socket_count=6, original_listener_loop_and_handler_threads_ended=True)


def _post_controls(owner, read_budget):
    """Independent post-retirement metadata observation. No original HTTP poll."""
    from bounded_metadata_ro import financial_controls, ram_lock
    from clock_controls_cold import capture_registered as clocks
    from native_sdk_epoch_control_v2 import capture_registered as epochs
    from paid_final_source_capture import capture_registered as final
    from observed_cut_control_witness import observed_six_cut_witness
    core, barrier = owner.core, owner.normal_cold_barrier
    _retired_transport(owner, read_budget)
    read_budget.check(); witness = observed_six_cut_witness(owner); read_budget.check()
    financial = financial_controls(core, barrier.approved, read_budget)
    with ram_lock(core.peers._lock, read_budget):
        peers = [dict(trajectory=t, role=r, purpose=p, birth=asdict(v))
                 for (t, r, p), v in sorted(core.peers._peers.items())]
    result = dict(financial=financial, normal_clock_controls=clocks(owner, read_budget=read_budget),
                  native_SDK_epoch_controls=epochs(owner, read_budget=read_budget),
                  paid_FINAL_controls=final(owner, read_budget=read_budget),
                  native_peer_birth_controls=peers, normal_cut_witness=witness)
    _retired_transport(owner, read_budget)
    read_budget.check()
    return result


def _finance_without_sequence(financial):
    value = copy.deepcopy(financial)
    sequence = {t: row.pop('sequence') for t, row in value['frontiers'].items()}
    return value, sequence


def _clock_science_equal(before, after):
    """Keep both real anchors/counters; never compute inferred elapsed time."""
    old, new = copy.deepcopy(before), copy.deepcopy(after)
    for t in old['tracks']:
        # An original read/tx refreshes this observation anchor while held.
        # Preserve its actual pre/post values in the receipt, never add the gap.
        previous_anchor = old['tracks'][t]['active'].pop('observed_ns')
        current_anchor = new['tracks'][t]['active'].pop('observed_ns')
        M.need(current_anchor >= previous_anchor, 'NORMAL_INERT_ORIGINAL_CLOCK_ANCHOR_NO_REGRESSION')
    old_pauses = {(r['trajectory'], r['role']): r for r in old.pop('budget_pause')}
    new_pauses = {(r['trajectory'], r['role']): r for r in new.pop('budget_pause')}
    M.need(set(old_pauses) == set(new_pauses), 'NORMAL_INERT_ORIGINAL_BUDGET_PAUSE_IDENTITY_SET_UNCHANGED')
    for key, row in old_pauses.items():
        current = new_pauses[key]
        M.need(current['since_ns'] is None and current['total_ns'] >= row['total_ns'] and
               (row['since_ns'] is not None or current['total_ns'] == row['total_ns']),
               'NORMAL_INERT_ORIGINAL_GATE_SHUTDOWN_PAUSE_ACCOUNTING_ONLY')
    return old == new


def _bind_pre_post(pre, post):
    old, pre_seq = _finance_without_sequence(pre['financial'])
    new, post_seq = _finance_without_sequence(post['financial'])
    M.need(old == new and all(post_seq[t] >= pre_seq[t] for t in pre_seq),
           'NORMAL_INERT_WAIT_ANY_FEE_REQUEST_OPERATION_OR_QUEUE_CHANGE')
    M.need(_clock_science_equal(pre['normal_clock_controls'], post['normal_clock_controls']) and
           pre['native_SDK_epoch_controls'] == post['native_SDK_epoch_controls'] and
           pre['paid_FINAL_controls'] == post['paid_FINAL_controls'] and
           pre['native_peer_birth_controls'] == post['native_peer_birth_controls'],
           'NORMAL_INERT_WAIT_SCIENTIFIC_CLOCK_SDK_FINAL_OR_PEER_CONTROL_CHANGE')
    M.need(not post['native_SDK_epoch_controls']['unresolved_session_references'],
           'NORMAL_INERT_WAIT_COMPLETE_ORIGINAL_SESSION_LOCATORS')
    jobs = post['paid_FINAL_controls']['original_queue']['all_jobs']
    M.need(all(r['state'] not in ('CLAIMED', 'RUNNING', 'CHILD_EXITED_HOLD', 'CUSTODY_UNKNOWN') for r in jobs),
           'NORMAL_INERT_WAIT_ALL_ORIGINAL_PAID_FINAL_CUSTODY_CLEAR')
    return dict(pre_frontier_sequences=pre_seq, post_frontier_sequences=post_seq,
                unchanged_financial_request_operation_queue_equations=True,
                pre_and_post_real_clock_anchors_and_original_pause_counters_retained=True)


class NormalInertIssuer:
    """First-cold fixed source producer. No caller dict/callback/factory proof."""
    def __init__(self, owner):
        from native_cold_owner import NativeColdOwner
        from original_relay_core import OriginalRelayCore
        from normal_cold_sealer import NormalColdCandidateSealer
        verify_source_components()
        M.need(type(owner) is NativeColdOwner and type(owner.core) is OriginalRelayCore and
               not owner.core.qualification_only and type(owner.normal_cold_sealer) is NormalColdCandidateSealer,
               'NORMAL_INERT_ISSUER_ONLY_REAL_REGISTERED_PRODUCTION_OWNER')
        source = owner.normal_cold_sealer
        source._current()
        M.need(not source.requested and not source.publication_started and
               not source.cohort.activation_attempted and not source.core.scientific_activation_qualified and
               hasattr(source, '_complete_source_control_cold_proof') and id(owner) not in _ISSUERS and
               not hasattr(owner, 'normal_inert_cut_issuer'), 'NORMAL_INERT_INSTALL_FIRST_COLD_BEFORE_PAID_ONLY')
        self.owner, self.source, self.core, self.birth = owner, source, owner.core, source.birth
        self.pid, self.thread = os.getpid(), threading.get_ident()
        self.ticket, self.publication_started = None, False
        _ISSUERS[id(owner)] = self
        owner.normal_inert_cut_issuer = self

    def _current(self):
        self.source._current()
        M.need(_ISSUERS.get(id(self.owner)) is self and self.owner.normal_inert_cut_issuer is self and
               self.owner.core is self.core and self.owner.normal_cold_sealer is self.source and
               self.birth == self.source.birth and os.getpid() == self.pid and threading.get_ident() == self.thread,
               'NORMAL_INERT_SAME_ORIGINAL_REGISTERED_ISSUER_AND_METADATA_THREAD')

    def issue(self, *, read_budget):
        self._current(); verify_source_components()
        M.need(type(read_budget) is ReadBudget and self.ticket is None and not self.publication_started,
               'NORMAL_INERT_SINGLE_SOURCE_PUBLICATION_NO_RETRY_OR_OVERWRITE')
        source, core = self.source, self.core
        M.need(source.state == 'NORMAL_SOURCE_CANDIDATE_WRITTEN_NOT_READY' and
               source.control_reference is not None and source.handoff_reference is not None,
               'NORMAL_INERT_WAIT_ORIGINAL_COMPLETE_PRE_RETIREMENT_DURABLE_CANDIDATE')
        ref = source.control_reference
        control_path = M.existing(ref['identity'], private=True)
        M.need(control_path == core.home/'normal-cold-candidate-control-v1'/('CONTROL_'+str(source.sequence).zfill(12)+'.json'),
               'NORMAL_INERT_ORIGINAL_SOURCE_DERIVED_O_EXCL_CONTROL_ONLY')
        control, _ = M.private_read(control_path, ref['sha256'])
        M.need(control['schema'] == 'count14-normal-cold-whole-graph-control-CANDIDATE-v1' and
               control['authority']['original_owner_birth'] == asdict(self.birth) and
               control['authority']['contract_sha256'] == source.source_binding and
               control['observed_six_normal_frozen_cuts'] is True and control['candidate_notready'] is True,
               'NORMAL_INERT_ORIGINAL_DURABLE_SOURCE_SCOPE_NO_CAPABILITY_UPGRADE')
        pre = control['metadata_capture']
        M.need(all(k in pre for k in ('normal_clock_controls', 'native_SDK_epoch_controls', 'paid_FINAL_controls')) and
               len(pre['cuts']) == 6, 'NORMAL_INERT_WAIT_COMPLETE_PRE_CLOCK_SDK_FINAL_CONTROLS')
        transport = _retired_transport(self.owner, read_budget)
        before = _post_controls(self.owner, read_budget)
        equality = _bind_pre_post(pre, before)
        after = _post_controls(self.owner, read_budget)
        # During this final post observation, even an observation anchor change
        # is NOT elided. Keep the entire real post controls stable or just WAIT.
        M.need(before == after, 'NORMAL_INERT_POST_RETIREMENT_CONTROLS_CHANGED_WAIT')
        domain = core.formal_full_used_domain
        locks = [('ledger', M.descriptor(core.ledger.home/'owner.lock')),
                 ('queue', M.descriptor(core.queue.home/'owner.lock')),
                 ('fullused', M.descriptor(domain.directory))]
        _validate_owned_locks([core.ledger.fd, core.queue.fd, domain.fd], [row for kind, row in locks])
        body = dict(old_owner_birth=asdict(self.birth), contract=copy.deepcopy(core.contract),
            contract_sha256=source.source_binding, owner_home=M.descriptor(core.home),
            ledger_home=M.descriptor(core.ledger.home), queue_home=M.descriptor(core.queue.home),
            ledger_database=M.descriptor(core.ledger.home/'ledger.sqlite'),
            queue_database=M.descriptor(core.queue.home/'queue.sqlite'),
            full_used_directory=M.descriptor(domain.directory), locks=locks,
            control_locks=[row for kind, row in locks], financial_metadata=before['financial'],
            source_controls=copy.deepcopy(pre), original_source_reference=copy.deepcopy(ref),
            post_retirement_controls=before, transport_retirement=transport,
            financial_equations=equality, producer_source_pins=verify_source_components(),
            producer_scope='EXACT_REGISTERED_NORMAL_SOURCE_INERT_ONLY',
            actual_production_six_source_guard_used=True)
        self._current(); read_budget.check()
        self.publication_started = True
        prepared = _save(core.home, body, own=False)
        # Partial publication never becomes authority and is never overwritten.
        M.need(_post_controls(self.owner, read_budget) == before and
               _retired_transport(self.owner, read_budget) == transport,
               'NORMAL_INERT_POST_PUBLICATION_CHANGED_RETAIN_PARTIAL_NO_REISSUE')
        self._current()
        _commit_publication(prepared, own=False)
        self.ticket = prepared
        return self.ticket


def install_registered_issuer(owner):
    return NormalInertIssuer(owner)
