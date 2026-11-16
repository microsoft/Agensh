"""Prospective host PUBLIC-code producer; never a fee/exemption authority.

Only exact original Refused.code ENUMs at two pinned framework functions are
observed. args/message/locals are never read. Guard-time work is bounded RAM
under a nonblocking own lock; PUBLIC I/O and process witnesses occur outside
ledger/queue/dispatcher locks. Missing physical proof means no projection.
"""
from pathlib import Path
from types import MethodType
import ast
import copy
import hashlib
import inspect
import os
import threading
import time
import textwrap

from common import Refused, need, digest, publish, wire, private_dir, hash_file, strict
from final_queue import FinalQueue, process_identity
from final_authority import FinalAuthority
from model_capacity import ModelCapacity
from native_final_dispatch import NativeFinalDispatcher
from allowance_control import FormalAllowanceControl, PROJECTION

PINS = {
    'model_capacity.py': '1df72fa17fa25159befd4fed8c5751921c60720d53212dddac57c9de283b09ba',
    'final_authority.py': '3644fe51daa13083b03d21a549b0be2d228a4de68a00d73c0df82feec3526629',
}
SITES = {
    'AUX_SCOPE_NOT_CURRENT': ModelCapacity._scope,
    'FINAL_AUTHORITY_QUEUE_CLAIM': FinalAuthority.__call__,
}
MAX_CONTEXTS = 4096
MAX_PENDING = 256


def validate_static_sources():
    """Framework source only, called before any guard/financial lock."""
    from common import Refused as OriginalRefused
    need(OriginalRefused is Refused and Refused.__getattribute__ is BaseException.__getattribute__,
         'FIXED_CODE_ORIGINAL_PUBLIC_CODE_ATTRIBUTE_NOT_MESSAGE_PROPERTY')
    for enum, function in SITES.items():
        path = Path(inspect.getsourcefile(function)).resolve()
        need(path.name in PINS and hash_file(path)['sha256'] == PINS[path.name],
             'FIXED_CODE_EXACT_ORIGINAL_FRAMEWORK_SOURCE_PIN')
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
        sites = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and
                 isinstance(n.func, ast.Name) and n.func.id == 'need' and len(n.args) == 2 and
                 isinstance(n.args[1], ast.Constant) and n.args[1].value == enum]
        need(len(sites) == 1, 'FIXED_CODE_STATIC_LITERAL_GUARD_NOT_FRAME_CAUSE_INFERENCE')
    return {enum: function.__code__ for enum, function in SITES.items()}


