"""Explicit generation ports for ORIGINAL production services/history controls.

Original classes, seals, registries, pre/post source/financial/retirement,
history parsing, new-birth and three-lock checks remain. No module is patched,
no old leaf is rewritten and OWN is not relabeled production. No live service,
sampler, SDK, writer, science release or whole-runtime authority is provided.
"""
from dataclasses import asdict
from pathlib import Path
from types import FunctionType
import ast
import copy
import hashlib
import importlib
import inspect
import os
import re
import stat
import textwrap

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth
import normal_inert_cut as T
import generation_inert_cut as G
import generation_financial_runtime_source_v2 as GF
import durable_service_source_controls as D
import retired_system_history as H
import retired_resource_history as R

PINS = {
    'generation_inert_cut': '0d23b664bf8dcfae949c11877fd3a6160d134b1a3a1bcc7f00bd2c660e0d73c5',
    'generation_financial_runtime_source_v2': 'd30309aa7c29b6c61b550d9f3a463f0e33913d70bd96c2e1528d9c98e0bdc162',
    'durable_service_source_controls': 'fe5cbbbb186e4d9049895f68c32529d8237d6ffbeda35d03b8ed15a0482f0b83',
    'retired_system_history': '448802312193a2ef4b5f3fe2b35ff2d65a3ffef8c3cc158c1f46b37b1a3d3ed5',
    'retired_resource_history': 'b756439360673e2e0cf96d7e0e3ae7f546cfd43fd7862e437894fc85cd3ade97',
}
SERVICE_LEAF = 'normal-retired-services-source-generations-v1'
HISTORY_LEAF = 'normal-retired-system-history-source-generations-v1'
SCHEMA = 'count14-original-service-history-explicit-generation-port-v1'
KEY = re.compile(r'[1-9][0-9]*-[1-9][0-9]*-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def _budget(value):
    M.need(type(value) is ReadBudget, 'GENERATION_SERVICES_ORIGINAL_FINITE_METADATA_BUDGET')
    value.check()


def _production(own):
    M.need(own is False, 'GENERATION_SERVICES_PRODUCTION_PORT_NEVER_ACCEPTS_OWN')


def verify_sources():
    for name, pin in PINS.items():
        path = Path(importlib.import_module(name).__file__)
        s = path.lstat()
        M.need(path.is_absolute() and path.resolve() == path and stat.S_ISREG(s.st_mode)
               and s.st_nlink == 1 and not s.st_mode & 0o022
               and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
               'GENERATION_SERVICES_FROZEN_ORIGINAL_SOURCE_PINS')
    GF.verify_sources()
    GF._original_functions(D, ('verify_sources', '_self_pin', '_budget', '_save', '_complete',
        '_live_source_cap', 'publish_source', '_reference', '_read_complete', '_validate_controls',
        '_verified', '_verify_common'))
    GF._original_functions(H, ('verify_sources', '_self_pin', '_publish', '_reference', '_read',
                               '_read_bound', 'private_directory', 'control'))
    GF._original_functions(R, ('verify_sources', '_read', '_read_bound', '_control', '_directory'))
    D.verify_sources(); H.verify_sources(); R.verify_sources()
    path = Path(__file__)
    s = path.lstat()
    M.need(path.is_absolute() and path.resolve() == path and stat.S_ISREG(s.st_mode)
           and s.st_nlink == 1 and not s.st_mode & 0o022,
           'GENERATION_SERVICES_CANONICAL_FROZEN_SELF')
    return dict(PINS)


def _ports(original, changes, bindings):
    """Fixed expression sites, exact counts and complete reverse-AST equality."""
    M.need(type(original) is FunctionType, 'GENERATION_SERVICES_EXACT_ORIGINAL_FUNCTION_TYPE')
    initial = ast.parse(textwrap.dedent(inspect.getsource(original)))
    tree = copy.deepcopy(initial)
    def replace(root, before, after, count):
        old, new = ast.parse(before, mode='eval').body, ast.parse(after, mode='eval').body
        hits = []
        class Change(ast.NodeTransformer):
            def generic_visit(self, node):
                if ast.dump(node) == ast.dump(old):
                    hits.append(True)
                    return ast.copy_location(copy.deepcopy(new), node)
                return super().generic_visit(node)
        value = Change().visit(root)
        M.need(len(hits) == count, 'GENERATION_SERVICES_EXACT_ORIGINAL_EXPRESSION_COUNTS')
        return value
    for old, new, count in changes:
        tree = replace(tree, old, new, count)
    inverse = copy.deepcopy(tree)
    for old, new, count in reversed(changes):
        inverse = replace(inverse, new, old, count)
    M.need(ast.dump(inverse) == ast.dump(initial),
           'GENERATION_SERVICES_ALL_OTHER_ORIGINAL_AST_PREDICATES_UNCHANGED')
    namespace = dict(original.__globals__, **bindings)
    local = {}
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':original-explicit-expression-ports', 'exec'), namespace, local)
    return local[original.__name__]


