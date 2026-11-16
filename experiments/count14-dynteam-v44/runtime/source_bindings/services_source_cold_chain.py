#!/usr/bin/env python3
"""One fixed original financial entry/factory/emitter, explicit service controls.

Installation is first-cold only. No retirement, ticket issuance or sidecar
publication is requested by import, emission, factory verification or binding.
Original science, constructors, command prefix and source modules stay intact.
"""
from pathlib import Path
from types import FunctionType, ModuleType
import hashlib
import importlib
import importlib.util
import json

PARENTS = {
    'factory': ('financial_source_factory.py', 'b828661e94d6a63a839b145ddb424e396470f993809c0a1e116f102ed99a0a5a'),
    'entry': ('financial_source_entry.py', '9f649f0ed575b9a96ab609570b6b88eb89b39e9398e7691e84ea83fd9caa9861'),
    'emit': ('financial_source_emit.py', 'cbc81ca3b5b97d257cc2a378294567d388d1d5ec667fe11a9826e2ecbab27830'),
}
PINS = {
    'financial_source_cold': 'c23b831ffce2e2b26435a613089fd077e32d66d4d29c9c21e39356fa13e53385',
    'source_services_retirement': '084a59c44b0bfe49cca9c138472bda76575cd52a24fbed569f0b8f765aaa1887',
    'services_inert_clock_cold': 'b90faf172bf7c21ade52915a5c31d058e55a692aa165465bf06eaad287f87075',
    'source_services_controls': 'f7c72e41dc7df2940917ad664d582308ab936387c0b5190a21e2c07bac2d55db',
    'durable_service_source_controls': 'fe5cbbbb186e4d9049895f68c32529d8237d6ffbeda35d03b8ed15a0482f0b83',
    'retired_system_history': '448802312193a2ef4b5f3fe2b35ff2d65a3ffef8c3cc158c1f46b37b1a3d3ed5',
    'retired_system_live_receiver': '4c3df1b4ac22d3e30b2da12173058f1b11bf787ad271b9f71d4c3ecc767a81c1',
    'retired_resource_history': 'b756439360673e2e0cf96d7e0e3ae7f546cfd43fd7862e437894fc85cd3ade97',
}
OPS = ('REQUEST_NORMAL_SOURCE_SERVICES_RETIREMENT',
       'POLL_NORMAL_SOURCE_SERVICES_RETIREMENT',
       'OBSERVE_NORMAL_SOURCE_SERVICES_RETIREMENT',
       'PUBLISH_NORMAL_INERT_SERVICE_CONTROLS')
RETAINED_PARENT_NAMESPACE = None
RETAINED_PRIVATE_FACTORY = None
RETAINED_ORIGINAL_OWNER = None
RETAINED_ORIGINAL_LEDGER = None