class FixedPublicCodeProducer:
    def __init__(self, dispatcher, control):
        need(type(dispatcher) is NativeFinalDispatcher and type(control) is FormalAllowanceControl and
             dispatcher.queue is control.core.queue and dispatcher.ledger is control.core.ledger and
             type(dispatcher.queue) is FinalQueue and type(dispatcher.capacity) is ModelCapacity and
             not dispatcher.children and not dispatcher.points and not dispatcher.faulted and
             set(control.core.gate.startup_held) == set(control.core.rows),
             'FIXED_CODE_SAME_EMPTY_ORIGINAL_DISPATCHER_COLD_INSTALL_ONLY')
        control.fresh()
        self.dispatcher, self.control = dispatcher, control
        self.owner = process_identity(os.getpid())
        self.site_codes = validate_static_sources()
        self.source_pin = hash_file(Path(__file__))['sha256']
        self.lock = threading.Lock()
        self.contexts, self.pending, self.observations, self.witnesses, self.projections = {}, [], {}, {}, {}
        self.sequence, self.dropped = 0, 0
        self.failures = []
        self.home = private_dir(control.core.home / 'final-fixed-public-code-v1', create=True)
        need(not any(self.home.iterdir()), 'FIXED_CODE_NEW_PUBLIC_CONTROL_HOME_NO_OVERWRITE')

    def _outside(self):
        d = self.dispatcher
        need(not d.ledger.mutex._is_owned() and not d.queue.mutex._is_owned() and
             not d.lock._is_owned() and process_identity(os.getpid()) == self.owner,
             'FIXED_CODE_NO_PUBLIC_IO_OR_PROCESS_WAIT_UNDER_SCIENCE_LOCK')

    def register_memory_only(self, record, authority, identity):
        """Original dispatch calls this BEFORE publishing ready; RAM only."""
        if (type(authority) is not FinalAuthority or authority.child is not record.get('child') or
            authority.child_identity != identity or authority.job_id != record['job']['id'] or
            authority.claim != record['job']['claim'] or authority.queue is not self.dispatcher.queue or
            authority.ledger is not self.dispatcher.ledger or record.get('scope') not in
            self.dispatcher.capacity.authorizers or
            self.dispatcher.capacity.authorizers[record['scope']] is not authority):
            self.dropped += 1
            return False
        if not self.lock.acquire(False):
            self.dropped += 1
            return False
        try:
            scope = record['scope']
            if scope in self.contexts or len(self.contexts) >= MAX_CONTEXTS:
                self.dropped += 1
                return False
            self.contexts[scope] = dict(record=record, authority=authority, identity=copy.deepcopy(identity),
                job_id=record['job']['id'], claim=record['job']['claim'], scope=scope)
            return True
        finally:
            self.lock.release()

    def capture_memory_only(self, error, scope):
        """PUBLIC attribute + file:line:function only; no message/args/locals."""
        if type(error) is not Refused or type(scope) is not str:
            return False
        enum = error.__dict__.get('code')
        if type(enum) is not str or enum not in self.site_codes:
            return False
        tb, location = error.__traceback__, None
        while tb is not None:
            code = tb.tb_frame.f_code
            if code is self.site_codes[enum]:
                location = dict(file=code.co_filename, line=tb.tb_lineno, function=code.co_name)
            tb = tb.tb_next
        if location is None:
            return False
        if not self.lock.acquire(False):
            self.dropped += 1
            return False
        try:
            context = self.contexts.get(scope)
            if context is None or len(self.pending) >= MAX_PENDING:
                self.dropped += 1
                return False
            key = (context['job_id'], enum)
            if key in self.observations or any(p['key'] == key for p in self.pending):
                return False
            self.sequence += 1
            self.pending.append(dict(key=key, PUBLIC_code=enum, location=location,
                observed_monotonic_ns=time.monotonic_ns(), scope=scope, sequence=self.sequence))
            return True
        finally:
            self.lock.release()

    def scope_body(self, original):
        producer = self
        def guarded(capacity, scope):
            try:
                return original(capacity, scope)
            except Refused as error:
                # The exact exception is re-raised. Collection failure cannot
                # turn a refused authority into success or change accounting.
                producer.capture_memory_only(error, scope)
                raise
        return guarded

    def _live_witness(self, context, observed_ns):
        child = context['record']['child']
        before = time.monotonic_ns()
        if before < observed_ns or child.poll() is not None:
            return None
        try:
            actual = process_identity(child.pid)  # original refuses Z/X
        except (OSError, Refused):
            return None
        after = time.monotonic_ns()
        if actual != context['identity']:
            return None
        return dict(child=copy.deepcopy(actual), observed_before_ns=before, observed_after_ns=after,
                    live_after_guard_occurrence=True)

    def _drain_pending(self):
        # Never wait for the control lock, even outside scientific locks.
        if not self.lock.acquire(False):
            return []
        try:
            values, self.pending = self.pending, []
            return values
        finally:
            self.lock.release()

    def flush_occurrences(self):
        self._outside()
        for occurrence in self._drain_pending():
            context = self.contexts[occurrence['scope']]
            key = occurrence['key']
            witness = self._live_witness(context, occurrence['observed_monotonic_ns'])
            value = dict(schema='count14-fixed-public-code-occurrence-NOT_EXEMPTION-v1',
                owner=self.owner, job_id=context['job_id'], original_claim=context['claim'],
                scope=context['scope'], child=context['identity'], PUBLIC_code=occurrence['PUBLIC_code'],
                location=occurrence['location'], observed_monotonic_ns=occurrence['observed_monotonic_ns'],
                producer_source_sha256=self.source_pin, physical_live_witness=witness,
                message_args_or_locals_read=False, fee_or_allowance_changed=False)
            path = self.home / (context['job_id'] + '_' + occurrence['PUBLIC_code'] + '_OCCURRENCE_PUBLIC.json')
            publish(path, wire(value), mode=0o400)
            self.observations[key] = value
            self.witnesses[key] = witness

    def bind_terminal_projections(self):
        """Only original natural wait + durable PARTIAL/financial proof binds.

        This method does NOT register a tool exemption or approve a repair. An
        already-dead child without a live-after-occurrence witness is ineligible.
        Missing evidence is retained, not retroactively reconstructed.
        """
        self._outside()
        for scope, context in self.contexts.items():
            jid, record = context['job_id'], context['record']
            keys = [k for k in self.observations if k[0] == jid]
            if jid in self.projections or len(keys) != 1 or self.witnesses.get(keys[0]) is None:
                continue
            if not (record.get('partial') is True and record.get('terminal') is not None and
                    record['child'].returncode is not None and record['job']['claim'] == context['claim']):
                continue
            job = record['job']
            _, chain, _ = self.control._snapshot(job['point'], job['replicate'])
            matches = [r for r in chain if r['job_id'] == jid and 'failure_proof' in r]
            need(len(matches) == 1, 'FIXED_CODE_ORIGINAL_DURABLE_FINANCIAL_PARTIAL_REQUIRED')
            proof = matches[0]['failure_proof']
            occurrence = self.observations[keys[0]]
            need(proof['scope'] == scope and proof['original_claim'] == context['claim'] and
                 proof['terminal_sha256'] == digest(record['terminal']),
                 'FIXED_CODE_SAME_SCOPE_CLAIM_ORIGINAL_TERMINAL')
            with self.dispatcher.queue.mutex:
                actual = self.dispatcher.queue._job(jid)
            need(strict(actual['child']) == context['identity'] and
                 self.witnesses[keys[0]]['observed_after_ns'] <= time.monotonic_ns(),
                 'FIXED_CODE_SAME_ORIGINAL_CHILD_LIFETIME')
            value = dict(schema=PROJECTION, owner=self.owner, job_id=jid,
                original_claim=context['claim'], scope=scope, terminal_sha256=proof['terminal_sha256'],
                child=context['identity'], public_code=occurrence['PUBLIC_code'],
                producer_source_sha256=self.source_pin,
                observed_monotonic_ns=occurrence['observed_monotonic_ns'])
            path = self.home / (jid + '_FIXED_PROJECTION_PUBLIC.json')
            publish(path, wire(value), mode=0o400)
            self.projections[jid] = dict(path=str(path), sha256=hash_file(path)['sha256'])

    def safe_flush(self):
        try:
            self.flush_occurrences()
            self.bind_terminal_projections()
        except Exception as error:
            # A diagnostic failure is PUBLIC, never successful evidence and
            # never an excuse to clear original financial/dispatcher faults.
            locations, tb = [], error.__traceback__
            while tb:
                locations.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                                      function=tb.tb_frame.f_code.co_name))
                tb = tb.tb_next
            self.failures.append(dict(PUBLIC_code='FIXED_CODE_PRODUCER_PROOF_RETAINED_NOT_QUALIFIED',
                exception_type=type(error).__name__, locations=locations))
            if len(self.failures) > 16:
                self.failures.pop(0)

    def public(self):
        return dict(schema='count14-fixed-public-code-producer-control-v1',
            occurrence_count=len(self.observations), terminal_projection_count=len(self.projections),
            pending_count=len(self.pending), dropped_observations=self.dropped,
            failures=copy.deepcopy(self.failures), automatic_fee_exemptions=0,
            model_calls=0, official_or_Dev4_runtime_qualified=False)


