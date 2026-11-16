"""Budgeted Responses relay, built on unchanged qualified conversion bytes.

Does not acquire or infer real gateway capacity. The reservation policy is
explicitly either a pinned verified upstream ceiling (legacy strict mode) or
a user-authorized LOCAL planning allowance, never claimed as a platform fact.
Actual usage is always settled; overruns retain charges and fault, never replay.
Search only, never AUX credentials.
"""
import os as _count14_os  # endpoints/keys come from environment; see CONFIGURATION.md
from pathlib import Path
import copy,json,os,sqlite3,threading,uuid
from common import hash_file,need,Refused,sha,digest,wire,private_dir,integer
from protocol import Rejected,prepare,assistant_history
from budget import TOOL_CUSTODY_AUDIT_CODES
from feasibility_relay import RelayEngine

class Bounds:
    CONTEXT_FIELDS={'schema','model','maximum_context_tokens','server_enforces_context_ceiling','scope','source_url','model_metadata_sha256','metadata_get_evidence_sha256','wire_policy'}
    @staticmethod
    def api_context(proof,expected_sha):
        need(type(proof)is dict and set(proof)==Bounds.CONTEXT_FIELDS,'API_CONTEXT_PROOF_FIELDS')
        need(digest(proof)==sha(expected_sha),'API_CONTEXT_PROOF_PIN')
        need(proof['schema']=='agensh-api-context-reservation-proof-v1'and
             proof['scope']=='ENTIRE_EXPANDED_CHAT_PROMPT_TOOLS_AND_OUTPUT'and
             proof['wire_policy']=='PASSTHROUGH_CLIENT_MAX_ELSE_OMIT'and
             proof['server_enforces_context_ceiling']is True,'API_CONTEXT_PROOF_SCOPE')
        integer(proof['maximum_context_tokens'],'API_CONTEXT_LIMIT',1)
        need(type(proof['model'])is str and 0<len(proof['model'])<=128,'API_CONTEXT_MODEL')
        need(type(proof['source_url'])is str and proof['source_url'].startswith('https://')and
             proof['source_url'].endswith('/v1/models'),'API_CONTEXT_METADATA_SOURCE')
        sha(proof['model_metadata_sha256']);sha(proof['metadata_get_evidence_sha256'])
        return proof['maximum_context_tokens']
    def matches_model(self,model):
        # Original msg221 exact logical-policy -> PR1 wire-model registration.
        # API proof bytes remain immutable; non-context bounds stay exact.
        return model==self.proof['model'] or (
            self.context_limit is not None and
            self.proof['source_url']==(_count14_os.environ.get('COUNT14_GLM_BASE_URL', 'https://glm-gateway.example.invalid/v1').rstrip('/') + '/models') and
            (model,self.proof['model'])==('VLLM-GATEWAY-GLM-5.3-FP8','GLM-5.3-FP8'))
    def output_accounting_limit(self,chat,*,input_tokens=0):
        maximum=chat.get('max_tokens')
        if self.context_limit is not None:
            if maximum is not None:integer(maximum,'AGENT_MAX_OUTPUT',1)
            # This is an accounting ceiling implied by TOTAL context, not a
            # claimed independent API output limit and never a wire clamp.
            integer(input_tokens,'ACTUAL_INPUT_TOKENS')
            remaining=self.context_limit-input_tokens
            return remaining if maximum is None else min(remaining,maximum)
        integer(maximum,'MAX_OUTPUT',1)
        return maximum
    def usage_breach(self,chat,usage):
        output_bad=usage['output_tokens']>self.output_accounting_limit(chat,input_tokens=usage['input_tokens'])
        total_bad=(self.context_limit is not None and
                   usage['input_tokens']+usage['output_tokens']>self.context_limit)
        if usage['input_tokens']>self.prompt_limit or output_bad or total_bad:
            return ('UPSTREAM_TOKEN_BOUND_VIOLATION' if self.server_token_ceiling_verified or output_bad
                    else 'LOCAL_PROMPT_RESERVATION_EXCEEDED_USAGE_RETAINED')
        return None
    FIELDS={'schema','model','maximum_prompt_tokens','maximum_output_tokens','prompt_limit_source_sha256','output_limit_source_sha256','server_enforces_prompt_ceiling','server_enforces_output_ceiling','scope'}
    CONFIGURED_FIELDS={'schema','model','prompt_reservation_tokens','maximum_output_tokens','scope'}
    @staticmethod
    def configured(model,maximum_output,*,prompt_reservation_tokens=262144):
        """Local accounting plan, NOT a tokenizer or a verified server bound.

        262144 is a configured planning allowance, not a platform assertion.
        max_output remains an explicit relay/wire limit; actual usage decides
        all charges, and any planning overrun faults without rewriting history.
        """
        integer(prompt_reservation_tokens,'PROMPT_RESERVATION',1)
        integer(maximum_output,'OUTPUT_LIMIT',1)
        need(type(model)is str and 0<len(model)<=128,'RESERVATION_MODEL')
        return {'schema':'agensh-local-reservation-policy-v1','model':model,
                'prompt_reservation_tokens':prompt_reservation_tokens,
                'maximum_output_tokens':maximum_output,
                'scope':'LOCAL_PLANNING_NOT_VERIFIED_SERVER_CEILING'}
    def __init__(self,proof,expected_sha):
        need(type(proof)is dict,'RESERVATION_PROOF_FIELDS')
        self.context_limit=None
        if proof.get('schema')=='agensh-api-context-reservation-proof-v1':
            self.context_limit=self.api_context(proof,expected_sha)
            self.prompt_limit=self.context_limit
            self.kind='VERIFIED_API_TOTAL_CONTEXT_CEILING'
            self.server_token_ceiling_verified=True
            self.proof=copy.deepcopy(proof);self.sha=expected_sha
            return
        local=proof.get('schema')=='agensh-local-reservation-policy-v1'
        need(set(proof)==(self.CONFIGURED_FIELDS if local else self.FIELDS),'RESERVATION_PROOF_FIELDS')
        need(digest(proof)==sha(expected_sha),'RESERVATION_PROOF_PIN')
        if local:
            need(proof['scope']=='LOCAL_PLANNING_NOT_VERIFIED_SERVER_CEILING','LOCAL_RESERVATION_SCOPE')
            integer(proof['prompt_reservation_tokens'],'PROMPT_RESERVATION',1)
            need(type(proof['model'])is str and 0<len(proof['model'])<=128,'RESERVATION_MODEL')
            self.prompt_limit=proof['prompt_reservation_tokens'];self.kind='LOCAL_CONFIGURED_PLANNING'
        else:
            need(proof['schema']=='agensh-upstream-reservation-proof-v1' and proof['scope']=='ENTIRE_EXPANDED_CHAT_PROMPT_AND_TOOLS','UNSUPPORTED_RELIABLE_RESERVATION')
            need(proof['server_enforces_prompt_ceiling']is True and proof['server_enforces_output_ceiling']is True,'UNSUPPORTED_RELIABLE_RESERVATION')
            integer(proof['maximum_prompt_tokens'],'PROMPT_LIMIT',1)
            sha(proof['prompt_limit_source_sha256']);sha(proof['output_limit_source_sha256'])
            self.prompt_limit=proof['maximum_prompt_tokens'];self.kind='VERIFIED_UPSTREAM_CEILING'
        integer(proof['maximum_output_tokens'],'OUTPUT_LIMIT',1)
        self.server_token_ceiling_verified=not local
        self.proof=copy.deepcopy(proof);self.sha=expected_sha
    def upper(self,chat):
        need(self.matches_model(chat['model']),'PROOF_MODEL_MISMATCH')
        if self.context_limit is not None:
            self.output_accounting_limit(chat)
            # Real API total-context ceiling: safe without reading/tokenizing
            # prompts or pretending to know this request's exact input count.
            return self.context_limit
        maximum=chat['max_tokens'];integer(maximum,'MAX_OUTPUT',1)
        need(maximum<=self.proof['maximum_output_tokens'],'OUTPUT_CAP_NOT_PROVEN' if self.server_token_ceiling_verified else 'OUTPUT_CAP_EXCEEDS_LOCAL_POLICY')
        # Includes resumed history/tools in the planning allowance, but LOCAL
        # mode deliberately makes NO claim that a server enforces this input cap.
        return self.prompt_limit+maximum