def _reference_parent(path, own, leaf):
    _production(own)
    return path.parent.parent.name == leaf and KEY.fullmatch(path.parent.name) is not None


def load_service_reference(path, sha256):
    verify_sources()
    fn = _ports(D._reference,
        [('p.parent.name == (OWN_LEAF if own else LEAF)', '_reference_parent(p, own, _leaf)', 1)],
        dict(_reference_parent=_reference_parent, _leaf=SERVICE_LEAF))
    return fn(path, sha256, own=False)  # Original UNVERIFIED reference class/seal.


def load_system_history_reference(path, sha256):
    verify_sources()
    fn = _ports(H._reference,
        [('p.parent.name == (OWN_LEAF_NAME if own else LEAF_NAME)', '_reference_parent(p, own, _leaf)', 1)],
        dict(_reference_parent=_reference_parent, _leaf=HISTORY_LEAF))
    return fn(path, sha256, own=False)  # Original UNVERIFIED reference class/seal.


def _leaf(home, ticket, budget, kind):
    _budget(budget)
    body = G._read_reference(ticket, own=False, read_budget=budget)
    M.need(M.existing(body['owner_home'], directory=True, private=True) == home,
           'GENERATION_SERVICES_T_DERIVED_EXACT_ORIGINAL_HOME')
    M.need(kind in ('services', 'SYSTEM_history'), 'GENERATION_SERVICES_FIXED_METADATA_KIND')
    parent = home / (SERVICE_LEAF if kind == 'services' else HISTORY_LEAF)
    return parent / G._source_key(M.birth(body['old_owner_birth']))


def _ticket_reference(ticket):
    return dict(path=ticket.path, sha256=ticket.sha256, identity=M.descriptor(ticket.path))


def _generation_metadata(home, ticket, budget, kind):
    source = G._read_reference(ticket, own=False, read_budget=budget)
    parent = _leaf(home, ticket, budget, kind).parent
    M.existing(M.descriptor(parent), directory=True, private=True)
    return dict(schema=SCHEMA, kind=kind, port_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        original_ticket=_ticket_reference(ticket), source_birth=source['old_owner_birth'],
        parent_identity=M.descriptor(parent))


def _validate_generation(body, home, ticket, budget, kind):
    _budget(budget)
    M.need(type(body) is dict and body['OWN'] is False
           and body.get('service_history_generation') == _generation_metadata(home, ticket, budget, kind)
           and body['old_owner_birth'] == body['service_history_generation']['source_birth']
           and body['source_directory']['path'] == str(_leaf(home, ticket, budget, kind)),
           'GENERATION_SERVICES_EXACT_PORT_T_SOURCE_BIRTH_PARENT_AND_LEAF')
    if kind == 'services':
        M.need(body['original_ticket'] == body['service_history_generation']['original_ticket'],
               'GENERATION_SERVICES_ORIGINAL_INNER_T_REFERENCE_UNMODIFIED')
    budget.check()


def read_service_complete(reference, home, *, ticket, budget):
    _budget(budget); verify_sources()
    fn = _ports(D._read_complete,
        [('home / (OWN_LEAF if own else LEAF)', '_generation_leaf(home, _ticket, budget, "services")', 2)],
        dict(_generation_leaf=_leaf, _ticket=ticket))
    body, record = fn(reference, home, own=False, budget=budget)
    _validate_generation(body, home, ticket, budget, 'services')
    return body, record


