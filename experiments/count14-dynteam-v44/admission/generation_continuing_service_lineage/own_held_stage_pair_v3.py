"""OWN real H stage on the original metadata pair's ALREADY held locks.

No production path, second lock acquisition, original-registry forgery, writer,
DB migration, request, model, task access or next T.
Lock vectors are canonicalized from original P tuples to JSON lists only;
every label, order, path and descriptor field remains exactly equal. The original F OWN source
verifier keeps every metadata/DB guard. Four custody and three exact paired-queue context statements change
in a private clone: borrow real pair FDs, compare their exact locks, retain the
verified source locally, and never close borrowed FDs on an exception.
"""
from pathlib import Path
from types import MethodType, SimpleNamespace
from dataclasses import asdict
import ast
import copy
import hashlib
import importlib
import inspect
import os
import textwrap
import threading

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth
import normal_inert_cut as T
import metadata_inert_pair as P
import financial_runtime_source_control as F
import normal_held_financial_writer as H
import staged_financial_runtime as S
import durable_service_source_controls as C

PINS = {
    'normal_inert_cut': 'aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262',
    'metadata_inert_pair': '83b2662daef394a6c3bb9cbfa46fc15a49c4382df7db5c963ec89a1f61b853da',
    'financial_runtime_source_control': '5d7aedc421df71583d55ec6ffc32cd80389c1f944ed93c3dcad99b433d38f906',
    'normal_held_financial_writer': '686247ad8d2ca768abf1dc0085ac4a18e58419f37e2bceb61b152d8f8b413261',
    'staged_financial_runtime': '62de21eed76372cbe6d6721da10891d0a86e4cfc65dbbdbbf22294b3e49baba5',
    'durable_service_source_controls': 'fe5cbbbb186e4d9049895f68c32529d8237d6ffbeda35d03b8ed15a0482f0b83',
}
_SEAL = object()
_REG = {}
_ATTEMPTS = {}


def verify_sources():
    for name, pin in PINS.items():
        p = Path(importlib.import_module(name).__file__)
        M.need(p.is_absolute() and p.resolve() == p and not p.is_symlink()
               and not p.stat().st_mode & 0o022 and hashlib.sha256(p.read_bytes()).hexdigest() == pin,
               'OWN_STAGE_PAIR_EXACT_FROZEN_ORIGINAL_SOURCES')
    H.verify_sources()


def _budget(value):
    M.need(type(value) is ReadBudget, 'OWN_STAGE_PAIR_ORIGINAL_FINITE_BUDGET')
    value.check()


def _proof(owner, ticket, budget):
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    _budget(budget)
    verify_sources()
    M.need(type(owner) is NativeColdOwner and type(owner.core) is OriginalRelayCore
           and owner.core.qualification_only is True and type(ticket) is T.OWNNormalInertTicket,
           'OWN_STAGE_PAIR_ONLY_ORIGINAL_OWN_METADATA_OWNER_AND_TYPED_T')
    proof = P.verify_OWN_registered_pair(owner, read_budget=budget)
    cap = T.verify_OWN_inert_ticket(ticket, owner=owner, read_budget=budget)
    M.need(proof.new_owner_birth == cap.new_owner_birth == process_birth(os.getpid())
           and proof.source_birth == cap.old_owner_birth and proof.owner is owner,
           'OWN_STAGE_PAIR_SAME_ORIGINAL_T_AND_THREE_REAL_LOCKS')
    return proof, cap