class PrivateStates:
    """Private durable continuation text; not a public ledger or report log."""
    def __init__(self,home,*,unmanaged_cli=False):
        home=private_dir(home,create=True);p=home/'continuations.sqlite';need(not p.is_symlink(),'CONTINUATION_SYMLINK')
        self.lock=threading.RLock();self.db=sqlite3.connect(p,check_same_thread=False,isolation_level=None);os.chmod(p,0o600)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS states(id TEXT PRIMARY KEY,body BLOB NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS parked(id TEXT PRIMARY KEY,identity BLOB NOT NULL,request BLOB NOT NULL,generation INTEGER)')
        if not unmanaged_cli:self.db.execute('CREATE TABLE IF NOT EXISTS tools(trajectory TEXT NOT NULL,role TEXT NOT NULL,call_id TEXT NOT NULL,operation_id TEXT NOT NULL,PRIMARY KEY(trajectory,role,call_id))')
    def __len__(self):
        with self.lock:return self.db.execute('SELECT COUNT(*) FROM states').fetchone()[0]
    def get(self,key):
        with self.lock:
            r=self.db.execute('SELECT body FROM states WHERE id=?',(key,)).fetchone()
            if not r:return None
            d=json.loads(r[0]);d['identity']=tuple(d['identity']);return d
    def __setitem__(self,key,value):
        with self.lock:self.db.execute('INSERT INTO states VALUES(?,?)',(key,wire(value)))
    def tool(self,identity,call_id):
        with self.lock:
            r=self.db.execute('SELECT operation_id FROM tools WHERE trajectory=? AND role=? AND call_id=?',(*identity,call_id)).fetchone();return r[0]if r else None
    def add_tool(self,identity,call_id,op):
        with self.lock:self.db.execute('INSERT INTO tools VALUES(?,?,?,?)',(*identity,call_id,op))
    def park(self,rid,identity,request):
        with self.lock:self.db.execute('INSERT INTO parked VALUES(?,?,?,NULL)',(rid,wire(identity),wire(request)))
    def admitted(self,rid,generation):
        with self.lock:self.db.execute('UPDATE parked SET generation=? WHERE id=?',(generation,rid))
    def backup(self,destination):
        # Native SQLite backup under the same mutex as continuation/tool writes.
        # Never copy a live database file or WAL as an ordinary workspace file.
        p=Path(destination);need(not p.exists() and not p.is_symlink(),'CONTINUATION_BACKUP_NO_CLOBBER')
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd)
        with self.lock:
            target=sqlite3.connect(p)
            try:self.db.backup(target)
            finally:target.close()
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
        return hash_file(p)
    def close(self):self.db.close()

