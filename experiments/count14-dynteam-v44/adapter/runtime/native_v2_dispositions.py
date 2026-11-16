"""Cold new-root ONLY binding of v2 rejection/accounting and physical views.

Original financial SQL/schema/formulas and original stop thresholds remain.
Only ORIGINAL v2 additive rejection tables/views and SELECT projections are
used. No class/global code mutation, connection replacement, replay or retry.
Physical closed HTTP5xx does not imply COMPLETED or erase UNKNOWN charges.
This module is not a health probe, full AUX writer fence, or activation proof.
"""
from pathlib import Path
from types import FunctionType,MethodType,CodeType
import hashlib
import importlib.util
import inspect

from budget import Ledger,LOGICAL_PENDING
from scientific_relay import ScientificRelay,ScientificUsage
from feasibility_relay import ChatTransport
from common import need

ORIGINAL_SHA='1eb1aa19ac788ce70d53178e45945595ee2b1d1e0326a9c4dee38a49cffe5c91'


def original_v2():
    # A selectively exported, byte-identical framework file, not live code or
    # historical scientific state. Its class-wide Projection is NEVER invoked.
    path=Path(__file__).resolve().parents[1]/'original-v2-dispositions-v1/rejection_ledger.py'
    need(path.is_file() and not path.is_symlink() and path.resolve()==path and
         hashlib.sha256(path.read_bytes()).hexdigest()==ORIGINAL_SHA,
         'DYNTEAM_ORIGINAL_V2_DISPOSITION_SOURCE_PIN')
    spec=importlib.util.spec_from_file_location('count14_original_v2_rejection_private_import',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def clone(function,*,code=None,globals_delta=None):
    result=FunctionType(function.__code__ if code is None else code,
                        dict(function.__globals__,**(globals_delta or {})),function.__name__,
                        function.__defaults__,function.__closure__)
    result.__kwdefaults__=function.__kwdefaults__
    return result


# Only original returned+closed HTTP failures; timeout/stream truncation/closed
# downstream alone are NOT upstream physical proof. Correlate request, role,
# trajectory, preserved upper charge, explicit error, then original handler end.
PHYSICAL_TERMINAL="""NOT (state='UNKNOWN' AND EXISTS(
 SELECT 1 FROM unknown_charges uc WHERE uc.request_id=upstream_effective_requests.id
 AND uc.upper_bound=upstream_effective_requests.upper_bound)
 AND EXISTS(SELECT 1 FROM events ue WHERE ue.trajectory=upstream_effective_requests.trajectory
 AND ue.kind='UNKNOWN_EXECUTION' AND json_extract(ue.metadata,'$.request_id')=upstream_effective_requests.id
 AND json_extract(ue.metadata,'$.code') GLOB 'UPSTREAM_HTTP_5[0-9][0-9]')
 AND EXISTS(SELECT 1 FROM events he WHERE he.trajectory=upstream_effective_requests.trajectory
 AND he.kind='SCIENTIFIC_HTTP_HANDLER_FINISHED'
 AND json_extract(he.metadata,'$.request_id')=upstream_effective_requests.id
 AND json_extract(he.metadata,'$.role')=upstream_effective_requests.role))"""


def physical_code(code):
    values=[]
    for constant in code.co_consts:
        if isinstance(constant,CodeType):constant=physical_code(constant)
        elif isinstance(constant,str):
            key=''.join(constant.split()).upper().rstrip(';')
            if (key.startswith('SELECTCOUNT(*)FROMUPSTREAM_EFFECTIVE_REQUESTSWHERE') and
                    key.endswith("STATEIN('RESERVED','SENT','UNKNOWN')")):
                constant=constant.rstrip().rstrip(';')+' AND '+PHYSICAL_TERMINAL
        values.append(constant)
    return code.replace(co_consts=tuple(values))


class NativeV2Dispositions:
    def __init__(self,ledger):
        need(type(ledger) is Ledger and hasattr(ledger,'_dynteam_catalogues') and
             not hasattr(ledger,'_dynteam_v2_dispositions'),
             'DYNTEAM_ORIGINAL_NEW_SCOPE_LEDGER_ONLY_COLD_DISPOSITIONS')
        with ledger.mutex:
            need(not ledger.db.in_transaction and
                 ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==0 and
                 ledger.db.execute('SELECT COUNT(*) FROM aux_permits').fetchone()[0]==0,
                 'DYNTEAM_V2_DISPOSITIONS_BEFORE_ANY_REQUEST_OR_AUX')
            self.ledger,self.original=ledger,original_v2()
            self.original.schema(ledger)
            # Bind clones to THIS ledger only, retaining the already approved
            # dynamic cardinality register method. Do not edit Ledger methods,
            # module globals, old instances, DB rows or existing connection.
            self.raw_connection=ledger.db;self.original_methods={}
            logical=LOGICAL_PENDING.replace('requests.id','upstream_effective_requests.id')
            logical+=' AND NOT EXISTS(SELECT 1 FROM upstream_rejections ur WHERE ur.request_id=upstream_effective_requests.id)'
            for name,base in vars(Ledger).items():
                if not inspect.isfunction(base) or name in ('__init__','_unknown_schema'):continue
                bound=getattr(ledger,name);function=bound.__func__
                self.original_methods[name]=bound
                if name=='unknown_statistics':replacement=clone(self.original.statistics)
                elif name=='_unknown_thresholds':replacement=clone(self.original.thresholds)
                else:
                    code=self.original.changed_code(function.__code__)
                    # Preserve exact bound ORIGINAL tx/COMMIT/ROLLBACK and
                    # other methods needing neither SELECT nor logical-view
                    # changes. Byte-equivalent cloning is unnecessary and
                    # breaks trusted identity checks in the original clock.
                    if code==function.__code__ and 'LOGICAL_PENDING' not in code.co_names:continue
                    replacement=clone(function,code=code,globals_delta={'LOGICAL_PENDING':logical})
                setattr(ledger,name,MethodType(replacement,ledger))
            effective_global=ledger.global_unresolved
            ledger._dynteam_effective_global_unresolved=effective_global
            # Keep original scientific closure arithmetic over EFFECTIVE raw
            # occupancy, not a physical view (otherwise charged/closed UNKNOWN
            # gets subtracted twice and logical counts can become negative).
            function=ledger.global_logical_unresolved.__func__
            need(function.__code__.co_names.count('global_unresolved')==1,
                 'DYNTEAM_ORIGINAL_ONE_LOGICAL_CAPACITY_REFERENCE')
            code=function.__code__.replace(co_names=tuple('_dynteam_effective_global_unresolved'
                if name=='global_unresolved' else name for name in function.__code__.co_names))
            ledger.global_logical_unresolved=MethodType(clone(function,code=code),ledger)
            function=effective_global.__func__
            ledger.global_unresolved=MethodType(clone(function,code=physical_code(function.__code__)),ledger)
            self.original_effective_reserve=ledger.reserve
            owner=self
            def physical_reserve(this,t,role,generation,rid,upper,proof_sha):
                with this.mutex:
                    need(owner.search_count(t,role)==0,'ROLE_ALREADY_INFLIGHT')
                    need(owner.search_count(t)<this.account(t)['request_cap'],'TRAJECTORY_CAPACITY')
                    return owner.original_effective_reserve(t,role,generation,rid,upper,proof_sha)
            ledger.reserve=MethodType(physical_reserve,ledger)
            ledger._dynteam_v2_dispositions=self
            self.gates=[];self.engines=[];self.servers=[]

    def search_count(self,t=None,role=None):
        sql="SELECT COUNT(*) FROM upstream_effective_requests WHERE state IN ('RESERVED','SENT','UNKNOWN') AND "+PHYSICAL_TERMINAL
        args=[]
        if t is not None:sql+=' AND trajectory=?';args.append(t)
        if role is not None:sql+=' AND role=?';args.append(role)
        with self.ledger.mutex:return self.ledger.db.execute(sql,args).fetchone()[0]

    def bind_gate(self,gate):
        need(gate.ledger is self.ledger and not gate.waiters and gate not in self.gates,
             'DYNTEAM_V2_PHYSICAL_GATE_SAME_ORIGINAL_COLD')
        function=gate.reserve.__func__
        code=physical_code(self.original.changed_code(function.__code__))
        gate.reserve=MethodType(clone(function,code=code),gate)
        self.gates.append(gate)
        return gate

    def bind_engine(self,engine,*,original_transport):
        transport_function=engine.transport
        native_transport_cell=(transport_function.__closure__[transport_function.__code__.co_freevars.index('transport')]
            if inspect.isfunction(transport_function) and 'transport' in transport_function.__code__.co_freevars else None)
        need(type(engine) is ScientificRelay and engine.budget is self.ledger and
             type(engine.ledger) is ScientificUsage and engine not in self.engines and
             type(original_transport) is ChatTransport and native_transport_cell is not None and
             native_transport_cell.cell_contents is original_transport and
             engine.ledger.admission_gate in self.gates,
             'DYNTEAM_ORIGINAL_TRANSPORT_USAGE_AND_BOUND_GATE_REQUIRED')
        usage=engine.ledger;original=usage.record;owner=self
        transport_sha=hashlib.sha256(inspect.getsource(ChatTransport).encode()).hexdigest()
        def record(this,rid,identity,kind,request_sha,*,response=None,usage=None,code=None):
            if usage is None and kind=='UNKNOWN' and code in ('UPSTREAM_HTTP_429','UPSTREAM_HTTP_503'):
                # The ORIGINAL transport closed HTTPError before emitting this
                # fixed public enum. No parsing messages/response body, no
                # status-prefix guessing, no fabricated usage or model retry.
                try:
                    with owner.ledger.mutex:
                        r=owner.ledger.db.execute('SELECT trajectory,role FROM requests WHERE id=?',(rid,)).fetchone()
                        need(r is not None and tuple(r)==identity,'DYNTEAM_REJECTION_SAME_ORIGINAL_REQUEST_IDENTITY')
                        return owner.original.reject(owner.ledger,rid,int(code[-3:]),dict(
                            kind='ORIGINAL_CHAT_TRANSPORT_CLOSED_EXPLICIT_HTTP_ERROR',
                            transport_sha256=transport_sha,public_code=code,request_sha256=request_sha))
                finally:this.admission_gate.notify()
            return original(rid,identity,kind,request_sha,response=response,usage=usage,code=code)
        usage.record=MethodType(record,usage);self.engines.append(engine)
        return engine

    def bind_http_custodian(self,server):
        from native_scientific_http import NativeScientificHttpServer
        need(type(server) is NativeScientificHttpServer and server.ledger is self.ledger and
             server.engine in self.engines and server not in self.servers and not server.listener_stopped,
             'DYNTEAM_V2_DISPOSITION_SAME_COLD_ORIGINAL_HTTP_CUSTODIAN')
        function=server.close_after_drained.__func__
        code=physical_code(self.original.changed_code(function.__code__))
        server.close_after_drained=MethodType(clone(function,code=code),server)
        self.servers.append(server)
        return server

    def public(self):
        return dict(original_v2_source_sha256=ORIGINAL_SHA,same_original_connection=self.ledger.db is self.raw_connection,
            class_or_other_instances_mutated=False,original_unknown_charge_and_stop_rules_retained=True,
            request_rows_reclassified=False,requests_replayed=0,automatic_retries=0,
            physical_SEARCH_slots=self.search_count(),logical_unresolved=self.ledger.global_logical_unresolved(),
            health_probe_or_full_AUX_terminal_projection_qualified=False)
