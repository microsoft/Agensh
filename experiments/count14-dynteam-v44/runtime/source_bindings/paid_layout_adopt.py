"""Metadata-only existing NativeLayout component, not a whole-owner restore.

capture_layout_section returns an UNSEALED candidate from an exact live layout.
hydrate_layout consumes only the pinned PaidColdCustody.control field, never a
caller-supplied section. A trusted normal whole-owner sealer does not yet exist:
production is therefore a fixed WAIT. Explicit OWN component qualification may
exercise the exact type/current/receipt path without claiming global authority.

No SQL, fresh NativeLayout constructor, mkdir, owner/mode repair, SDK/state/task
read, model gate release, process signal or request replay is performed here.
"""
from dataclasses import asdict
from pathlib import Path
from types import FunctionType, MethodType
import copy
import hashlib
import importlib
import os
import stat

from paid_cold_material import (ColdScope, birth, descriptor, digest, existing,
    need, nonexecuting, private_read, sha, stamp, strict, wire)

SOURCES = {
    'native_layout': '05a002bed1250bf98c5f9aab52f285bb2960dc3f5b058f1eead66b68ca698388',
    'native_beta_layout': '92a22647dc030a222f053b1ee6d6a0a0f673f617b49b234ca9382790a7be055a',
    'paid_cold_owner': '8a61182f40f57937ec86825d21da7784307d6ccae5c7f7656dd6e14274fb2c9a',
    'paid_cold_attach': '97b1d2dd121f0c2686de22059f6d8433bdaa825c16b00055a1b749030eb845c7',
    'paid_cold_material': '87f2537297188aef237669dd26d9e9ac0c851efcfb49138719375fa5ba1b61f5',
}
FRESH = 'NEW_LAYOUT_DURABLE_MODEL_GATES_HELD'
RESTORED = 'RESTORED_EXISTING_LAYOUT_DURABLE_MODEL_GATES_HELD'
SECTION = 'count14-native-layout-adoption-unsealed-candidate-v1'
RECEIPT = 'count14-native-layout-adoption-component-PUBLIC-v1'
PROOF = 'NATIVE_LAYOUT_PUBLIC_INODES.json'
SECTION_KEYS = {'schema', 'candidate_only', 'whole_cohort_cut_qualified', 'runtime_ready',
    'contract_sha256', 'source_pins', 'native_uid', 'old_owner', 'old_epoch', 'new_epoch',
    'original_proof', 'directories', 'previous_receipts'}
RECEIPT_KEYS = {'schema', 'contract_sha256', 'source_pins', 'native_uid',
    'old_owner', 'new_owner', 'old_epoch', 'new_epoch', 'original_proof',
    'directories_sha256', 'candidate_sha256', 'previous_receipt', 'protected_control_sha256',
    'handoff_sha256', 'OWN_component_only', 'runtime_ready', 'whole_cohort_cut_qualified',
    'requests_replayed', 'ledger_rewrites'}


def verify_sources():
    for name, pin in SOURCES.items():
        module = importlib.import_module(name)
        p = Path(module.__file__)
        need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and
             p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == pin,
             'PAID_LAYOUT_EXACT_ORIGINAL_SOURCE_PINS')
    return dict(SOURCES)