class _AnonymousStreamSanity:
    """Counts/booleans/enums ONLY; never retain a delta, tool body or raw ID."""
    FINISH = frozenset(('stop','length','tool_calls','content_filter'))
    def __init__(self, maximum):
        self.maximum=maximum
        self.chunks=0;self.iterator_returned=False;self.invalid_shape=False
        self.content=False;self.reasoning=False;self.tools=False
        self.content_chunks=0;self.reasoning_chunks=0;self.tool_chunks=0
        self.finishes={}
    def feed(self, chunk):
        self.chunks+=1
        if type(chunk)is not dict:self.invalid_shape=True;return
        choices=chunk.get('choices',[])
        if type(choices)is not list:self.invalid_shape=True;return
        if len(choices)>1:self.invalid_shape=True
        for choice in choices[:1]:
            if type(choice)is not dict:self.invalid_shape=True;continue
            delta=choice.get('delta',{})
            if type(delta)is not dict:self.invalid_shape=True;continue
            text=type(delta.get('content'))is str and len(delta['content'])>0
            reason=any(type(delta.get(k))is str and len(delta[k])>0
                       for k in ('reasoning','reasoning_content'))
            tools=type(delta.get('tool_calls'))is list and len(delta['tool_calls'])>0
            self.content=self.content or text;self.reasoning=self.reasoning or reason;self.tools=self.tools or tools
            self.content_chunks+=int(text);self.reasoning_chunks+=int(reason);self.tool_chunks+=int(tools)
            if choice.get('finish_reason')is not None:
                value=choice['finish_reason'];key=value if type(value)is str and value in self.FINISH else 'OTHER'
                self.finishes[key]=self.finishes.get(key,0)+1
    def public(self,response,kind):
        content=tools=reasoning=None;status=None
        if type(response)is dict and type(response.get('output'))is list:
            content=tools=reasoning=False
            for item in response['output']:
                if type(item)is not dict:continue
                if item.get('type')=='function_call':tools=True
                if item.get('type')=='reasoning':reasoning=True
                if item.get('type')=='message'and type(item.get('content'))is list:
                    content=content or any(type(p)is dict and type(p.get('text'))is str and len(p['text'])>0 for p in item['content'])
            value=response.get('status');status=value if value in ('completed','incomplete','failed','in_progress')else 'OTHER'
        return dict(schema='count14-anonymous-upstream-mapper-response-sanity-v1',
            wire_max_tokens=self.maximum,wire_max_tokens_present=self.maximum is not None,
            upstream_chunk_count=self.chunks,
            upstream_content_nonempty=self.content,upstream_reasoning_nonempty=self.reasoning,
            upstream_tool_calls_nonempty=self.tools,upstream_content_chunk_count=self.content_chunks,
            upstream_reasoning_chunk_count=self.reasoning_chunks,upstream_tool_chunk_count=self.tool_chunks,
            upstream_finish_reason_counts=dict(self.finishes),original_iterator_returned=self.iterator_returned,
            upstream_invalid_shape_observed=self.invalid_shape,mapped_content_nonempty=content,
            mapped_reasoning_item_present=reasoning,mapped_tool_calls_nonempty=tools,mapped_status=status,
            original_record_kind=kind if kind in ('COMPLETED','ACCOUNTED_ERROR','UNKNOWN')else 'OTHER',
            agent_or_ACP_received_NOT_proven=True)

