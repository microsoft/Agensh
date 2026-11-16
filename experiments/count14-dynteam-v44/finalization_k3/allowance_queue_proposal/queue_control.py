"""Offline proposal: authorized raw>=4 CONTROL carrier on ORIGINAL FinalQueue.

Original financial and job schemas/rows remain intact. Production installation
is NOT authorized here. Only explicit OWN boundaries can execute the new DDL.
No new dispatcher, request replay, allowance, model or custody release exists.
"""
import ast,copy,inspect,os,re
from pathlib import Path
from types import FunctionType,MethodType,SimpleNamespace
from common import need,digest,sha,strict,wire,publish,private_dir,hash_file
from budget import Ledger
from final_queue import FinalQueue,process_identity
import final_queue,final_attempts
from formal_scope import validate_contract,PUBLIC_CONTRACT_CANONICAL_SHA256
from allowance_control import FormalAllowanceControl,read_public,attempt_key
from formal_ast import globals_clone

AUTH='formal_final_control_authorizations_v1'
JOBS='formal_final_control_jobs_v1'
SCHEMA='count14-formal100m-queue-control-domain-proposal-v1'
AUTH_SCHEMA='count14-formal100m-queue-control-registration-public-v1'
CLAIM_SCHEMA='count14-formal100m-queue-control-original-claim-public-v1'
POLICY='USER_20261030_ORIGINAL_ALLOWANCE_PLUS_ONE_THEN_ACTUAL_N'

# Only new CONTROL tables/triggers. No ALTER/UPDATE/DELETE of any old table.
DDL=f'''
CREATE TABLE {AUTH}(id TEXT PRIMARY KEY,metadata TEXT NOT NULL,sha256 TEXT NOT NULL UNIQUE);
CREATE TRIGGER no_update_{AUTH} BEFORE UPDATE ON {AUTH} BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER no_delete_{AUTH} BEFORE DELETE ON {AUTH} BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TABLE {JOBS}(id TEXT PRIMARY KEY REFERENCES {AUTH}(id),point TEXT NOT NULL REFERENCES points,
 replicate INTEGER NOT NULL CHECK(replicate IN(1,2,3)),state TEXT NOT NULL,claim TEXT,child TEXT,
 terminal TEXT,result TEXT,attempt INTEGER NOT NULL CHECK(attempt>=4),original_job TEXT NOT NULL REFERENCES jobs,
 UNIQUE(point,replicate,attempt));
CREATE TRIGGER no_delete_{JOBS} BEFORE DELETE ON {JOBS} BEGIN SELECT RAISE(ABORT,'identity append only'); END;
CREATE TRIGGER no_identity_update_{JOBS} BEFORE UPDATE OF id,point,replicate,attempt,original_job ON {JOBS}
 BEGIN SELECT RAISE(ABORT,'identity append only'); END;
CREATE TRIGGER require_authorization_{JOBS} BEFORE INSERT ON {JOBS} BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM {AUTH} a WHERE a.id=NEW.id
 AND json_extract(a.metadata,'$.point_id')=NEW.point
 AND json_extract(a.metadata,'$.replicate_id')=NEW.replicate
 AND json_extract(a.metadata,'$.raw_attempt')=NEW.attempt
 AND json_extract(a.metadata,'$.original_job_id')=NEW.original_job)
 THEN RAISE(ABORT,'exact host authorization required') END;
END;
'''


class OwnControlBoundary:
    """Explicit offline fixture type, NEVER accepted as a production owner."""
    def __init__(self,*,ledger,queue,root,contract,kernels,input_verifier):
        root=Path(root)
        need(root.is_absolute()and root.resolve()==root and root.name.startswith('OWN-')and
             type(ledger)is Ledger and type(queue)is FinalQueue and ledger.home==root/'ledger'and
             queue.home==root/'queue'and callable(input_verifier),'OWN_EXACT_ORIGINAL_QUEUE_BOUNDARY')
        validate_contract(contract,digest(contract))
        self.ledger,self.queue,self.root,self.contract=ledger,queue,root,contract
        self.kernels,self.input_verifier=kernels,input_verifier
        self.owner=process_identity(os.getpid());self.offline_OWN=True