def _sync_original_home(home):
    # Preserve the ORIGINAL D._complete(home/LEAF) durability boundary after
    # its leaf has moved under one new generation parent. Metadata only.
    M.existing(M.descriptor(home), directory=True, private=True)
    fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _complete_for_source(owner, budget):
    def complete(old_leaf, body, *, final_guard):
        issuer, ticket_body, _, _, _ = GF._source(owner, budget)
        home, ticket = owner.core.home, issuer.ticket
        M.need(old_leaf == home / D.LEAF and body['OWN'] is False
               and body['old_owner_birth'] == ticket_body['old_owner_birth'] == asdict(process_birth(os.getpid()))
               and body['original_ticket'] == _ticket_reference(ticket),
               'GENERATION_SERVICES_ONLY_ACTUAL_CURRENT_REGISTERED_PRODUCTION_SOURCE')
        leaf = _leaf(home, ticket, budget, 'services')
        if not os.path.lexists(leaf.parent):
            leaf.parent.mkdir(mode=0o700)
        value = dict(body, service_history_generation=_generation_metadata(home, ticket, budget, 'services'))
        def guarded_original_postcheck():
            final_guard()  # Original live service cap/source/financial/retirement checks.
            _validate_generation(dict(value, source_directory=M.descriptor(leaf)), home, ticket, budget, 'services')
            verify_sources()
        result = D._complete(leaf, value, final_guard=guarded_original_postcheck)
        # Original SOURCE/postcheck/ISSUED and generation-parent fsync have
        # succeeded; sync home BEFORE returning to original registry commit.
        _sync_original_home(home)
        return result
    return complete


def publisher_function(owner, read_budget):
    verify_sources()
    return _ports(D.publish_source,
        [('F._source(owner, read_budget)', '_generation_financial_source(owner, read_budget)', 2)],
        dict(_generation_financial_source=GF._source, _complete=_complete_for_source(owner, read_budget)))


def publish_source(owner, *, source_cap, read_budget):
    _budget(read_budget)
    return publisher_function(owner, read_budget)(owner, source_cap=source_cap, read_budget=read_budget)


def _verify_generation_ticket(ticket, *, owner, read_budget, own):
    _production(own)
    return G.verify_ticket(ticket, owner=owner, read_budget=read_budget, own=False)


def _read_services_port(reference, home, *, own, budget, ticket):
    _production(own)
    return read_service_complete(reference, home, ticket=ticket, budget=budget)


def receiver_function(ticket):
    verify_sources()
    changes = [
        ('(T.verify_OWN_inert_ticket if own else T.verify_inert_ticket)(ticket, owner=owner, read_budget=read_budget)',
         '_generation_ticket(ticket, owner=owner, read_budget=read_budget, own=own)', 2),
        ('P.verify_registered_pair(owner, ticket=ticket, read_budget=read_budget)',
         '_generation_pair(owner, ticket=ticket, read_budget=read_budget)', 1),
        ('T._read_reference(ticket, own=own, read_budget=read_budget)',
         '_generation_read(ticket, own=own, read_budget=read_budget)', 1)]
    return _ports(D._verify_common, changes, dict(_generation_ticket=_verify_generation_ticket,
        _generation_pair=G.verify_registered_pair, _generation_read=G._read_reference,
        _read_complete=lambda reference, home, *, own, budget:
            _read_services_port(reference, home, own=own, budget=budget, ticket=ticket)))


def verify_reference(reference, *, owner, ticket, read_budget):
    _budget(read_budget)
    value = receiver_function(ticket)(reference, owner, ticket, read_budget=read_budget, own=False)
    M.need(type(value) is D.VerifiedRetiredServiceControls and value.OWN is False,
           'GENERATION_SERVICES_ORIGINAL_SEALED_METADATA_TYPE_NOT_RW_AUTHORITY')
    return value


def _service_verifier(own):
    _production(own)
    return verify_reference


def _history_leaf(home, ticket, budget):
    return _leaf(home, ticket, budget, 'SYSTEM_history')


def _save_history_source(path, body, *, ticket, budget):
    from normal_cold_sealer import save_candidate
    source = G._read_reference(ticket, own=False, read_budget=budget)
    home = M.existing(source['owner_home'], directory=True, private=True)
    M.need(body['OWN'] is False and body['old_owner_birth'] == source['old_owner_birth']
           == asdict(process_birth(os.getpid())) and path == _history_leaf(home, ticket, budget) / 'SOURCE_PUBLIC.json',
           'GENERATION_HISTORY_ONLY_CURRENT_T_BOUND_SOURCE_BODY_AND_EXACT_LEAF')
    value = dict(body, service_history_generation=_generation_metadata(home, ticket, budget, 'SYSTEM_history'))
    _validate_generation(value, home, ticket, budget, 'SYSTEM_history')
    return save_candidate(path, value)