def _borrow_loader(pair):
    original = ast.parse(textwrap.dedent(inspect.getsource(F.load_OWN_source)))
    tree = copy.deepcopy(original)
    fn = tree.body[0]
    changes = []

    def replace(seq, index, replacement):
        before = copy.deepcopy(seq[index])
        replacement = ast.copy_location(replacement, seq[index])
        seq[index] = replacement
        changes.append((replacement, before))

    # Native original cores legitimately use final-queue; the standalone
    # F OWN fixture used queue. Accept only the ORIGINAL registered T/P exact
    # queue domain, never an arbitrary caller path or a parent directory.
    queue_context=[]
    for node in list(ast.walk(fn)):
        if isinstance(node,ast.Compare):
            for i,value in enumerate(list(node.comparators)):
                expression=ast.unparse(value)
                if expression=="home / 'queue'":
                    replace(node.comparators,i,ast.parse("Path(_held_pair.material['queue_home']['path'])",mode='eval').body)
                    queue_context.append('home')
                elif expression=="home / 'queue/queue.sqlite'":
                    replace(node.comparators,i,ast.parse("Path(_held_pair.material['queue_database']['path'])",mode='eval').body)
                    queue_context.append('database')
        elif isinstance(node,ast.Call)and ast.unparse(node.func)=='M.descriptor'and len(node.args)==1 and ast.unparse(node.args[0])=="home / 'queue/owner.lock'":
            replace(node.args,0,ast.parse("Path(_held_pair.material['queue_home']['path'])/'owner.lock'",mode='eval').body)
            queue_context.append('lock')
    M.need(sorted(queue_context)==['database','home','lock'],
           'OWN_STAGE_PAIR_THREE_EXACT_ORIGINAL_QUEUE_STORAGE_CONTEXT_SITES')

    fds = [i for i, n in enumerate(fn.body) if isinstance(n, ast.Assign)
           and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'fds']
    M.need(len(fds) == 1 and ast.unparse(fn.body[fds[0]].value) == '[]',
           'OWN_STAGE_PAIR_ORIGINAL_EMPTY_OWN_FD_INVENTORY_SITE')
    replace(fn.body, fds[0], ast.parse('fds=list(_held_pair.lock_fds)').body[0])
    blocks = [n for n in fn.body if isinstance(n, ast.Try)]
    M.need(len(blocks) == 1, 'OWN_STAGE_PAIR_ONE_ORIGINAL_FD_CUSTODY_TRY')
    block = blocks[0]
    opens = [i for i, n in enumerate(block.body) if isinstance(n, ast.For) and ast.unparse(n.iter) == 'expected']
    M.need(len(opens) == 1, 'OWN_STAGE_PAIR_ONE_ORIGINAL_LOCK_ACQUISITION_BLOCK')
    replace(block.body, opens[0], ast.parse(
        "M.need(expected==[list(row) for row in _paired_locks],'OWN_STAGE_PAIR_EXACT_ALREADY_HELD_LOCKS_NOT_NEW_AUTHORITY')").body[0])
    stores = [i for i, n in enumerate(block.body) if isinstance(n, ast.Assign)
              and len(n.targets) == 1 and isinstance(n.targets[0], ast.Subscript)
              and ast.unparse(n.targets[0].value) == '_OWN_RECEIVERS']
    M.need(len(stores) == 1, 'OWN_STAGE_PAIR_ONE_ORIGINAL_OWN_RECEIVER_CUSTODY_STORE')
    replace(block.body, stores[0], ast.parse('_retain_verified_source(value)').body[0])
    M.need(len(block.handlers) == 1 and isinstance(block.handlers[0].body[0], ast.For)
           and ast.unparse(block.handlers[0].body[0].iter) == 'fds',
           'OWN_STAGE_PAIR_ONE_ORIGINAL_EXCEPTION_FD_CLOSE_BLOCK')
    replace(block.handlers[0].body, 0, ast.Pass())
    reverse = copy.deepcopy(tree)
    for changed, before in changes:
        hits = [n for n in ast.walk(reverse) if type(n) is type(changed)
                and getattr(n, 'lineno', None) == changed.lineno
                and getattr(n, 'col_offset', None) == changed.col_offset
                and ast.dump(n, include_attributes=False) == ast.dump(changed, include_attributes=False)]
        M.need(len(hits) == 1, 'OWN_STAGE_PAIR_UNIQUE_CUSTODY_STATEMENT_INVERSE')
        # Replace the node through its parent, including type changes.
        for parent in ast.walk(reverse):
            for name, value in ast.iter_fields(parent):
                if type(value) is list:
                    for i, node in enumerate(value):
                        if node is hits[0]:
                            value[i] = copy.deepcopy(before)
    M.need(len(changes) == 7 and ast.dump(reverse, include_attributes=False) == ast.dump(original, include_attributes=False),
           'OWN_STAGE_PAIR_ALL_OTHER_ORIGINAL_F_FILE_DB_BIRTH_NAMESPACE_GUARDS_UNCHANGED')
    retained = []
    namespace = {}
    globals_ = dict(vars(F), _held_pair=pair, _paired_locks=pair.control_lock_records,
                    _retain_verified_source=retained.append)
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':original-OWN-verifier-borrowed-pair-custody', 'exec'),
         globals_, namespace)
    return namespace['load_OWN_source'], retained