class ScientificUsage:
    def __init__(self,ledger,bounds,states,*,global_allocated_cap,admission_gate=None,profile=None,tool_parents=None):
        self.tool_parents=tool_parents
        self.anonymous_response_metadata_unavailable=False
        need(tool_parents is None or tool_parents.ledger is ledger,'NATIVE_MODEL_PARENT_SAME_LEDGER')
        integer(global_allocated_cap,'ALLOCATED_CAP',1);need(global_allocated_cap<=96,'ALLOCATED_CAP');self.global_cap=global_allocated_cap;self.admission_gate=admission_gate
        self.ledger,self.bounds,self.states=ledger,bounds,states;self.scope=threading.local();self.profile=profile
    def begin(self,rid,identity,request_sha,limit):
        s=self.scope.value;t,role=identity;custody=s.get('http_custody')
        try:
            if custody is not None:custody.bind(rid,identity,request_sha)
            need(not hasattr(self.ledger,'model_capacity_global_cap')or self.ledger.model_capacity_global_cap==self.global_cap,'SHARED_CAPACITY_ALLOCATION_BINDING')
            # Cross-trajectory cap and reservation share one durable writer.
            with self.ledger.mutex:
                n=self.ledger.global_unresolved()
                if self.admission_gate is None:need(not self.ledger.model_paused(),'MODEL_CAPACITY_OWNER_PAUSED');need(n<self.global_cap,'GLOBAL_ALLOCATED_CAPACITY')
                else:need(self.admission_gate.ledger is self.ledger and self.admission_gate.global_cap==self.global_cap,'ADMISSION_GATE_CAPACITY_BINDING')
                if self.admission_gate is None:self.ledger.reserve(t,role,s['generation'],rid,s['upper'],self.bounds.sha)
            if self.admission_gate is not None:
                s['generation']=self.admission_gate.reserve(t,role,rid,s['upper'],self.bounds.sha,s['chat'],pending_store=self.states,admission_guard=None if custody is None else custody.guard)
            try:
                if custody is not None:custody.confirm_before_send()
                with self.ledger.mutex:
                    if custody is not None:custody.guard()
                    if self.profile is not None:s['rng']=self.profile.reserve_rng(self.ledger,t,role,rid)
                    with self.ledger.tx():self.ledger.event(t,'REQUEST_PAYLOAD_PIN',{'request_id':rid,'request_sha256':request_sha,'billing_domain':'SEARCH','model':s['chat']['model'],'reservation_policy_sha256':self.bounds.sha,'reservation_policy_kind':self.bounds.kind,'server_token_ceiling_verified':self.bounds.server_token_ceiling_verified})
                    self.ledger.sent(rid)
            except Refused:
                with self.ledger.mutex:
                    row=self.ledger.db.execute('SELECT state FROM requests WHERE id=?',(rid,)).fetchone()
                    if row is not None and row[0]=='RESERVED':self.ledger.cancel_unsent(rid)
                raise
            s.update(rid=rid,identity=identity)
        except Refused as e:raise Rejected(e.code,429 if 'CAPACITY'in e.code or 'BOUNDARY'in e.code else 409)from None
        except sqlite3.Error:
            self.ledger.latch_fault(t,'SEARCH_ADMISSION_STORAGE_FAILURE');raise Rejected('SEARCH_ADMISSION_STORAGE_FAILURE_NO_RETRY',502)from None
    def fault(self,t,code):
        self.ledger.latch_fault(t,code)
        with self.ledger.tx():
            self.ledger.db.execute("UPDATE accounts SET state='FAULT' WHERE trajectory=?",(t,));self.ledger.event(t,'RELAY_STOPPED',{'code':code})
    def record(self,rid,identity,kind,request_sha,*,response=None,usage=None,code=None):
        t,role=identity;s=self.scope.value
        try:
            with self.ledger.mutex:r=self.ledger.db.execute('SELECT state FROM requests WHERE id=?',(rid,)).fetchone()
            if r and (r[0]=='SETTLED' or self.ledger.unknown_charged(rid)):return # preserve an already-measured breach; no second charge or UNKNOWN overwrite
            observation=s.get('anonymous_response_sanity')
            if type(observation)is _AnonymousStreamSanity and not s.get('anonymous_receipt_written',False):
                metadata=observation.public(response,kind)
                metadata.update(role=role,role_action_index=(s.get('rng')or{}).get('action_index'))
                metadata.update(reported_input_tokens=None if usage is None else usage.get('input_tokens'),
                                reported_output_tokens=None if usage is None else usage.get('output_tokens'))
                # Append metadata only. Never change requests/usage/UNKNOWN or
                # propagate observer storage errors into a paid stream.
                try:
                    with self.ledger.tx():self.ledger.event(t,'ANONYMOUS_MODEL_RESPONSE_SANITY',metadata)
                    s['anonymous_receipt_written']=True
                except Exception:
                    self.anonymous_response_metadata_unavailable=True
            if usage is None:self.ledger.unknown(rid,code or'RELAY_UNKNOWN');return
            calls=[] if getattr(self.ledger,'native_unmanaged_cli',False) else [x['call_id'] for x in (response or{}).get('output',[]) if x.get('type')=='function_call']
            pending=['tool-'+digest({'rid':rid,'call_id':c}) for c in calls]
            receipt=digest({'rid':rid,'usage':usage,'response_sha256':digest(response)if response is not None else None,'terminal_kind':kind,'code':code})
            self.ledger.settle(rid,usage['input_tokens'],usage['output_tokens'],receipt,pending_tools=pending)
            for call,op in zip(calls,pending):
                try:self.states.add_tool(identity,call,op)
                except sqlite3.IntegrityError:
                    self.fault(t,'CONTINUATION_TOOL_ID_CONFLICT');raise Rejected('CONTINUATION_TOOL_ID_CONFLICT',502)from None
            if not getattr(self.ledger,'native_unmanaged_cli',False) and self.tool_parents is not None and response is not None:
                try:self.tool_parents.register_committed_response(rid,identity,response)
                except Exception:
                    self.ledger.latch_fault(t,'NATIVE_TOOL_PARENT_INDEX_UNKNOWN');raise Rejected('NATIVE_TOOL_PARENT_INDEX_UNKNOWN_NO_RETRY',502)from None
            bound_breach=self.bounds.usage_breach(s['chat'],usage)
            if bound_breach is not None:
                code=bound_breach
                self.fault(t,code);raise Rejected(code,502)
            if kind!='COMPLETED':self.fault(t,code or'ACCOUNTED_PROTOCOL_ERROR')
        except Refused as e:raise Rejected(e.code,502)from None
        except sqlite3.Error:
            self.ledger.latch_fault(t,'SEARCH_RECEIPT_STORAGE_FAILURE');raise Rejected('SEARCH_RECEIPT_STORAGE_FAILURE_NO_RETRY',502)from None
        finally:
            sanity=None if self.admission_gate is None else getattr(self.admission_gate,'formal_early_sanity',None)
            if sanity is not None:
                try:sanity.observe(t)
                except Exception as error:
                    with self.ledger.tx():self.ledger.event(t,'FORMAL_EARLY_SANITY_HOLD',{'reasons':['OBSERVER_METADATA_FAILURE'],'exception_type':type(error).__name__,'pause_new_release_only':True,'cancel_sent':False,'replay':False})
            if self.admission_gate is not None:self.admission_gate.notify()
    def totals(self):
        with self.ledger.mutex:
            rows=self.ledger.db.execute("SELECT trajectory,role,COUNT(*),SUM(state='SETTLED'),SUM(COALESCE(input,0)),SUM(COALESCE(output,0)),SUM(state IN ('RESERVED','SENT','UNKNOWN')) FROM requests GROUP BY trajectory,role").fetchall()
            return [dict(trajectory=r[0],agent=r[1],requests=r[2],accounted_requests=r[3],input_tokens=r[4],output_tokens=r[5],unknown_or_inflight=r[6],category='agensh_SEARCH')for r in rows]