def _prepare_history_leaf(home, ticket, budget):
    # Reached only at the ORIGINAL H leaf expression, after its exact source,
    # approved-contract, durable-reference and full history-parser checks.
    leaf = _history_leaf(home, ticket, budget)
    if not os.path.lexists(leaf.parent):
        leaf.parent.mkdir(mode=0o700)
    _generation_metadata(home, ticket, budget, 'SYSTEM_history')
    return leaf


def history_publisher_function(ticket):
    verify_sources()
    changes = [
        ('C._read_complete(service_reference, core.home, own=own, budget=read_budget)',
         '_generation_services(service_reference, core.home, own=own, budget=read_budget, ticket=_ticket)', 2),
        ('core.home / (OWN_LEAF_NAME if own else LEAF_NAME)',
         '_generation_leaf(core.home, _ticket, read_budget)', 1),
        ("save_candidate(leaf / 'SOURCE_PUBLIC.json', body)",
         "_generation_save_history(leaf / 'SOURCE_PUBLIC.json', body, ticket=_ticket, budget=read_budget)", 1)]
    return _ports(H._publish, changes, dict(_generation_services=_read_services_port,
        _generation_leaf=_prepare_history_leaf, _generation_save_history=_save_history_source, _ticket=ticket))


def publish_system_history(owner, *, source_cap, service_reference, read_budget):
    _budget(read_budget); verify_sources()
    issuer, _, _, _, _ = GF._source(owner, read_budget)
    ticket, home = issuer.ticket, owner.core.home
    # Validate the original live production cap and complete generation SOURCE
    # before creating even the new metadata-only parent directory.
    D._live_source_cap(source_cap, owner.core, budget=read_budget, own=False)
    read_service_complete(service_reference, home, ticket=ticket, budget=read_budget)
    leaf = _history_leaf(home, ticket, read_budget)
    result = history_publisher_function(ticket)(owner.core, source_cap=source_cap,
        service_reference=service_reference, read_budget=read_budget, own=False)
    # The original direct-home fsync is retained; generation nesting needs its
    # exact private parent synced as well before returning success.
    fd = os.open(leaf.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return result


def _read_history_body(path, pin, *, limit, home, ticket, budget):
    body, observed = M.private_read(path, pin, limit=limit)
    _validate_generation(body, home, ticket, budget, 'SYSTEM_history')
    return body, observed


def history_receiver_function():
    verify_sources()
    changes = [
        ('C.verify_OWN_reference if own else C.verify_reference', '_generation_service_verifier(own)', 1),
        ('owner.core.home / (OWN_LEAF_NAME if own else LEAF_NAME)',
         '_generation_leaf(owner.core.home, ticket, read_budget)', 1),
        ('M.private_read(path, history_reference._pin, limit=8 * 1024 * 1024)',
         '_generation_read_body(path, history_reference._pin, limit=8 * 1024 * 1024, home=owner.core.home, ticket=ticket, budget=read_budget)', 1)]
    return _ports(H._read, changes, dict(_generation_service_verifier=_service_verifier,
        _generation_leaf=_history_leaf, _generation_read_body=_read_history_body))


def read_system_history(reference, *, history_reference, owner, ticket, read_budget):
    _budget(read_budget)
    value = history_receiver_function()(reference, history_reference=history_reference,
        owner=owner, ticket=ticket, read_budget=read_budget, own=False)
    M.need(type(value) is H.VerifiedSystemHistory and value.OWN is False,
           'GENERATION_HISTORY_ORIGINAL_SEALED_READONLY_TYPE_NOT_LIVE_HEALTH')
    return value


def resource_receiver_function():
    verify_sources()
    return _ports(R._read,
        [('C.verify_OWN_reference if own else C.verify_reference', '_generation_service_verifier(own)', 1)],
        dict(_generation_service_verifier=_service_verifier))


def read_resource_history(reference, *, owner, ticket, read_budget):
    _budget(read_budget)
    value = resource_receiver_function()(reference, owner=owner, ticket=ticket, read_budget=read_budget, own=False)
    M.need(type(value) is R.VerifiedResourceHistory and value.OWN is False,
           'GENERATION_RESOURCE_HISTORY_ORIGINAL_SEALED_READONLY_TYPE_NOT_SAMPLER')
    return value