def prepare_OWN_stage(owner, *, ticket, services_reference, financial_reference,
                      components_sha256, read_budget):
    proof, cap = _proof(owner, ticket, read_budget)
    M.need(id(owner) not in _ATTEMPTS, 'OWN_STAGE_PAIR_SINGLE_STAGE_ATTEMPT_RETAIN_PARTIAL')
    attempt = dict(owner=owner, phase='VERIFYING_OWN_SOURCE_ON_EXISTING_PAIR')
    _ATTEMPTS[id(owner)] = attempt
    try:
        pair = owner.core.metadata_inert_pair
        loader, retained = _borrow_loader(pair)
        source = loader(financial_reference, read_budget=read_budget)
        M.need(retained == [source] and type(source) is F.VerifiedFinancialRuntimeSource and source.OWN is True
               and id(source) not in F._OWN_RECEIVERS and source.old_owner_birth == cap.old_owner_birth
               and source.new_owner_birth == cap.new_owner_birth and source.contract_sha256 == cap.contract_sha256
               and source._body['locks'] == [list(row) for row in pair.control_lock_records],
               'OWN_STAGE_PAIR_ORIGINAL_F_VERIFIED_SOURCE_BORROWED_NOT_FAKE_FD_REGISTRY')
        for key in ('owner_home', 'ledger_home', 'ledger_database', 'queue_home', 'queue_database', 'full_used_directory'):
            M.need(source._body['storage'][key] == proof.material[key],
                   'OWN_STAGE_PAIR_SOURCE_T_PAIR_SAME_CANONICAL_STORAGE')
        services = C.verify_OWN_reference(services_reference, owner=owner, ticket=ticket, read_budget=read_budget)
        home = owner.core.home
        row, _ = M.private_read(home / 'OWN-normal-held-components.json', components_sha256)
        M.need(row['schema'] == 'OWN_NORMAL_HELD_FINANCIAL_COMPONENTS_V1' and row['OWN'] is True
               and row['source_reference'] == dict(path=financial_reference.path, sha256=financial_reference.sha256)
               and row['old_owner_birth'] == asdict(source.old_owner_birth)
               and row['contract_sha256'] == source.contract_sha256,
               'OWN_STAGE_PAIR_ACTUAL_SOURCE_COMPONENTS_NOT_CALLER_STAGE_METADATA')
        context = SimpleNamespace(OWN=True, old_owner_birth=source.old_owner_birth,
            new_owner_birth=source.new_owner_birth, contract=proof.material['contract'], rows=owner.core.rows,
            owner_home=home, ledger_home=owner.core.ledger.home, queue_home=owner.core.queue.home,
            ledger_database=cap.ledger_database, queue_database=cap.queue_database,
            ledger_db=H._BindingRO(owner.core.ledger.db), queue_db=owner.core.queue.db,
            lock_fds=tuple(pair.lock_fds), source_owner=owner, source_ticket=ticket,
            services_reference=services_reference, services_cap=services, normal_components=row['components'])
        stage = H._private_make()(context, source.controls['normal_financial_runtime_controls'], read_budget=read_budget)
        H._GRAPHS[id(stage)] = dict(stage=stage, OWN=True, OWN_source=source, context=context,
            connections=[], writer=None, financial_before=F._db_controls(
                Path(cap.ledger_database['path']), Path(cap.queue_database['path']), read_budget))
        _REG[id(stage)] = dict(stage=stage, owner=owner, ticket=ticket, services=services, source=source,
            reference=financial_reference, pair=pair, birth=proof.new_owner_birth,
            thread=threading.get_ident(), seal=_SEAL, closed=False)
        current_OWN_stage(stage, read_budget=read_budget)
        attempt.update(phase='ACTUAL_ORIGINAL_HELD_STAGE_CREATED_READONLY', stage=stage)
        return stage
    except BaseException as error:
        attempt.update(phase='PARTIAL_RETAINED_NO_RETRY', failure_type=type(error).__name__)
        raise


def current_OWN_stage(stage, *, read_budget):
    _budget(read_budget)
    r = _REG.get(id(stage))
    M.need(type(r) is dict and r['stage'] is stage and r['seal'] is _SEAL and not r['closed']
           and r['birth'] == process_birth(os.getpid()) and r['thread'] == threading.get_ident(),
           'OWN_STAGE_PAIR_ACTUAL_REGISTERED_STAGE_BIRTH_THREAD')
    proof, cap = _proof(r['owner'], r['ticket'], read_budget)
    record = H._same(stage, read_budget, own=True)
    M.need(record['OWN_source'] is r['source'] and record['writer'] is None
           and stage.context.lock_fds == tuple(r['pair'].lock_fds)
           and stage.core is not r['owner'].core and stage.core.home == r['owner'].core.home
           and stage.core.gate.closed and stage.core.gate.startup_held == set(stage.core.rows)
           and not stage.core.gate.waiters and stage.original_source_method_semantics_equal,
           'OWN_STAGE_PAIR_ORIGINAL_H_SEMANTIC_GRAPH_GATE_SOURCE_LOCKS_REMAIN_HELD')
    from budget import Ledger
    from final_queue import FinalQueue
    for instance, cls in ((stage.ledger, Ledger), (stage.queue, FinalQueue)):
        for name in vars(cls):
            if name.startswith('__') or not callable(getattr(cls, name, None)):
                continue
            method = getattr(instance, name)
            M.need(type(method) is MethodType and method.__self__ is instance and method.__func__ is S._refuse,
                   'OWN_STAGE_PAIR_ALL_FINANCE_QUEUE_METHODS_STILL_ORIGINAL_H_QUARANTINE')
    return r


def close_OWN_stage_after_services(stage, *, read_budget):
    r = current_OWN_stage(stage, read_budget=read_budget)
    for key in ('system_health', 'resource_producer'):
        service = getattr(stage.core, key, None)
        M.need(service is None or service.accepting is False and service.physical_clear(),
               'OWN_STAGE_PAIR_CLOSE_ONLY_AFTER_ACTUAL_OWN_CHILDREN_PHYSICALLY_CLEAR')
    M.need(H._GRAPHS[id(stage)]['writer'] is None, 'OWN_STAGE_PAIR_NEVER_CLOSE_AN_OWN_WRITER_HERE')
    H._GRAPHS.pop(id(stage))
    S._STAGED.pop(id(stage))
    r['closed'] = True  # borrowed DBs/FDs still belong to ORIGINAL metadata pair