class ScientificRelay(RelayEngine):
    def __init__(self,transport,ledger,bounds,private_home,*,model,max_output=None,max_inflight=16,global_allocated_cap=16,max_states=100000,tool_terminal_port=None,admission_gate=None,profile=None,tool_parents=None):
        need(tool_parents is None or tool_parents.ledger is ledger,'NATIVE_MODEL_PARENT_SAME_LEDGER')
        need(bounds.matches_model(model),'PROOF_MODEL_MISMATCH')
        if bounds.context_limit is not None:need(max_output is None,'API_CONTEXT_NO_RELAY_OUTPUT_CAP')
        self.continuations=PrivateStates(private_home,unmanaged_cli=getattr(ledger,'native_unmanaged_cli',False));usage=ScientificUsage(ledger,bounds,self.continuations,global_allocated_cap=global_allocated_cap,admission_gate=admission_gate,profile=profile,tool_parents=tool_parents)
        self.profile=profile;self.private_home=private_home
        def trusted_transport(chat):
            scope=usage.scope.value;need(digest(chat)==digest(scope['chat']),'UPSTREAM_REQUEST_CONSTRUCTION_DRIFT')
            outgoing=profile.upstream(chat,scope['rng']) if profile is not None else chat
            with ledger.tx():ledger.event(scope['identity'][0],'UPSTREAM_PAYLOAD_PIN',{'request_id':scope['rid'],'canonical_chat_sha256':digest(outgoing)})
            observation=_AnonymousStreamSanity(outgoing.get('max_tokens'))
            scope['anonymous_response_sanity']=observation
            original_result=transport(outgoing)
            if not outgoing['stream']:return original_result
            def observed_chunks():
                for chunk in original_result:
                    observation.feed(chunk)
                    yield chunk  # SAME object, same order, no new send or retry.
                observation.iterator_returned=True  # original iterator validated DONE
            return observed_chunks()
        super().__init__(trusted_transport,usage,model=model,max_output=max_output,max_states=max_states,max_inflight=max_inflight,request_limit=None)
        self.states=self.continuations;self.budget=ledger;self.tool_terminal_port=tool_terminal_port
    def retain_continuation(self,request,rid,identity,response,messages):
        # store:false disables client GET/previous-id retrieval, never private
        # scientific checkpoint custody. Full-context replay stays unchanged.
        try:
            with self.lock:
                self.continuations[rid]=dict(identity=identity,response=copy.deepcopy(response),
                    history=messages+[assistant_history(response)],client_store=request.get('store',True))
        except Exception:
            self.budget.latch_fault(identity[0],'SCIENTIFIC_CONTINUATION_STORAGE_FAILURE')
            raise Rejected('SCIENTIFIC_CONTINUATION_STORAGE_FAILURE_NO_RETRY',502)from None
    def lookup(self,ident,identity):
        state=super().lookup(ident,identity)
        if state.get('client_store',True)is not True:raise Rejected('RESPONSE_NOT_FOUND',404)
        return state
    def run(self,request,identity,emit=None,*,http_custody=None):
        committed_stream=None
        try:
            need(type(identity)is tuple and len(identity)==2,'HOST_AUTHENTICATED_IDENTITY_REQUIRED')
            if http_custody is not None:
                from native_scientific_http import NativeHttpRequest
                need(type(http_custody)is NativeHttpRequest and http_custody.engine is self
                     and http_custody.identity==identity,'SCIENTIFIC_HTTP_ORIGINAL_CUSTODY_SCOPE')
            if self.profile is not None:request=self.profile.normalize(request)
            t,role=identity;front=self.budget.frontier(t);self.budget._identity(t,role,front['generation'])
            previous=request.get('previous_response_id');history=[]if previous is None else self.lookup(previous,identity)['history']
            chat,_=prepare(request,history,model=self.model,max_output=self.max_output);upper=self.ledger.bounds.upper(chat)
            if getattr(self.budget,'native_unmanaged_cli',False):
                self.ledger.scope.value={'generation':front['generation'],'upper':upper,'chat':chat,'http_custody':http_custody}
                return super().run(request,identity,emit=emit)
            # Legacy qualified mode only; not installed by new driver.
            # Only original, same-role call IDs release that role's tool custody.
            value=request.get('input');outputs=[]if not isinstance(value,list) else [v['call_id'] for v in value if isinstance(v,dict) and v.get('type')=='function_call_output']
            for call in outputs:
                op=self.continuations.tool(identity,call);need(op is not None,'TOOL_RESULT_NOT_OWNED_BY_THIS_ROLE')
                # Repeated full-context tool history is not a replayed model
                # request. An audited logical release must stay nonblocking.
                if self.budget.tool_audit_released(op,identity,front['generation']):continue
                try:
                    # A worker's function_call_output is not proof that a native
                    # command/tool/background writer has physically finished.
                    need(callable(self.tool_terminal_port),'NATIVE_TOOL_TERMINAL_PORT_NOT_CONFIGURED')
                    receipt=self.tool_terminal_port(identity,front['generation'],call,op)
                    if type(receipt)is dict and 'terminal_scope'in receipt:
                        from native_cli_callback_custody import NativeCliCallbackCustody
                        need(type(self.tool_terminal_port)is NativeCliCallbackCustody,
                             'NATIVE_CALLBACK_CUSTODY_ORIGINAL_HOST_PORT_REQUIRED')
                        self.tool_terminal_port.validate_relay_receipt(receipt,identity,front['generation'],call,op)
                    else:
                        need(type(receipt)is dict and set(receipt)=={'trajectory','role','generation','call_id','operation_id','physical_terminal','receipt_sha256'},'NATIVE_TOOL_TERMINAL_RECEIPT')
                        need((receipt['trajectory'],receipt['role'])==identity and type(receipt['generation'])is int and receipt['generation']==front['generation'] and receipt['call_id']==call and receipt['operation_id']==op,'NATIVE_TOOL_TERMINAL_IDENTITY')
                        need(receipt['physical_terminal']is True,'NATIVE_TOOL_NOT_TERMINAL')
                    sha(receipt['receipt_sha256'])
                    proof_kind='NATIVE_TOOL_TERMINAL_PROOF'
                    proof_meta={'operation_id':op,'role':role,'receipt_sha256':receipt['receipt_sha256']}
                    if 'terminal_scope'in receipt:
                        proof_kind='NATIVE_TOOL_CALLBACK_CUSTODY_PROOF'
                        proof_meta.update(terminal_scope=receipt['terminal_scope'],
                                          writer_custody_sha256=receipt['writer_custody_sha256'],
                                          descendant_terminal_not_claimed=True)
                    with self.budget.tx():self.budget.event(t,proof_kind,proof_meta)
                    self.budget.operation_end(op)
                except Refused as failure:
                    if failure.code not in TOOL_CUSTODY_AUDIT_CODES:raise
                    self.budget.audit_tool_release(op,identity,front['generation'],failure.code)
            # Native CLI variants may omit a returned tool from full-context
            # continuation. Missing logical closure is audit-only as well; the
            # settled model parent and actual native children remain untouched.
            self.budget.audit_role_tools(identity,front['generation'],'ROLE_TOOLS_PENDING')
            self.ledger.scope.value={'generation':front['generation'],'upper':upper,'chat':chat,'http_custody':http_custody}
            if emit is not None:
                from native_model_tool_parent import CommittedToolStream
                def committed(event):
                    scope=self.ledger.scope.value;rid=scope['rid'];response=event.get('response',{})
                    with self.budget.mutex:
                        row=self.budget.db.execute('SELECT state,trajectory,role,generation FROM requests WHERE id=?',(rid,)).fetchone()
                        need(response.get('id')==rid and row is not None and tuple(row)==('SETTLED',t,role,scope['generation']),'NATIVE_TOOL_STREAM_BEFORE_LEDGER_COMMIT')
                def deliver(event):
                    try:emit(event)
                    except Exception:
                        self.budget.latch_fault(t,'NATIVE_TOOL_STREAM_DELIVERY_UNKNOWN');raise
                committed_stream=CommittedToolStream(deliver,self.private_home,committed)
            return super().run(request,identity,emit=committed_stream if committed_stream is not None else None)
        except Refused as e:raise Rejected(e.code,409)from None
        finally:
            if committed_stream is not None:committed_stream.close()
            if hasattr(self.ledger.scope,'value'):del self.ledger.scope.value
    def close(self):self.continuations.close()
