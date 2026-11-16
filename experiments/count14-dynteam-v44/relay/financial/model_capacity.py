"""Single-owner SEARCH+AUX physical model capacity, separate from AUX finances.

Same database/mutex as search admission, not an independent per-finalizer semaphore.
The controller registers trusted native scopes; workers cannot allocate one. A
native logical UNKNOWN_CHARGED never releases physical custody. A missing owner
or interrupted permit remains occupied and is never automatically replayed.
This manages this adapter's allocation; external L0EG allocation is a deployment
port/contract, not evidence manufactured here that all gateway clients use it.
"""
import json,uuid
from common import need,integer,ident,sha,digest,wire

class ModelCapacity:
    def __init__(self,ledger,*,native_transport_sha256,native_classifier_sha256,global_allocated_cap=96,auxiliary_cap=16):
        integer(global_allocated_cap,'CAPACITY_GLOBAL',1);integer(auxiliary_cap,'CAPACITY_AUX',1)
        need(auxiliary_cap<=global_allocated_cap<=96,'CAPACITY_LIMITS')
        self.transport_pin=sha(native_transport_sha256);self.classifier_pin=sha(native_classifier_sha256)
        need(not hasattr(ledger,'model_capacity_owner_epoch'),'CAPACITY_ALREADY_OWNED');ledger.model_capacity_global_cap=global_allocated_cap
        self.ledger=ledger;self.global_cap=global_allocated_cap;self.aux_cap=auxiliary_cap;self.epoch=uuid.uuid4().hex;self.authorizers={};ledger.model_capacity_owner_epoch=self.epoch
        with ledger.tx():ledger.db.execute("UPDATE model_control SET paused=1,epoch=epoch+1,reason='NEW_CURRENT_OWNER_REQUIRES_RELEASE' WHERE singleton=1")
    def release(self,*,owner_evidence):
        # Host-only publication after the controller actually checks original
        # health and shared allocation. Not exposed to final children over RPC.
        need(type(owner_evidence)is dict and set(owner_evidence)=={'current_owner_authorized','gateway_health_sha256','allocation_sha256'}and owner_evidence['current_owner_authorized']is True,'CAPACITY_FRESH_OWNER_RELEASE_REQUIRED')
        sha(owner_evidence['gateway_health_sha256']);sha(owner_evidence['allocation_sha256'])
        with self.ledger.tx():
            self.ledger.db.execute("UPDATE model_control SET paused=0,epoch=epoch+1,reason='CURRENT_OWNER_RELEASED' WHERE singleton=1")
            self.ledger.event('AUX_CONTROL','MODEL_CAPACITY_RELEASE',{'evidence_sha256':digest(owner_evidence),'global_allocated_cap':self.global_cap,'auxiliary_cap':self.aux_cap})
    def pause(self,scope,metadata):
        allowed={'http_status','error_type','timeout','setting','role','request_id','charged_tokens','classification','finalization'}
        need(type(metadata)is dict and set(metadata)<=allowed,'CAPACITY_INCIDENT_METADATA_ONLY')
        if 'error_type'in metadata:ident(metadata['error_type'])
        if 'request_id'in metadata:ident(metadata['request_id'])
        if 'http_status'in metadata:need(metadata['http_status']is None or type(metadata['http_status'])is int and 100<=metadata['http_status']<=599,'CAPACITY_INCIDENT_HTTP')
        if 'charged_tokens'in metadata:integer(metadata['charged_tokens'],'CAPACITY_INCIDENT_TOKENS')
        for key in ('timeout','finalization'):
            if key in metadata:need(type(metadata[key])is bool,'CAPACITY_INCIDENT_BOOL')
        if 'classification'in metadata:need(metadata['classification']in ('REJECTED_PREGEN','RETRYABLE_REJECTED','UNKNOWN_CHARGED'),'CAPACITY_INCIDENT_CLASSIFICATION')
        if 'setting'in metadata:need(metadata['setting']in ('Agensh-16','Agensh-1'),'CAPACITY_INCIDENT_SETTING')
        if 'role'in metadata:need(metadata['role']=='single','CAPACITY_INCIDENT_ROLE')
        with self.ledger.tx():
            s=self._scope(scope);self.ledger.db.execute("UPDATE model_control SET paused=1,epoch=epoch+1,reason='NATIVE_FINAL_INCIDENT' WHERE singleton=1")
            self.ledger.event(s['trajectory'],'NATIVE_FINAL_REQUESTED_PAUSE',metadata)
        return True
    def state(self,scope):
        with self.ledger.mutex:
            self._scope(scope);r=self.ledger.db.execute('SELECT * FROM model_control WHERE singleton=1').fetchone()
            return {'mode':'PAUSED'if r['paused']else'RUNNING','epoch':r['epoch'],'reason':r['reason'],'auto_resume_enabled':False}
    def register_scope(self,binding,*,authorize):
        need(type(binding)is dict and binding.get('schema')=='count14-agensh-native-final-binding-v1'and binding.get('purpose')=='AUX_FINALIZATION','AUX_SCOPE_IDENTITY')
        from r16_natural_contract import natural_binding
        nm=natural_binding(binding)
        need(binding.get('setting')in ('Agensh-16','Agensh-1')and type(binding.get('target_tokens'))is int and (nm is not None or binding['target_tokens']in (10000000,20000000))and type(binding.get('replicate_index'))is int and binding['replicate_index']in (1,2,3),'AUX_SCOPE_IDENTITY')
        for key in ('manifest_sha256','input_policy_sha256','model_policy_sha256','rng_policy_sha256'):sha(binding.get(key))
        need(callable(authorize),'AUX_SCOPE_NATIVE_AUTHORITY_REQUIRED');t=binding.get('trajectory');scope=digest(binding)
        with self.ledger.tx():
            a=self.ledger.account(t);need(a['manifest_sha']==binding['manifest_sha256'],'AUX_SCOPE_MANIFEST')
            old=self.ledger.db.execute('SELECT binding,epoch FROM aux_scopes WHERE scope=?',(scope,)).fetchone()
            if old is None:self.ledger.db.execute('INSERT INTO aux_scopes VALUES(?,?,?,?)',(scope,t,wire(binding).decode(),self.epoch));self.ledger.event(t,'AUX_SCOPE_REGISTERED',{'scope':scope,'binding_sha256':scope})
            else:need(old['binding']==wire(binding).decode()and old['epoch']==self.epoch,'AUX_PREVIOUS_OWNER_NO_REBIND')
            self.authorizers[scope]=authorize
        return scope
    def _scope(self,scope):
        sha(scope);row=self.ledger.db.execute('SELECT * FROM aux_scopes WHERE scope=?',(scope,)).fetchone()
        need(row is not None and row['epoch']==self.epoch and scope in self.authorizers,'AUX_SCOPE_NOT_CURRENT')
        need(self.authorizers[scope]()is True,'AUX_NATIVE_OWNER_NOT_CURRENT');return row
    def acquire(self,scope,permit_id):
        ident(permit_id)
        with self.ledger.tx():
            s=self._scope(scope);old=self.ledger.db.execute('SELECT * FROM aux_permits WHERE id=?',(permit_id,)).fetchone()
            if old is not None:
                need(old['scope']==scope and old['epoch']==self.epoch and old['state']=='RESERVED','AUX_PERMIT_ALREADY_USED_NO_REPLAY');return dict(old)
            if self.ledger.model_paused():return None
            n=self.ledger.db.execute("SELECT COUNT(*) FROM aux_permits WHERE state IN ('RESERVED','SENT','UNKNOWN')").fetchone()[0]
            if n>=self.aux_cap or self.ledger.global_unresolved()>=self.global_cap:return None
            self.ledger.db.execute("INSERT INTO aux_permits VALUES(?,?,?,'RESERVED',NULL,NULL)",(permit_id,scope,self.epoch));self.ledger.event(s['trajectory'],'AUX_PERMIT_RESERVED',{'permit_id':permit_id,'scope':scope,'billing_domain':'AUX_FINALIZATION','physical_capacity_only':True})
            return dict(self.ledger.db.execute('SELECT * FROM aux_permits WHERE id=?',(permit_id,)).fetchone())
    def _permit(self,scope,permit_id):
        s=self._scope(scope);p=self.ledger.db.execute('SELECT * FROM aux_permits WHERE id=?',(permit_id,)).fetchone()
        need(p is not None and p['scope']==scope and p['epoch']==self.epoch,'AUX_PERMIT_SCOPE');return s,p
    def sent(self,scope,permit_id,request_id):
        ident(request_id)
        with self.ledger.tx():
            s,p=self._permit(scope,permit_id);need(p['state']=='RESERVED','AUX_ALREADY_SENT_NO_REPLAY')
            # Last durable admission boundary, serialized with owner PAUSED.
            # Explicit False is an unsent HOLD, not failure/UNKNOWN or a retry.
            if self.ledger.model_paused():return False
            self.ledger.db.execute("UPDATE aux_permits SET state='SENT',request_id=? WHERE id=?",(request_id,permit_id));self.ledger.event(s['trajectory'],'AUX_MODEL_SENT',{'permit_id':permit_id,'request_id':request_id,'scope':scope});return True
    def unknown(self,scope,permit_id,proof_sha256):
        sha(proof_sha256)
        with self.ledger.tx():
            s,p=self._permit(scope,permit_id);need(p['state']in ('SENT','UNKNOWN'),'AUX_UNKNOWN_WITHOUT_SEND')
            self.ledger.db.execute("UPDATE aux_permits SET state='UNKNOWN' WHERE id=?",(permit_id,));self.ledger.event(s['trajectory'],'AUX_MODEL_POSSIBLE_EXECUTION',{'permit_id':permit_id,'proof_sha256':proof_sha256,'slot_retained':True})
    def _terminal(self,scope,permit_id,proof_sha256,kind):
        sha(proof_sha256)
        with self.ledger.tx():
            s,p=self._permit(scope,permit_id)
            if p['state']=='TERMINAL':need(p['terminal_sha']==proof_sha256,'AUX_TERMINAL_CONFLICT');return
            need(p['state']in ('SENT','UNKNOWN'),'AUX_TERMINAL_WITHOUT_SEND')
            self.ledger.db.execute("UPDATE aux_permits SET state='TERMINAL',terminal_sha=? WHERE id=?",(proof_sha256,permit_id));self.ledger.event(s['trajectory'],kind,{'permit_id':permit_id,'proof_sha256':proof_sha256})
    def provider_terminal(self,scope,permit_id,proof):
        need(type(proof)is dict and set(proof)=={'kind','provider_terminal','request_id','transport_source_sha256','receipt_sha256'}and proof.get('kind')=='ORIGINAL_STREAM_RETURNED_VALID_USAGE_AND_FINISH'and proof.get('request_id')and proof.get('provider_terminal')is True,'AUX_PROVIDER_TERMINAL_REQUIRED')
        for key in ('transport_source_sha256','receipt_sha256'):sha(proof.get(key))
        need(proof['transport_source_sha256']==self.transport_pin,'AUX_NATIVE_TRANSPORT_PIN')
        with self.ledger.mutex:
            _,p=self._permit(scope,permit_id);need(p['request_id']==proof['request_id'],'AUX_TERMINAL_REQUEST_ID')
        self._terminal(scope,permit_id,digest(proof),'AUX_MODEL_PHYSICAL_TERMINAL')
    def pre_generation_rejected(self,scope,permit_id,proof):
        # The original frozen v54 classifier (including its authorized pre-stream
        # 503 policy) owns this classification. This is not UNKNOWN_CHARGED.
        need(type(proof)is dict and set(proof)=={'kind','classification','stream_started','classifier_source_sha256','receipt_sha256','request_id'}and proof.get('kind')=='ORIGINAL_V54_PREGEN_CLASSIFICATION'and proof.get('classification')in ('REJECTED_PREGEN','RETRYABLE_REJECTED')and proof.get('stream_started')is False,'AUX_NO_EXECUTION_PROOF_REQUIRED')
        sha(proof.get('classifier_source_sha256'));sha(proof.get('receipt_sha256'));need(proof['classifier_source_sha256']==self.classifier_pin,'AUX_NATIVE_CLASSIFIER_PIN')
        with self.ledger.mutex:
            _,p=self._permit(scope,permit_id);need(p['request_id']==proof.get('request_id'),'AUX_TERMINAL_REQUEST_ID')
        self._terminal(scope,permit_id,digest(proof),'AUX_MODEL_NO_EXECUTION_TERMINAL')
    def cancel_unsent(self,scope,permit_id):
        with self.ledger.tx():
            s,p=self._permit(scope,permit_id);need(p['state']=='RESERVED','AUX_POSSIBLE_EXECUTION_NO_RELEASE')
            self.ledger.db.execute("UPDATE aux_permits SET state='CANCELLED_UNSENT' WHERE id=?",(permit_id,));self.ledger.event(s['trajectory'],'AUX_CANCELLED_UNSENT',{'permit_id':permit_id})
    def frontier(self,scope):
        with self.ledger.mutex:
            self._scope(scope);rows=self.ledger.db.execute('SELECT state,COUNT(*) FROM aux_permits WHERE scope=? GROUP BY state',(scope,)).fetchall()
            counts={r[0]:r[1]for r in rows};return {'scope':scope,'counts':counts,'unresolved':sum(counts.get(s,0)for s in ('RESERVED','SENT','UNKNOWN')),'global_unresolved':self.ledger.global_unresolved(),'global_allocated_cap':self.global_cap}