class CarrierQueueDomain:
    def __init__(self,control):
        need(type(control)is FormalAllowanceControl,'CONTROL_CARRIER_EXACT_ORIGINAL_OWNER_PORT')
        control.fresh();self.control=control;self.q=control.core.queue;self.l=control.core.ledger
        validate_contract(control.core.contract,digest(control.core.contract))
        self.contract=control.core.contract;self.kernels=control.kernels
        self.owner=control.birth;self.offline_OWN=False;self.installed=False
    def install_production(self):
        need(False,'PROPOSAL_PRODUCTION_CONTROL_SCHEMA_INSTALL_NOT_AUTHORIZED')
    @classmethod
    def install_OWN(cls,boundary):
        need(type(boundary)is OwnControlBoundary,'OWN_CONTROL_CARRIER_NOT_PRODUCTION_OWNER')
        self=cls.__new__(cls);self.control=None;self.boundary=boundary
        self.q,self.l=boundary.queue,boundary.ledger;self.contract=boundary.contract
        self.kernels,self.owner=boundary.kernels,boundary.owner;self.offline_OWN=True;self.installed=False
        self.home=private_dir(boundary.root/'host-control-carrier',create=True)
        need(not any(self.home.iterdir()),'OWN_FRESH_HOST_CONTROL_CARRIER')
        with self.q.mutex:
            need(not any(r['state']in('CLAIMED','RUNNING')for r in final_attempts.all_rows(self.q)),
                 'OWN_COLD_CONTROL_BINDING_NO_LIVE_CHILD')
            self.q.db.executescript(DDL)
        self._bind_private_original_ports(boundary.input_verifier)
        value=dict(schema=SCHEMA,offline_OWN=True,production_install_authorized=False,
            owner=self.owner,home=str(self.home),queue_home=str(self.q.home),ledger_home=str(self.l.home),
            contract_sha256=digest(self.contract),policy=POLICY,original_kernel_paths=self.kernels.source_paths,
            original_kernel_sha256=self.kernels.source_sha256,control_source_sha256=source_pins(),
            carrier_table=JOBS,authorization_table=AUTH,DDL_sha256=digest(DDL),
            native_raw_domain='ONLY_ACTUAL_HOST_POLICY_AUTHORIZED_RAW_GE4',
            original_financial_schema_changed=False)
        self.descriptor=self.home/'QUEUE_CONTROL_DOMAIN_PUBLIC.json'
        publish(self.descriptor,wire(value),mode=0o400);self.pin=hash_file(self.descriptor)['sha256']
        self.installed=True;return self
    def fresh(self):
        need(process_identity(os.getpid())==self.owner and type(self.q)is FinalQueue and type(self.l)is Ledger,
             'CONTROL_CARRIER_SAME_ORIGINAL_OWNER_TYPES')
        if self.control is not None:self.control.fresh()
        else:need(self.offline_OWN and type(self.boundary)is OwnControlBoundary and
                  self.boundary.root.name.startswith('OWN-'),'CONTROL_CARRIER_NOT_FAKE_PRODUCTION')
    def _bind_private_original_ports(self,input_verifier):
        q=self.q;space=dict(vars(final_attempts))
        for name,value in list(space.items()):
            if inspect.isfunction(value)and value.__module__==final_attempts.__name__:
                f=FunctionType(value.__code__,space,value.__name__,value.__defaults__,value.__closure__)
                f.__kwdefaults__=value.__kwdefaults__;space[name]=f
        original_table=space['table'];original_job=space['replacement_job'];original_rows=final_attempts.all_rows
        def table(this,jid):
            need(this is q,'CONTROL_CARRIER_NO_CROSS_SCOPE_QUEUE')
            return JOBS if this.db.execute('SELECT 1 FROM '+JOBS+' WHERE id=?',(jid,)).fetchone()else original_table(this,jid)
        def job(this,jid):
            need(this is q,'CONTROL_CARRIER_NO_CROSS_SCOPE_QUEUE')
            if table(this,jid)!=JOBS:return original_job(this,jid)
            row=this.db.execute('SELECT r.*,p.trajectory,p.setting,p.target,p.input_root,p.input_policy FROM '+JOBS+' r JOIN points p ON r.point=p.point WHERE r.id=?',(jid,)).fetchone()
            need(row is not None,'CONTROL_CARRIER_REGISTERED_JOB_REQUIRED');return dict(row)
        def rows(this):
            need(this is q,'CONTROL_CARRIER_NO_CROSS_SCOPE_QUEUE')
            self._known_job_tables_locked()
            return original_rows(this)+[this._job(r[0])for r in this.db.execute('SELECT id FROM '+JOBS+' ORDER BY rowid')]
        space.update(table=table,replacement_job=job,all_rows=rows)
        private=SimpleNamespace(**space);self.attempts=private
        candidate=globals_clone(final_queue._claim_candidate,attempts=private)
        def verified_candidate(this):
            r=candidate(this)
            if r is not None and r.get('attempt',1)>=4:self._registration_locked(r)
            return r
        for name in('_job','attach','reap','complete','frontier'):
            setattr(q,name,MethodType(globals_clone(getattr(FinalQueue,name),attempts=private),q))
        original_claim=globals_clone(FinalQueue.claim,attempts=private,_claim_candidate=verified_candidate,
            verify_input=input_verifier)
        def claim(this):
            self.fresh();r=original_claim(this)
            if r is not None and r.get('attempt',1)>=4:self.authorize_claim(r)
            return r
        q.claim=MethodType(claim,q);q._formal_control_carrier_domain=self
    def _known_job_tables_locked(self):
        required={'id','point','replicate','state','claim','child','terminal','result'}
        for r in self.q.db.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            name=r[0];need(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',name)is not None,'CONTROL_TABLE_IDENTIFIER')
            cols={x[1]for x in self.q.db.execute('PRAGMA table_info("'+name+'")')}
            if required<=cols:need(name in('jobs','replacement_jobs',JOBS),'UNREGISTERED_JOB_CONTROL_DOMAIN_WAIT')
    def all_rows(self,q):
        self.fresh();need(q is self.q,'CONTROL_CARRIER_EXACT_READ_QUEUE')
        with q.mutex:return self.attempts.all_rows(q)
    def effective_rows(self,q):
        self.fresh();need(q is self.q,'CONTROL_CARRIER_EXACT_READ_QUEUE')
        with q.mutex:return self.attempts.effective_rows(q)
    def _capture_locked(self,point,k):
        q,l=self.q,self.l;sha(point)
        descriptor=q.db.execute('SELECT *FROM points WHERE point=?',(point,)).fetchone()
        need(descriptor is not None,'CONTROL_REGISTERED_ORIGINAL_POINT')
        descriptor=dict(descriptor);rows=[j for j in self.kernels.point_rows(q,point)if j['replicate']==k]
        need(rows and descriptor['trajectory']in {r['trajectory_id']for r in self.contract['trajectories']}and
             point==digest(dict(trajectory=descriptor['trajectory'],target=descriptor['target'])),
             'CONTROL_SAME_FORMAL_REGULAR_POINT')
        chain=[];proof_bindings=[]
        for j in rows:
            r=dict(point_id=point,replicate_id=k,attempt=j['attempt'],job_id=j['id'],state=j['state'])
            prior=q.db.execute('SELECT metadata,sha256 FROM '+AUTH+' WHERE id=?',(j['id'],)).fetchone()
            if j['attempt']>=4:
                need(prior is not None,'CONTROL_EVERY_CARRIER_ROW_HAS_AUTHORIZATION')
                a=strict(prior[0]);need(digest(a)==prior[1],'CONTROL_ORIGINAL_AUTHORIZATION_CHANGED')
                if a['last_extra']:r.update(last_extra=True,last_extra_grant_sha256=a['last_extra_grant_sha256'])
            p=q.db.execute('SELECT metadata FROM replicate_partials WHERE job_id=?',(j['id'],)).fetchone()
            if p is not None:
                p=strict(p[0]);allocation=l.db.execute('SELECT metadata FROM aux_attempt_allocations WHERE job_id=?',(j['id'],)).fetchone()
                need(allocation is not None,'CONTROL_ORIGINAL_SYSTEM_ALLOCATION_REQUIRED');allocation=strict(allocation[0])
                proof=self.kernels.failed_proof(q,j,p,allocation);r.update(state='PARTIAL',failure_proof=proof)
                # Paid unknown causes are NOT inferred from Refused/code/zero
                # assertions. Production tool exemptions must come from the
                # existing exact host control reader, outside these locks.
                proof_bindings.append(dict(job=j,partial=p,allocation=allocation))
            else:proof_bindings.append(dict(job=j))
            chain.append(r)
        return descriptor,rows,chain,proof_bindings
    def plan(self,point,k):
        self.fresh();need(type(k)is int and k in(1,2,3),'CONTROL_ORIGINAL_REPLICATE_ID')
        with self.l.mutex:
            with self.q.mutex:
                descriptor,rows,chain,binding=self._capture_locked(point,k)
        if self.control is not None:
            for r in chain:
                if r['state']=='PARTIAL':
                    x=self.control.home/(r['job_id']+'_EXEMPTION_PUBLIC.json')
                    if x.exists():
                        j=next(j for j in rows if j['id']==r['job_id'])
                        r['tool_exemption']=self.control._exemption(j,r['failure_proof'],x)
        decision=self.kernels.policy.decide_attempts(chain,original_limit=3)
        return dict(point_id=point,replicate_id=k,descriptor=descriptor,chain=chain,
            source_state_sha256=digest(binding),decision=decision,policy=POLICY,
            offline_OWN=self.offline_OWN,raw_ordinal_is_not_consumed_allowance=True)
    def register_next(self,plan):
        self.fresh();need(type(plan)is dict and plan.get('policy')==POLICY,'CONTROL_ORIGINAL_POLICY_PLAN_REQUIRED')
        point,k=plan['point_id'],plan['replicate_id'];d=plan['decision'];nxt=d['next_attempt']
        need(type(nxt)is int and nxt>=4 and d['action']in('NEW_INDEPENDENT_ORIGINAL_ALLOWANCE','NEW_INDEPENDENT_LAST_EXTRA')and
             d['terminal']is False,'CONTROL_NO_NEW_JOB_AFTER_PENDING_SUCCESS_OR_EXHAUSTION')
        jid=original_replacement_id(point,k,nxt)
        with self.q.mutex:
            need(self.q.db.execute('SELECT 1 FROM '+AUTH+' WHERE id=?',(jid,)).fetchone()is None,
                 'CONTROL_DUPLICATE_REGISTRATION_REFUSED')
        fresh=self.plan(point,k);need(fresh==plan,'CONTROL_STALE_OR_TAMPERED_POLICY_PLAN')
        need(plan['chain'][-1]['state']=='PARTIAL'and plan['chain'][-1]['attempt']+1==nxt,
             'CONTROL_NO_RAW_SKIP_OR_UNDISPOSED_PREDECESSOR')
        last=d['action']=='NEW_INDEPENDENT_LAST_EXTRA'
        grant=(d['original_last_extra_grant_sha256']or digest(dict(policy=POLICY,point_id=point,
            replicate_id=k,original_limit=3,original_decision_sha256=digest(d),owner=self.owner)))if last else None
        first=plan['chain'][0]['job_id']
        authorization=dict(schema=AUTH_SCHEMA,offline_OWN=self.offline_OWN,owner=self.owner,
            contract_sha256=digest(self.contract),domain_sha256=self.pin,policy=POLICY,
            original_policy_sha256=self.kernels.source_sha256['policy'],job_id=jid,point_id=point,
            replicate_id=k,raw_attempt=nxt,original_job_id=first,previous_job_id=plan['chain'][-1]['job_id'],
            source_state_sha256=plan['source_state_sha256'],decision=d,original_limit=3,
            last_extra=last,last_extra_grant_sha256=grant,original_failure_chain=plan['chain'],
            fees_changed=False,UNKNOWN_or_physical_slots_released=False,requests_replayed=0)
        pin=digest(authorization)
        # A retained PUBLIC prefix is not a committed queue authority on its
        # own. Only the exact original q transaction registers/claims the row.
        publish(self.home/(jid+'_REGISTRATION_PUBLIC.json'),wire(authorization),mode=0o400)
        with self.l.mutex:
            with self.q.mutex:
                _,_,_,current=self._capture_locked(point,k)
                need(digest(current)==plan['source_state_sha256'],'CONTROL_PREFIX_CHANGED_BEFORE_COMMIT')
                with self.q.tx():
                    self.q.db.execute('INSERT INTO '+AUTH+' VALUES(?,?,?)',(jid,wire(authorization).decode(),pin))
                    self.q.db.execute('INSERT INTO '+JOBS+" VALUES(?,?,?,'QUEUED',NULL,NULL,NULL,NULL,?,?)",(jid,point,k,nxt,first))
                    self.q.event('ONE_REPLICATE_REPLACEMENT_ENQUEUED',dict(job_id=jid,failed_job_id=authorization['previous_job_id'],
                        point_id=point,replicate_id=k,attempt=nxt,rng_policy_sha256=digest(final_attempts.RNG_POLICY),
                        new_requests_required=True,billing_domain='AUX_FINALIZATION',search_budget_delta=0,
                        policy=POLICY,control_authorization_sha256=pin))
        return jid
    def _registration_locked(self,row):
        need(row['attempt']>=4,'CONTROL_CARRIER_RAW_DOMAIN')
        a=self.q.db.execute('SELECT metadata,sha256 FROM '+AUTH+' WHERE id=?',(row['id'],)).fetchone()
        need(a is not None,'CONTROL_REAL_QUEUE_REGISTRATION_REQUIRED');v=strict(a[0])
        need(digest(v)==a[1]and v['schema']==AUTH_SCHEMA and v['owner']==self.owner and v['domain_sha256']==self.pin and
             v['job_id']==row['id']==original_replacement_id(row['point'],row['replicate'],row['attempt'])and
             v['point_id']==row['point']and v['replicate_id']==row['replicate']and v['raw_attempt']==row['attempt']and
             v['original_job_id']==row['original_job'],'CONTROL_SAME_ORIGINAL_ROW_AUTHORIZATION')
        return v,a[1]
    def authorize_claim(self,job):
        self.fresh()
        with self.q.mutex:
            actual=self.q._job(job['id']);need(actual==job and job['state']=='CLAIMED','CONTROL_ACTUAL_ORIGINAL_CLAIM')
            a,pin=self._registration_locked(job)
        value=dict(schema=CLAIM_SCHEMA,offline_OWN=self.offline_OWN,owner=self.owner,domain_sha256=self.pin,
            registration_sha256=pin,job_id=job['id'],point_id=job['point'],replicate_id=job['replicate'],
            raw_attempt=job['attempt'],claim=job['claim'],original_state='CLAIMED',trajectory=job['trajectory'],
            input_policy_sha256=job['input_policy'],policy=POLICY)
        publish(self.home/(job['id']+'_CLAIM_PUBLIC.json'),wire(value),mode=0o400);return value


def original_replacement_id(point,k,nxt):
    """Execute the exact original partial_and_replace hash-expression AST."""
    src=inspect.getsource(final_attempts.partial_and_replace);tree=ast.parse(src)
    assignment=next(n for n in ast.walk(tree)if isinstance(n,ast.Assign)and
        any(isinstance(t,ast.Name)and t.id=='new'for t in n.targets))
    expression=copy.deepcopy(assignment.value)
    return eval(compile(ast.fix_missing_locations(ast.Expression(expression)),'ORIGINAL_REPLACEMENT_ID_AST','eval'),
        {'digest':digest},{'job':{'point':point,'replicate':k},'nxt':nxt})


def source_pins():
    names=('queue_control.py','queue_native.py','queue_child.py')
    return {name:hash_file(Path(__file__).with_name(name))['sha256']for name in names}


class CarrierReader:
    def __init__(self,path,pin,*,allow_OWN=False):
        self.path=Path(path);self.home=self.path.parent;self.pin=sha(pin)
        v=read_public(self.path,root=self.home,expected=self.pin)
        need(v['schema']==SCHEMA and v['contract_sha256']==PUBLIC_CONTRACT_CANONICAL_SHA256 and
             v['policy']==POLICY and v['carrier_table']==JOBS and v['authorization_table']==AUTH and
             v['DDL_sha256']==digest(DDL)and v['home']==str(self.home),'CONTROL_EXACT_DOMAIN_DESCRIPTOR')
        need(allow_OWN is True and v['offline_OWN']is True and self.home.parent.name.startswith('OWN-')and
             v['production_install_authorized']is False,'PRODUCTION_CHILD_CANNOT_CONSUME_OWN_AUTHORITY')
        self.value=v;self.fresh()
    def fresh(self):
        need(read_public(self.path,root=self.home,expected=self.pin)==self.value and
             process_identity(self.value['owner']['pid'])==self.value['owner'],'CONTROL_READER_SAME_OWNER_KERNEL_BIRTH')
        need(self.value['control_source_sha256']==source_pins(),'CONTROL_READER_SOURCE_PINS')
    def allowed(self,point,k,a,**scope):
        need(type(a)is int and a>=1,'CONTROL_NATIVE_RAW_INTEGER')
        if a<=3:return True
        self.authorization(point,k,a,**scope);return True
    def authorization(self,point,k,a,*,trajectory=None,input_policy=None):
        self.fresh();jid=attempt_key(point,k,a)
        c=read_public(self.home/(jid+'_CLAIM_PUBLIC.json'),root=self.home)
        r=read_public(self.home/(jid+'_REGISTRATION_PUBLIC.json'),root=self.home,expected=c['registration_sha256'])
        need(c['schema']==CLAIM_SCHEMA and c['owner']==r['owner']==self.value['owner']and
             c['domain_sha256']==r['domain_sha256']==self.pin and c['job_id']==r['job_id']==jid and
             c['point_id']==r['point_id']==point and c['replicate_id']==r['replicate_id']==k and
             c['raw_attempt']==r['raw_attempt']==a and c['original_state']=='CLAIMED'and
             type(c['claim'])is str and c['claim']and r['fees_changed']is False and
             r['UNKNOWN_or_physical_slots_released']is False and r['requests_replayed']==0,
             'CONTROL_EXACT_ACTUAL_CLAIM_AND_POLICY_RECEIPT')
        if trajectory is not None:need(c['trajectory']==trajectory,'CONTROL_NATIVE_SAME_TRAJECTORY')
        if input_policy is not None:need(c['input_policy_sha256']==input_policy,'CONTROL_NATIVE_SAME_INPUT')
        return c