def public_read(row, *, home, expected_name):
    """One literal bounded PUBLIC metadata file; never arbitrary state input."""
    need(type(row) is dict and set(row) == {'identity', 'sha256'},
         'PAID_LAYOUT_EXACT_PUBLIC_METADATA_REFERENCE')
    p = existing(row['identity'])
    need(p == Path(home)/expected_name and p.parent.resolve() == p.parent,
         'PAID_LAYOUT_ONLY_ORIGINAL_LITERAL_PUBLIC_METADATA')
    s = p.lstat()
    need(s.st_uid == os.geteuid() and stat.S_IMODE(s.st_mode) == 0o400 and
         s.st_nlink == 1 and 0 < s.st_size <= 2*1024*1024,
         'PAID_LAYOUT_PUBLIC_METADATA_0400_OWNED_SINGLE_LINK_BOUNDED')
    token = lambda z: (z.st_dev,z.st_ino,z.st_uid,z.st_gid,z.st_mode,z.st_nlink,
                       z.st_size,z.st_mtime_ns,z.st_ctime_ns)
    fd = os.open(p, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        chunks, total = [], 0
        while True:
            chunk = os.read(fd, min(65536, 2*1024*1024+1-total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            need(total <= 2*1024*1024, 'PAID_LAYOUT_PUBLIC_METADATA_READ_LIMIT')
        raw = b''.join(chunks)
        b = os.fstat(fd)
        c = p.lstat()
        need(token(s) == token(a) == token(b) == token(c) and len(raw) == s.st_size,
             'PAID_LAYOUT_PUBLIC_METADATA_STABLE_SAME_FD')
    finally:
        os.close(fd)
    need(hashlib.sha256(raw).hexdigest() == sha(row['sha256']),
         'PAID_LAYOUT_PUBLIC_METADATA_RAW_PIN')
    return strict(raw)


def expected_layout(core, uid):
    """Original naming/alias functions; no filesystem mutation or scientific read."""
    from native_layout import native_names
    from native_beta_layout import native_aliases
    rows, bindings, paths = {}, {}, {}
    need(type(uid) is int and uid >= 0 and type(core.rows) is dict and core.rows,
         'PAID_LAYOUT_EXACT_NATIVE_UID_AND_COHORT')
    for t, row in core.rows.items():
        root = Path(row['root'])
        need(root.is_absolute() and root.resolve() == root and root.is_dir(),
             'PAID_LAYOUT_CANONICAL_ORIGINAL_TRACK_ROOT')
        data = root/'native-data'
        profile, org = native_names(t)
        base = data/profile
        paths[str(data)] = (os.geteuid(), 0o700)
        paths[str(base)] = (os.geteuid(), 0o755)
        for n in ('agents','acp','trajectories','workspaces'):
            paths[str(base/n)] = (os.geteuid(), 0o755)
        roles = {}
        aliases = native_aliases(row['arm'])
        need(set(aliases) == set(row['roles']), 'PAID_LAYOUT_COMPLETE_NATIVE_ROLE_CATALOGUE')
        for role, alias in aliases.items():
            account = org+'-'+alias['native_short']
            state, archive = base/'agents'/account, base/'trajectories'/account
            acp, workspace = base/'acp'/account, base/'workspaces'/account
            roles[role] = dict(agent_state=str(state),archive_root=str(archive),
                               acp_root=str(acp),workspace=str(workspace))
            bindings[t,role] = dict(archive_root=str(archive),
                native_turn_metadata=str(acp/'current-turn.json'),owner_uid=os.geteuid())
            for p in (state,acp,workspace):
                paths[str(p)] = (uid, 0o755)
            paths[str(archive)] = (os.geteuid(), 0o700)
        rows[t] = dict(data_root=str(data),profile=profile,org=org,profile_root=str(base),roles=roles)
    return rows, bindings, paths


def verify_directories(core, uid, directories):
    rows, bindings, expected = expected_layout(core, uid)
    need(type(directories) is list and len(directories) == len(expected) and
         all(type(x) is dict for x in directories) and
         [x.get('path') for x in directories] == sorted(expected),
         'PAID_LAYOUT_EXACT_COMPLETE_SORTED_DIRECTORY_INVENTORY')
    identities = {}
    for row in directories:
        p = existing(row, directory=True)
        own, mode = expected[str(p)]
        need(row['uid'] == own and row['mode'] == mode,
             'PAID_LAYOUT_ORIGINAL_DIRECTORY_OWNER_AND_MODE_NOT_REPAIRED')
        identities[str(p)] = (row['device'],row['inode'],row['uid'],row['mode'])
    return rows, bindings, identities


def verify_proof(core, reference, directories):
    value = public_read(reference, home=core.home, expected_name=PROOF)
    need(type(value) is dict and set(value) == {'schema','owner_pid','owner_start_ticks',
         'owner_boot_id','contract_sha256','directories'} and
         value['schema'] == 'count14-native-layout-public-v1' and
         value['contract_sha256'] == digest(core.contract) and
         value['directories'] == [dict(path=x['path'],dev=x['device'],inode=x['inode'],
                                      uid=x['uid'],mode=x['mode']) for x in directories],
         'PAID_LAYOUT_ORIGINAL_PROOF_EXACT_COMPLETE_DIRECTORY_IDENTITY')
    return value


def receipt_name(epoch):
    need(type(epoch) is int and epoch >= 2, 'PAID_LAYOUT_RECEIPT_EPOCH')
    return 'NATIVE_LAYOUT_ADOPTION_EPOCH_'+str(epoch)+'_PUBLIC.json'


def verify_chain(core, section):
    """Initial proof anchors owner1; later receipts anchor the immediately prior owner."""
    proof = verify_proof(core, section['original_proof'], section['directories'])
    prior = section['previous_receipts']
    need(type(prior) is list and len(prior) <= 64,
         'PAID_LAYOUT_BOUNDED_APPEND_ONLY_RECEIPT_CHAIN')
    old = birth(section['old_owner'])
    previous, expected_old, expected_epoch = None, None, None
    for reference in prior:
        identity = reference.get('identity', {}) if type(reference) is dict else {}
        name = Path(identity.get('path','')).name
        # A filename can select only this one metadata receipt pattern under home.
        prefix, suffix = 'NATIVE_LAYOUT_ADOPTION_EPOCH_', '_PUBLIC.json'
        need(name.startswith(prefix) and name.endswith(suffix), 'PAID_LAYOUT_CHAIN_LITERAL_RECEIPT_NAME')
        number = name[len(prefix):-len(suffix)]
        need(number.isascii() and number.isdecimal() and str(int(number)) == number,
             'PAID_LAYOUT_CHAIN_CANONICAL_EPOCH_NAME')
        value = public_read(reference,home=core.home,expected_name=receipt_name(int(number)))
        need(type(value) is dict and set(value) == RECEIPT_KEYS and value['schema'] == RECEIPT and
             value['contract_sha256'] == section['contract_sha256'] and
             value['source_pins'] == section['source_pins'] and
             value['native_uid'] == section['native_uid'] and
             value['original_proof'] == section['original_proof'] and
             value['directories_sha256'] == digest(section['directories']) and
             value['previous_receipt'] == previous and value['new_epoch'] == int(number) and
             type(value['old_epoch']) is int and value['new_epoch'] == value['old_epoch']+1 and
             value['runtime_ready'] is False and value['whole_cohort_cut_qualified'] is False and
             value['OWN_component_only'] is True and value['requests_replayed'] == value['ledger_rewrites'] == 0,
             'PAID_LAYOUT_RECEIPT_CHAIN_EXACT_BINDINGS_NO_RUNTIME_UPGRADE')
        before, after = birth(value['old_owner']), birth(value['new_owner'])
        need(before != after and before.uid == after.uid == os.geteuid(),
             'PAID_LAYOUT_CHAIN_GENUINE_DISTINCT_SAME_UID_OWNERS')
        if expected_old is None:
            need((proof['owner_pid'],proof['owner_start_ticks'],proof['owner_boot_id']) ==
                 (before.pid,before.start_ticks,before.boot_id), 'PAID_LAYOUT_ORIGINAL_PROOF_INITIAL_OWNER_ANCHOR')
        else:
            need(before == expected_old and value['old_epoch'] == expected_epoch,
                 'PAID_LAYOUT_RECEIPT_PREVIOUS_NEW_OWNER_AND_EPOCH_NOT_INITIAL_OWNER')
        for key in ('candidate_sha256','protected_control_sha256','handoff_sha256'):
            sha(value[key])
        previous, expected_old, expected_epoch = copy.deepcopy(reference), after, value['new_epoch']
    if expected_old is None:
        need((proof['owner_pid'],proof['owner_start_ticks'],proof['owner_boot_id']) ==
             (old.pid,old.start_ticks,old.boot_id), 'PAID_LAYOUT_FIRST_SOURCE_EQUALS_ORIGINAL_PROOF_OWNER')
    else:
        need(old == expected_old and section['old_epoch'] == expected_epoch,
             'PAID_LAYOUT_SOURCE_EQUALS_LAST_RECEIPT_NEW_OWNER_NOT_INITIAL_PROOF')
    return previous


def capture_layout_section(layout, *, old_epoch, new_epoch):
    """Candidate only. Never seals a cohort, authorizes TERM, or releases a gate."""
    from native_layout import NativeLayout
    from native_peer_registry import process_birth
    verify_sources()
    need(type(layout) is NativeLayout and layout.state in (FRESH,RESTORED) and
         layout.owner == process_birth(os.getpid()) and
         type(old_epoch) is int and old_epoch >= 1 and type(new_epoch) is int and new_epoch == old_epoch+1,
         'PAID_LAYOUT_CAPTURE_EXACT_LIVE_LAYOUT_AND_SUCCESSOR_EPOCH')
    core = layout.core
    need(digest(core.contract) == layout.contract_sha256 and getattr(core,'native_layout',None) is layout,
         'PAID_LAYOUT_CAPTURE_ORIGINAL_SAME_CORE_CONTRACT')
    if layout.state == RESTORED:
        custody = getattr(core,'paid_cold_restore_custody',None)
        need(held_custody(custody) is core and custody.owner.layout is layout,
             'PAID_LAYOUT_CAPTURE_RESTORED_EXACT_CUSTODY_CHAIN')
    rows, bindings, paths = expected_layout(core,layout.uid)
    need(layout.rows == rows and layout.archive_bindings == bindings and set(layout.identities) == set(paths),
         'PAID_LAYOUT_CAPTURE_COMPLETE_ORIGINAL_ROWS_AND_BINDINGS')
    for t in rows:
        need(layout.current(t) == rows[t], 'PAID_LAYOUT_CAPTURE_ORIGINAL_CURRENT_EACH_TRACK')
    directories = [descriptor(p) for p in sorted(paths)]
    _,_,identities = verify_directories(core,layout.uid,directories)
    need(layout.identities == identities, 'PAID_LAYOUT_CAPTURE_CURRENT_IDENTITY_INVENTORY')
    p = core.home/PROOF
    # Read only this PUBLIC proof; never discover or hash SDK/scientific files.
    s = p.lstat()
    need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and
         stat.S_ISREG(s.st_mode) and s.st_uid == os.geteuid() and
         stat.S_IMODE(s.st_mode) == 0o400 and s.st_nlink == 1 and
         0 < s.st_size <= 2*1024*1024,
         'PAID_LAYOUT_CAPTURE_ONLY_LITERAL_BOUNDED_PUBLIC_PROOF')
    token = lambda z: (stamp(z),z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_nlink)
    fd = os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as source:
        a = os.fstat(source.fileno())
        raw = source.read(2*1024*1024+1)
        b = os.fstat(source.fileno())
    need(token(s) == token(a) == token(b) == token(p.lstat()) and len(raw) == s.st_size,
         'PAID_LAYOUT_CAPTURE_PUBLIC_PROOF_STABLE_SAME_FD')
    proof = dict(identity=descriptor(p),sha256=hashlib.sha256(raw).hexdigest())
    section = dict(schema=SECTION,candidate_only=True,whole_cohort_cut_qualified=False,runtime_ready=False,
        contract_sha256=layout.contract_sha256,source_pins=dict(SOURCES),native_uid=layout.uid,
        old_owner=asdict(layout.owner),old_epoch=old_epoch,new_epoch=new_epoch,
        original_proof=proof,directories=directories,
        previous_receipts=copy.deepcopy(getattr(layout,'paid_layout_receipts',[])))
    verify_chain(core,section)
    return section


def restored_current():
    from native_layout import NativeLayout
    original = NativeLayout.current
    code = original.__code__
    need(code.co_consts.count(FRESH) == 1 and RESTORED not in code.co_consts,
         'PAID_LAYOUT_ONE_ORIGINAL_CURRENT_STATE_CONSTANT')
    constants = tuple(RESTORED if x == FRESH else x for x in code.co_consts)
    private = code.replace(co_consts=constants)
    need(private.co_code == code.co_code and
         private.replace(co_consts=code.co_consts) == code,
         'PAID_LAYOUT_CURRENT_BYTECODE_UNCHANGED_INVERSE_CONSTANT_EQUALITY')
    fn = FunctionType(private,original.__globals__,original.__name__,original.__defaults__,original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn


def held_custody(custody):
    from paid_cold_owner import PaidColdCustody
    from paid_cold_attach import AttachedPair
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    from native_peer_registry import process_birth
    need(type(custody) is PaidColdCustody and type(custody.scope) is ColdScope and
         custody.birth == process_birth(os.getpid()) and
         custody.state == 'PAID_COLD_EXACT_TYPED_CUSTODY_HELD_RUNTIME_UNHYDRATED_WAIT' and
         type(custody.pair) is AttachedPair and type(custody.owner) is NativeColdOwner and
         type(custody.owner.core) is OriginalRelayCore,
         'PAID_LAYOUT_EXACT_CURRENT_TYPED_HELD_CUSTODY')
    core = custody.owner.core
    need(core.paid_cold_restore_custody is custody and custody.owner.paid_cold_restore_custody is custody and
         core.ledger is custody.pair.ledger and core.queue is custody.pair.queue and
         core.paid_new_owner_birth == custody.birth and core.control is None and
         core.scientific_activation_qualified is False and digest(core.contract) == custody.scope.canonical_sha256 and
         digest(custody.control) == custody.control_sha256 and
         digest(core.paid_restored_control_candidate) == custody.control_sha256,
         'PAID_LAYOUT_PINNED_PROTECTED_CONTROL_SAME_CUSTODY_NO_CALLER_REPLACEMENT')
    need(len(custody.pair.lock_fds) == len(custody.pair.control_locks)+1,
         'PAID_LAYOUT_RETAINED_ORIGINAL_CONTROL_LOCK_FDS')
    paths = [core.home/'full-affinity-domain-control-v1',*custody.pair.control_locks]
    for fd, path in zip(custody.pair.lock_fds,paths):
        a,b = os.fstat(fd),Path(path).lstat()
        need((a.st_dev,a.st_ino) == (b.st_dev,b.st_ino) and Path(path).resolve() == Path(path),
             'PAID_LAYOUT_SAME_RETAINED_LOCK_FD_PATH_IDENTITY')
        # Only this own registered FD's public lock controls, no global scan.
        controls = [line.split() for line in Path('/proc/self/fdinfo',str(fd)).read_text().splitlines()
                    if line.startswith('lock:')]
        need(any(len(row) >= 7 and row[2:5] == ['FLOCK','ADVISORY','WRITE'] and
                 row[5] == str(os.getpid()) for row in controls),
             'PAID_LAYOUT_OWN_CURRENT_EXCLUSIVE_FLOCK_STILL_HELD')
    return core


def hydrate_layout(custody):
    """No supplied section/seal arguments; missing normal production seal WAITs."""
    from native_layout import NativeLayout
    from paid_cold_attach import refuse_runtime
    verify_sources()
    core = held_custody(custody)
    # No normal whole-owner producer has a pinned schema/source yet. Neither a
    # caller boolean nor the current candidate control can impersonate one.
    need(custody.scope.qualification_only is True,
         'PAID_LAYOUT_WAIT_TRUSTED_NORMAL_WHOLE_OWNER_SEAL_NOT_IMPLEMENTED')
    need(all(t.startswith('OWN-') and any(part.startswith('OWN-') for part in Path(r['root']).parts)
             for t,r in core.rows.items()), 'PAID_LAYOUT_COMPONENT_QUALIFICATION_ONLY_OWN_ROOTS')
    section = custody.control.get('native_layout_adoption')
    need(type(section) is dict and set(section) == SECTION_KEYS and section['schema'] == SECTION and
         section['candidate_only'] is True and section['runtime_ready'] is False and
         section['whole_cohort_cut_qualified'] is False and section['source_pins'] == SOURCES and
         section['contract_sha256'] == custody.scope.canonical_sha256 and
         section['old_owner'] == core.paid_old_owner_birth,
         'PAID_LAYOUT_MISSING_OR_UNTRUSTED_PROTECTED_LAYOUT_SECTION_WAIT')
    need(custody.owner.layout is None and not hasattr(core,'native_layout'),
         'PAID_LAYOUT_ONE_NEW_ADOPTION_NO_EXISTING_LAYOUT_REPLACEMENT')
    old = birth(section['old_owner'])
    need(old != custody.birth and old.uid == custody.birth.uid and nonexecuting(old,custody.birth),
         'PAID_LAYOUT_OLD_OWNER_ENDED_SAME_UID_NO_REQUEST_CANCELLATION')
    intent, _ = private_read(custody.intent['path'],custody.intent['sha256'])
    need(Path(custody.intent['path']) == core.home/'paid-cold-restore-control-v1/consume-intent.json' and
         intent['old_owner_sha256'] == digest(section['old_owner']) and intent['new_owner'] == asdict(custody.birth) and
         intent['old_epoch'] == section['old_epoch'] and intent['new_epoch'] == section['new_epoch'] and
         intent['handoff_sha256'] == custody.handoff_sha256,
         'PAID_LAYOUT_ORIGINAL_CONSUME_INTENT_SUCCESSOR_EPOCH_AND_BIRTH')
    rows, bindings, identities = verify_directories(core,section['native_uid'],section['directories'])
    previous = verify_chain(core,section)
    layout = NativeLayout.__new__(NativeLayout) # never fresh __init__ or _mkdir
    layout.core,layout.uid,layout.owner = core,section['native_uid'],custody.birth
    layout.contract_sha256,layout.state = section['contract_sha256'],RESTORED
    layout.rows,layout.archive_bindings,layout.identities = rows,bindings,identities
    layout.current = MethodType(restored_current(),layout)
    layout._mkdir = MethodType(refuse_runtime,layout) # no fresh mutation authority
    held_custody(custody)
    verify_chain(core,section)
    verify_directories(core,section['native_uid'],section['directories'])
    need(nonexecuting(old,custody.birth), 'PAID_LAYOUT_OLD_OWNER_POST_METADATA_RECHECK')
    value = dict(schema=RECEIPT,contract_sha256=section['contract_sha256'],source_pins=dict(SOURCES),
        native_uid=section['native_uid'],old_owner=section['old_owner'],new_owner=asdict(custody.birth),
        old_epoch=section['old_epoch'],new_epoch=section['new_epoch'],original_proof=section['original_proof'],
        directories_sha256=digest(section['directories']),candidate_sha256=digest(section),previous_receipt=previous,
        protected_control_sha256=custody.control_sha256,handoff_sha256=custody.handoff_sha256,
        OWN_component_only=True,runtime_ready=False,whole_cohort_cut_qualified=False,
        requests_replayed=0,ledger_rewrites=0)
    path = core.home/receipt_name(section['new_epoch'])
    raw = wire(value)
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    with os.fdopen(fd,'wb') as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    fd = os.open(core.home,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    reference = dict(identity=descriptor(path),sha256=hashlib.sha256(raw).hexdigest())
    public_read(reference,home=core.home,expected_name=path.name)
    layout.paid_layout_receipts = [*copy.deepcopy(section['previous_receipts']),reference]
    core.native_layout,custody.owner.layout = layout,layout
    for t in rows:
        layout.current(t)
    # custody.state/gaps, all quarantine and all runtime/graph readiness remain unchanged.
    return layout