def prepare_dispatch_body(function, producer):
    """Exactly one RAM-only registration before ORIGINAL ready publication."""
    import textwrap
    before = ast.parse(textwrap.dedent(inspect.getsource(function)))
    tree = copy.deepcopy(before)
    hook = ast.parse('_fixed_register(record,authority,identity)').body[0]
    hits = []
    class Insert(ast.NodeTransformer):
        def visit_Expr(self, node):
            if (isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and
                node.value.func.id == 'publish' and node.value.args and
                ast.unparse(node.value.args[0]) == "config.with_suffix('.ready')"):
                hits.append(True)
                return [copy.deepcopy(hook), node]
            return self.generic_visit(node)
    tree = Insert().visit(tree)
    restored = copy.deepcopy(tree)
    class Remove(ast.NodeTransformer):
        def visit_Expr(self, node):
            if ast.dump(node, include_attributes=False) == ast.dump(hook, include_attributes=False):
                return None
            return self.generic_visit(node)
    restored = Remove().visit(restored)
    need(len(hits) == 1 and ast.dump(restored, include_attributes=False) == ast.dump(before, include_attributes=False),
         'FIXED_CODE_DISPATCH_ONE_RAM_HOOK_INVERSE_AST')
    namespace = dict(function.__globals__, _fixed_register=producer.register_memory_only)
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':before-original-ready', 'exec'), namespace)
    return namespace[function.__name__]


def install_fixed_public_code_producer(dispatcher, control):
    need(not hasattr(dispatcher, 'fixed_public_code_producer'), 'FIXED_CODE_COLD_INSTALL_ONCE')
    producer = FixedPublicCodeProducer(dispatcher, control)
    dispatcher.fixed_public_code_producer = producer  # retain before fallible compile
    dispatch = prepare_dispatch_body(dispatcher.dispatch_one.__func__, producer)
    capacity = dispatcher.capacity
    original_scope = capacity._scope.__func__
    need(original_scope.__code__ is ModelCapacity._scope.__code__, 'FIXED_CODE_ORIGINAL_SCOPE_BODY_REQUIRED')
    capacity._scope = MethodType(producer.scope_body(original_scope), capacity)
    dispatcher.dispatch_one = MethodType(dispatch, dispatcher)
    original_poll = dispatcher.poll
    original_status = dispatcher.status
    def poll(_same):
        producer.safe_flush()
        try:
            return original_poll()
        finally:
            producer.safe_flush()
    dispatcher.poll = MethodType(poll, dispatcher)
    def status(_same):
        value = original_status()
        value['fixed_public_code_producer'] = producer.public()
        return value
    dispatcher.status = MethodType(status, dispatcher)
    return producer