def parent(kind):
    filename, expected = PARENTS[kind]
    path = Path(__file__).resolve().parents[1] / 'formal100m-financial-source-entry-cold-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1' / filename
    if path.resolve() != path or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('SERVICES_SOURCE_EXACT_FROZEN_FINANCIAL_PARENT_PIN')
    spec = importlib.util.spec_from_file_location('count14_services_financial_parent_' + kind, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def verify_sources():
    import paid_cold_material as M
    for name, expected in PINS.items():
        path = Path(importlib.import_module(name).__file__)
        M.need(path.is_absolute() and path.resolve() == path and not path.is_symlink()
               and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
               'SERVICES_SOURCE_FIXED_QUALIFIED_COMPONENT_PINS')
    from financial_source_cold import verify_sources as finance
    from source_services_retirement import verify_sources as services
    from durable_service_source_controls import verify_sources as durable
    finance(); services(); durable()
    return dict(PINS)


def registered(owner):
    import paid_cold_material as M
    import source_services_retirement as R
    from normal_inert_source_cold import registered as issuer
    verify_sources()
    issuer(owner)  # Original exact same-source owner/core/birth/thread guards.
    rt = R.registered(owner.core)
    M.need(rt.owner is owner and rt.core is owner.core and rt.OWN is False
           and all(getattr(rt, name).__func__ is getattr(R.SourceServicesRetirement, name)
                   for name in ('request', 'poll', 'observe')),
           'SERVICES_SOURCE_SAME_REGISTERED_OWNER_ORIGINAL_RETIREMENT_METHODS')
    return rt


def request(owner):
    from bounded_metadata_ro import ReadBudget
    return registered(owner).request(read_budget=ReadBudget())


def poll(owner):
    from bounded_metadata_ro import ReadBudget
    return registered(owner).poll(read_budget=ReadBudget())


def observe(owner):
    from bounded_metadata_ro import ReadBudget
    return registered(owner).observe(read_budget=ReadBudget())


def publish(owner):
    from bounded_metadata_ro import ReadBudget
    from source_services_controls import capture_registered
    from durable_service_source_controls import publish_source, load_reference
    from retired_system_history import publish_history
    registered(owner)
    budget = ReadBudget()
    cap = capture_registered(owner.core, read_budget=budget)
    reference = publish_source(owner, source_cap=cap, read_budget=budget)
    history = publish_history(owner.core, source_cap=cap,
        service_reference=load_reference(reference['path'], reference['sha256']), read_budget=budget)
    return dict(schema='count14-services-source-cold-publication-status-v1',
                service_source_reference=reference, system_history_source_reference=history, original_INERT_ticket_unmodified=True,
                financial_sidecar_independent=True, source_metadata_only=True, inert_only=True,
                new_dispatcher=False, safe_to_TERM=False, whole_runnable_ready=False,
                paid_activation_authorized=False)


def restore_independent_SYSTEM_receiver(owner, *, ticket):
    """Explicit NEW receiver only; no new caller paths/keys/health bools.

    This is not a paid/native/science restore or an automatic entry action.
    The library refuses until an actual qualified NEW original resource/native
    graph exists. Original T must verify before any fixed SOURCE file read.
    """
    import normal_inert_cut as T
    import paid_cold_material as M
    import durable_service_source_controls as C
    import retired_system_history as H
    import retired_system_live_receiver as L
    from bounded_metadata_ro import ReadBudget
    verify_sources()
    budget=ReadBudget()
    T.verify_inert_ticket(ticket, owner=owner, read_budget=budget)
    home=owner.core.home
    cm,_=M.private_read(home/C.LEAF/'ISSUED.json', limit=262144)
    hm,_=M.private_read(home/H.LEAF_NAME/'ISSUED_PUBLIC.json', limit=262144)
    reference=C.load_reference(home/C.LEAF/'SOURCE.json', cm['source_sha256'])
    history=H.load_reference(home/H.LEAF_NAME/'SOURCE_PUBLIC.json', hm['source_sha256'])
    return L.restore(reference, history_reference=history, owner=owner,
        ticket=ticket, read_budget=budget)


def read_retired_resource_history(owner, *, ticket):
    """Explicit read-only metadata API, NOT a sampler or owner transition.

    Original typed T must verify before fixed T-derived SOURCE reads. This
    returns old metadata only: no fresh resource health or runtime authority.
    """
    import normal_inert_cut as T
    import paid_cold_material as M
    import durable_service_source_controls as C
    import retired_resource_history as R
    from bounded_metadata_ro import ReadBudget
    verify_sources()
    budget=ReadBudget()
    T.verify_inert_ticket(ticket, owner=owner, read_budget=budget)
    home=owner.core.home
    marker,_=M.private_read(home/C.LEAF/'ISSUED.json', limit=262144)
    reference=C.load_reference(home/C.LEAF/'SOURCE.json', marker['source_sha256'])
    return R.read_history(reference, owner=owner, ticket=ticket, read_budget=budget)


def install_after_binder(cohort):
    import paid_cold_material as M
    import normal_inert_cut as T
    from normal_inert_source_cold import registered as issuer_for
    from source_services_retirement import SourceServicesRetirement
    from services_inert_clock_cold import install_unpublished_issuer
    verify_sources()
    issuer = issuer_for(cohort.owner)
    M.need(cohort.owner.core is cohort.core and issuer.source is cohort.normal_cold_sealer
           and cohort.normal_inert_cut_issuer is issuer
           and not hasattr(cohort.owner, 'source_services_retirement')
           and not hasattr(cohort.core, 'source_services_retirement'),
           'SERVICES_SOURCE_FIRST_COLD_AFTER_ORIGINAL_FINANCIAL_BINDER_ONCE')
    rt = SourceServicesRetirement(cohort.owner)
    proof = install_unpublished_issuer(issuer)
    M.need(type(issuer) is T.NormalInertIssuer
           and issuer.issue.__func__.__code__ is T.NormalInertIssuer.issue.__code__
           and rt.owner is cohort.owner and rt.core is cohort.core and not rt.requested,
           'SERVICES_SOURCE_RETAIN_EXACT_ISSUER_CODE_AND_NOT_REQUESTED_RETIREMENT')
    return proof


def install_private_factory_last(factory):
    import paid_cold_material as M
    verify_sources()
    M.need(isinstance(factory, ModuleType)
           and factory.create_prefix_owner.__globals__ is vars(factory)
           and hasattr(factory, '_financial_source_cold_proof')
           and not hasattr(factory, '_services_source_last_constructor')
           and all(vars(factory).get(k) is None for k in (
               'RETAINED_FACTORY_OWNER', 'RETAINED_FACTORY_LEDGER',
               'RETAINED_ORIGINAL_OWNER', 'RETAINED_ORIGINAL_LEDGER')),
           'SERVICES_SOURCE_NEW_UNRETAINED_ORIGINAL_FINANCIAL_FACTORY_ONLY')
    previous = factory.private_original_constructor

    def constructor(bind_same_owner):
        helper = previous(bind_same_owner)
        current = helper._formal_bind_same_owner

        def bind(owner, *, sources):
            cohort = current(owner, sources=sources)
            install_after_binder(cohort)
            return cohort

        helper._formal_bind_same_owner = bind
        return helper

    factory.restore_independent_SYSTEM_receiver = restore_independent_SYSTEM_receiver
    factory.read_retired_resource_history = read_retired_resource_history
    factory._services_source_last_constructor = previous
    factory.private_original_constructor = constructor
    factory._services_source_cold_proof = dict(
        original_financial_source_and_all_binders_first=True,
        same_original_owner_service_registration=True,
        exact_original_issuer_type_and_issue_code_retained=True,
        retirement_issue_and_both_publications_explicit_only=True,
        original_prefix_or_candidate_repeated=False,
        new_thread_or_dispatcher_on_install=False, source_scientific_bytes_modified=False,
        safe_to_TERM=False, paid_activation_authorized=False, whole_runnable_ready=False,
        actual_production_six_runtime_qualified=False)
    return factory


def load_private_factory(*, tester_sources=None, tester_companion=None, approved_repair_sources=()):
    factory = parent('factory').load_private_factory(tester_sources=tester_sources,
        tester_companion=tester_companion, approved_repair_sources=approved_repair_sources)
    return install_private_factory_last(factory)


def verify_actual_formal_import_graph():
    previous = parent('factory').verify_actual_formal_import_graph()
    factory = load_private_factory()
    return dict(schema='count14-services-financial-source-cold-import-graph-v1', parent=previous,
                services_source=factory._services_source_cold_proof,
                original_owner_constructed=False, actual_production_six_runtime_qualified=False,
                safe_to_TERM=False, whole_runnable_ready=False, paid_activation_authorized=False)


def create_prefix_owner(bindings_path, bindings_sha256, *, code_root, factory_path, factory_manifest,
                        tester_bindings_path=None, tester_bindings_sha256=None, approved_repair_sources=()):
    global RETAINED_PARENT_NAMESPACE, RETAINED_PRIVATE_FACTORY, RETAINED_ORIGINAL_OWNER, RETAINED_ORIGINAL_LEDGER
    if RETAINED_PARENT_NAMESPACE is not None:
        raise ValueError('SERVICES_SOURCE_SINGLE_RETAINED_OWNER_NO_REPLAY')
    module = parent('factory'); original = module.create_prefix_owner
    namespace = dict(vars(module), load_private_factory=load_private_factory)
    fn = FunctionType(original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__; RETAINED_PARENT_NAMESPACE = namespace
    try:
        return fn(bindings_path, bindings_sha256, code_root=code_root, factory_path=factory_path,
            factory_manifest=factory_manifest, tester_bindings_path=tester_bindings_path,
            tester_bindings_sha256=tester_bindings_sha256, approved_repair_sources=tuple(approved_repair_sources))
    finally:
        RETAINED_PRIVATE_FACTORY = namespace['RETAINED_PRIVATE_FACTORY']
        RETAINED_ORIGINAL_OWNER = namespace['RETAINED_ORIGINAL_OWNER']
        RETAINED_ORIGINAL_LEDGER = namespace['RETAINED_ORIGINAL_LEDGER']


def private_emitter(*, tester_bindings_path=None, tester_bindings_sha256=None):
    module = parent('emit').private_emitter(tester_bindings_path=tester_bindings_path,
                                           tester_bindings_sha256=tester_bindings_sha256)
    root = Path(__file__).resolve().parent
    if module._idle_helper_path != root.parent/'formal100m-financial-source-entry-cold-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/financial_source_factory.py':
        raise ValueError('SERVICES_SOURCE_EXACT_CURRENT_FINANCIAL_HELPER')
    module._idle_helper_path = Path(__file__).resolve()
    extra = [*sorted(root.glob('*.py')),
             *(root.parent/'formal100m-source-services-retirement-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1'/name for name in (
                 'source_services_retirement.py', 'services_inert_clock_cold.py', 'source_services_controls.py')),
             root.parent/'formal100m-services-durable-source-controls-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/durable_service_source_controls.py',
             root.parent/'formal100m-services-durable-source-controls-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/retired_system_history.py',
             root.parent/'formal100m-services-durable-source-controls-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/retired_system_live_receiver.py',
             root.parent/'formal100m-services-durable-source-controls-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/retired_resource_history.py']
    module._idle_pin_paths = tuple(dict.fromkeys((*module._idle_pin_paths, *extra)))
    return module


def emit(bindings_path, bindings_sha256, *, destination, tester_bindings_path=None,
         tester_bindings_sha256=None, new_bindings=None):
    module = parent('emit'); original = module.emit
    fn = FunctionType(original.__code__, dict(vars(module), private_emitter=private_emitter),
                      original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn(bindings_path, bindings_sha256, destination=destination,
              tester_bindings_path=tester_bindings_path,
              tester_bindings_sha256=tester_bindings_sha256, new_bindings=new_bindings)


def private_namespace(original):
    shared = parent('entry').private_namespace(original)
    namespace = vars(shared); previous = namespace['command']

    def command(row):
        if type(row) is dict and row.get('op') in OPS:
            if set(row) != {'op'}:
                raise ValueError('SERVICES_SOURCE_ONLY_EXACT_NO_ARGUMENT_OPCODE')
            owner = namespace['RETAINED_OWNER']
            if owner is None:
                raise ValueError('SERVICES_SOURCE_SAME_RETAINED_OWNER_REQUIRED')
            if row['op'] == OPS[0]: return request(owner)
            if row['op'] == OPS[1]: return poll(owner)
            if row['op'] == OPS[2]: return observe(owner)
            return publish(owner)
        return previous(row)

    namespace['command'] = command
    shared._services_source_previous_command = previous
    shared._services_source_ops = OPS
    return shared


def original_entry():
    return parent('entry').original_entry()


def main(argv=None):
    try:
        return private_namespace(original_entry()).main(argv)
    except Exception as error:
        frames = []; tb = error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                               function=tb.tb_frame.f_code.co_name))
            tb = tb.tb_next
        print(json.dumps(dict(PUBLIC_code='SERVICES_SOURCE_COLD_CHAIN_ENTRY_REFUSED',
                              exception_type=type(error).__name__, locations=frames,
                              message_or_private_body_exported=False), sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
