"""Same-original-owner PUBLIC allowance control, not a financial/schema patch.

Only this trusted host object writes receipts. A child/worker dict, path, code
string, zero-cost assertion or verified=True flag cannot mint an exemption.
No queue/ledger writes, enqueue, original disposition or custody release here.
"""
from pathlib import Path
import copy,os,stat,time
from common import need,digest,sha,strict,hash_file,publish,wire,private_dir
from final_queue import FinalQueue,process_identity
from original_relay_core import OriginalRelayCore
from budget import Ledger
from formal_scope import validate_contract,PUBLIC_CONTRACT_CANONICAL_SHA256
from allowance_original import load_kernels,PINS

CONTROL='count14-formal100m-allowance-host-control-v1'
ATTEMPT='count14-formal100m-allowance-attempt-authorization-public-v1'
EXEMPT='count14-formal100m-allowance-tool-exemption-public-v1'
BASIS='count14-formal100m-registered-repair-basis-public-v1'
PROJECTION='count14-formal100m-fixed-tool-failure-projection-public-v1'
POLICY='USER_20261030_ORIGINAL_ALLOWANCE_PLUS_ONE_THEN_ACTUAL_N'
ATTEMPT_FIELDS={'schema','owner','contract_sha256','control_sha256','job_id','point_id','replicate_id',
 'raw_attempt','claim','trajectory','input_policy_sha256','original_state','policy','source_state_sha256',
 'decision','native_queue_raw4_installed','fees_changed','requests_replayed'}


def read_public(path,*,root,expected=None):
    """Fixed PUBLIC metadata only; no scientific body or ambient path lookup."""
    p=Path(path);root=Path(root)
    need(p.is_absolute()and p.resolve()==p and root.resolve()==root and p.is_relative_to(root)
         and p.name.endswith('_PUBLIC.json'),'FORMAL_ALLOWANCE_FIXED_PUBLIC_PATH')
    for directory in (root,*p.relative_to(root).parents):
        directory=directory if directory==root else root/directory
        s=directory.lstat();need(stat.S_ISDIR(s.st_mode)and s.st_uid==os.geteuid()and not s.st_mode&0o022,
                                'FORMAL_ALLOWANCE_HOST_ONLY_DIRECTORY')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        s=os.fstat(fd);need(stat.S_ISREG(s.st_mode)and s.st_uid==os.geteuid()and
            s.st_nlink==1 and stat.S_IMODE(s.st_mode)==0o400 and s.st_size<=1024*1024,
            'FORMAL_ALLOWANCE_HOST_PUBLIC_FILE_CUSTODY')
        with os.fdopen(os.dup(fd),'rb')as f:raw=f.read(1024*1024+1)
        need(len(raw)==s.st_size,'FORMAL_ALLOWANCE_PUBLIC_SIZE')
        if expected is not None:need(__import__('hashlib').sha256(raw).hexdigest()==expected,'FORMAL_ALLOWANCE_PUBLIC_PIN')
        return strict(raw)
    finally:os.close(fd)


def attempt_key(point,k,a):
    sha(point);need(type(k)is int and k in(1,2,3)and type(a)is int and a>=1,'FORMAL_ALLOWANCE_RAW_IDENTITY')
    return digest(dict(point=point,replicate=k,**({'attempt':a}if a>1 else{})))


class FormalAllowanceReader:
    def __init__(self,path,expected_sha256):
        self.path=Path(path);self.home=self.path.parent;self.pin=sha(expected_sha256)
        value=read_public(self.path,root=self.home,expected=self.pin)
        need(type(value)is dict and set(value)=={'schema','contract_sha256','owner','home','original_kernels',
            'policy','source_sha256','queue_raw4_install_executed','raw_above4_native_domain_qualified'}and
            value['schema']==CONTROL and value['contract_sha256']==PUBLIC_CONTRACT_CANONICAL_SHA256 and
            value['home']==str(self.home)and value['policy']==POLICY and
            value['queue_raw4_install_executed']is False and value['raw_above4_native_domain_qualified']is False,
            'FORMAL_ALLOWANCE_EXACT_CONTROL_DESCRIPTOR')
        self.value=value;self.kernels=load_kernels(value['original_kernels']);self.fresh()
    def fresh(self):
        need(read_public(self.path,root=self.home,expected=self.pin)==self.value and
             process_identity(self.value['owner']['pid'])==self.value['owner'],
             'FORMAL_ALLOWANCE_SAME_LIVE_ORIGINAL_OWNER')
        for name,pin in self.value['source_sha256'].items():
            need(Path(name).name==name and hash_file(Path(__file__).with_name(name))['sha256']==pin,
                 'FORMAL_ALLOWANCE_CONTROL_CODE_PIN')
    def authorization(self,point,k,a,*,trajectory=None,input_policy=None):
        self.fresh();jid=attempt_key(point,k,a)
        r=read_public(self.home/(jid+'_ATTEMPT_PUBLIC.json'),root=self.home)
        need(type(r)is dict and set(r)==ATTEMPT_FIELDS and r.get('schema')==ATTEMPT and r.get('owner')==self.value['owner']and
             r.get('contract_sha256')==self.value['contract_sha256']and r.get('control_sha256')==self.pin and
             r.get('job_id')==jid and r.get('point_id')==point and r.get('replicate_id')==k and
             r.get('raw_attempt')==a and r.get('policy')==POLICY and type(r.get('claim'))is str and r['claim']and
             r.get('original_state')=='CLAIMED'and r.get('native_queue_raw4_installed')is False and
             r.get('fees_changed')is False and r.get('requests_replayed')==0,
             'FORMAL_ALLOWANCE_EXACT_SAME_CLAIM_AUTHORIZATION')
        # Current writer only admits original1..3. raw4 needs the separately
        # reviewed original cold queue-domain installation; never infer it.
        need(a<=3,'FORMAL_ALLOWANCE_RAW4_QUEUE_DOMAIN_NOT_INSTALLED')
        if trajectory is not None:need(r['trajectory']==trajectory,'FORMAL_ALLOWANCE_SAME_TRAJECTORY')
        if input_policy is not None:need(r['input_policy_sha256']==input_policy,'FORMAL_ALLOWANCE_SAME_INPUT')
        sha(r['source_state_sha256']);return r
    def allowed(self,point,k,a,**scope):
        need(type(a)is int and a>=1,'FORMAL_ALLOWANCE_NATIVE_ATTEMPT_INTEGER')
        if a<=3:return True # unchanged ordinary first-from0 native domain
        self.authorization(point,k,a,**scope);return True


class FormalAllowanceControl:
    def __init__(self,owner,*,original_kernel_paths,approved_repair_sources=()):
        from native_cold_owner import NativeColdOwner
        need(type(owner)is NativeColdOwner and type(owner.core)is OriginalRelayCore and not owner.errors,
             'FORMAL_ALLOWANCE_EXACT_EXISTING_ORIGINAL_OWNER')
        core=owner.core;validate_contract(core.contract,digest(core.contract))
        need(not core.qualification_only and not core.closed and type(core.queue)is FinalQueue and
             type(core.ledger)is Ledger and set(core.gate.startup_held)==set(core.rows)and
             not hasattr(core,'formal_allowance_control'),'FORMAL_ALLOWANCE_ONE_COLD_SAME_CORE')
        self.owner,self.core=owner,core;self.birth=process_identity(os.getpid())
        self.kernels=load_kernels(original_kernel_paths)
        self.approved={str(Path(p)):sha(pin)for p,pin in approved_repair_sources}
        self.home=private_dir(core.home/'final-allowance-control-v1',create=True)
        need(not any(self.home.iterdir()),'FORMAL_ALLOWANCE_FRESH_CONTROL_ROOT')
        value=dict(schema=CONTROL,contract_sha256=digest(core.contract),owner=self.birth,home=str(self.home),
            original_kernels=self.kernels.source_paths,policy=POLICY,source_sha256=source_pins(),
            queue_raw4_install_executed=False,raw_above4_native_domain_qualified=False)
        self.path=self.home/'CONTROL_PUBLIC.json';publish(self.path,wire(value),mode=0o400)
        self.reader=FormalAllowanceReader(self.path,hash_file(self.path)['sha256'])
        core.formal_allowance_control=self
    def fresh(self):
        from native_cold_owner import NativeColdOwner
        need(self.owner.core is self.core and type(self.owner)is NativeColdOwner and
             type(self.core)is OriginalRelayCore and not self.core.closed and
             process_identity(os.getpid())==self.birth,'FORMAL_ALLOWANCE_SAME_HOST_WRITER')
        self.reader.fresh()
    def _snapshot(self,point,k,*,exclude=None):
        """Original persisted proof reader; blocking same ledger->queue order."""
        self.fresh();l,q=self.core.ledger,self.core.queue
        with l.mutex:
            with q.mutex:
                rows=[r for r in self.kernels.point_rows(q,point)if r['replicate']==k]
                need(rows and all(r['trajectory']in self.core.rows and r['setting']==self.core.rows[r['trajectory']]['arm']
                     and r['target']in self.core.rows[r['trajectory']]['checkpoints_tokens']for r in rows),
                     'FORMAL_ALLOWANCE_ORIGINAL_REGISTERED_POINT_CHAIN')
                chain=[];bindings=[];possible_exemptions=[]
                for j in rows:
                    if j['id']==exclude:continue
                    r=dict(point_id=point,replicate_id=k,attempt=j['attempt'],job_id=j['id'],state=j['state'])
                    p=q.db.execute('SELECT metadata FROM replicate_partials WHERE job_id=?',(j['id'],)).fetchone()
                    if p is not None:
                        p=strict(p[0]);a=l.db.execute('SELECT metadata FROM aux_attempt_allocations WHERE job_id=?',(j['id'],)).fetchone()
                        need(a is not None,'FORMAL_ALLOWANCE_ORIGINAL_ALLOCATION_REQUIRED');a=strict(a[0])
                        proof=self.kernels.failed_proof(q,j,p,a);r.update(state='PARTIAL',failure_proof=proof)
                        possible_exemptions.append((j,proof,r))
                        bindings.append(dict(job=j,partial=p,allocation=a))
                    else:bindings.append(dict(job=j))
                    chain.append(r)
                captured=(rows,chain,bindings,possible_exemptions)
        # All PUBLIC file I/O stays outside scientific locks. Original jobs,
        # allocations and PARTIAL records are append-only evidence snapshots.
        rows,chain,bindings,possible_exemptions=captured
        for j,proof,r in possible_exemptions:
            path=self.home/(j['id']+'_EXEMPTION_PUBLIC.json')
            if path.exists():
                r['tool_exemption']=self._exemption(j,proof,path)
                bindings.append(dict(exemption_sha256=hash_file(path)['sha256']))
        return rows,chain,digest(bindings)
    def plan(self,point,k):
        rows,chain,state=self._snapshot(point,k)
        decision=self.kernels.policy.decide_attempts(chain,original_limit=3)
        nxt=decision['next_attempt']
        return dict(schema='count14-formal100m-allowance-plan-public-v1',point_id=point,replicate_id=k,
            policy=POLICY,decision=decision,source_state_sha256=state,
            raw_ordinal_is_not_consumed_allowance=True,queue_jobs_created=0,fees_changed=False,
            native_next_domain='ORIGINAL_RAW1_TO3'if nxt is None or nxt<=3 else
                'WAIT_ORIGINAL_RAW4_COLD_QUEUE_DOMAIN'if nxt==4 else'WAIT_REVIEWED_ABOVE4_CONTROL_DOMAIN',
            goal_or_smoke_blocked=False)
    def all_rows(self,queue):
        from allowance_queue_plan import readonly_queue_rows
        return readonly_queue_rows(self,queue,effective=False)
    def effective_rows(self,queue):
        from allowance_queue_plan import readonly_queue_rows
        return readonly_queue_rows(self,queue,effective=True)
    def authorize_claim(self,job):
        """Normal original dispatcher configuration hook, before asset copying."""
        self.fresh();q=self.core.queue
        with q.mutex:actual=q._job(job['id'])
        need(actual==job and job['state']=='CLAIMED'and type(job['claim'])is str and job['claim'],
             'FORMAL_ALLOWANCE_REAL_ORIGINAL_CLAIM_REQUIRED')
        a=job.get('attempt',1);need(a<=3,'FORMAL_ALLOWANCE_RAW4_QUEUE_INSTALL_NOT_EXECUTED')
        rows,chain,state=self._snapshot(job['point'],job['replicate'],exclude=job['id'])
        need(rows[-1]['id']==job['id'],'FORMAL_ALLOWANCE_NO_LATER_ATTEMPT')
        decision=None
        if a>1:
            decision=self.kernels.policy.decide_attempts(chain,original_limit=3)
            need(decision['next_attempt']==a and decision['terminal']is False,
                 'FORMAL_ALLOWANCE_SAME_APPROVED_NEXT_INDEPENDENT_ATTEMPT')
        else:need(not chain,'FORMAL_ALLOWANCE_ORIGINAL_FIRST_ATTEMPT')
        with q.mutex:need(q._job(job['id'])==actual,'FORMAL_ALLOWANCE_CLAIM_CHANGED_DURING_CONTROL_CHECKS')
        value=dict(schema=ATTEMPT,owner=self.birth,contract_sha256=digest(self.core.contract),
            control_sha256=self.reader.pin,job_id=job['id'],point_id=job['point'],replicate_id=job['replicate'],
            raw_attempt=a,claim=job['claim'],trajectory=job['trajectory'],input_policy_sha256=job['input_policy'],
            original_state=job['state'],policy=POLICY,source_state_sha256=state,decision=decision,
            native_queue_raw4_installed=False,fees_changed=False,requests_replayed=0)
        publish(self.home/(job['id']+'_ATTEMPT_PUBLIC.json'),wire(value),mode=0o400);return value
    def register_repair_basis(self,path,expected_sha256):
        """Only a pre-registered trusted-host approval source, never worker input."""
        self.fresh();path=Path(path)
        need(self.approved.get(str(path))==expected_sha256,'FORMAL_ALLOWANCE_REPAIR_SOURCE_NOT_REGISTERED')
        r=read_public(path,root=path.parent,expected=expected_sha256)
        need(type(r)is dict and set(r)=={'schema','contract_sha256','repair_package_sha256',
             'authorization_source_sha256','public_codes','old_producer_source_sha256'}and
             r['schema']=='count14-formal100m-approved-repair-basis-public-v1'and
             r['contract_sha256']==digest(self.core.contract)and type(r['public_codes'])is list and
             r['public_codes']and set(r['public_codes'])<=self.kernels.policy.TOOL_CODES,
             'FORMAL_ALLOWANCE_EXACT_APPROVED_REPAIR_BASIS')
        for key in('repair_package_sha256','authorization_source_sha256','old_producer_source_sha256'):sha(r[key])
        value=dict(schema=BASIS,owner=self.birth,control_sha256=self.reader.pin,approval=r,
            approval_sha256=expected_sha256,registered_at_ns=time.time_ns())
        out=self.home/(expected_sha256+'_REPAIR_BASIS_PUBLIC.json');publish(out,wire(value),mode=0o400)
        return out,hash_file(out)['sha256']
    def _exemption(self,job,proof,path):
        r=read_public(path,root=self.home)
        return self._validate_exemption_value(job,proof,r)
    def _validate_exemption_value(self,job,proof,r):
        fields={'schema','owner','control_sha256','job_id','raw_attempt','scope','original_claim','custody_proof_sha256',
            'repair_basis_path','repair_basis_sha256','approval_path','projection_path','projection_sha256',
            'host_observed_terminal_monotonic_ns'}
        need(type(r)is dict and set(r)==fields and r.get('schema')==EXEMPT and r.get('owner')==self.birth and r.get('control_sha256')==self.reader.pin and
             r.get('job_id')==job['id']and r.get('raw_attempt')==job.get('attempt',1)and
             all(r.get(k)==proof[k]for k in('scope','original_claim','custody_proof_sha256')),
             'FORMAL_ALLOWANCE_EXEMPTION_NOT_SELF_AUTHORIZED')
        basis=read_public(r['repair_basis_path'],root=self.home,expected=r['repair_basis_sha256'])
        need(type(basis)is dict and set(basis)=={'schema','owner','control_sha256','approval','approval_sha256','registered_at_ns'}and
             basis['schema']==BASIS and basis['owner']==self.birth and basis['control_sha256']==self.reader.pin and
             self.approved.get(r['approval_path'])==basis['approval_sha256'],
             'FORMAL_ALLOWANCE_EXEMPTION_REGISTERED_REPAIR_PROOF')
        approved=read_public(r['approval_path'],root=Path(r['approval_path']).parent,expected=basis['approval_sha256'])
        need(approved==basis['approval'],'FORMAL_ALLOWANCE_REGISTERED_APPROVAL_BYTES_CHANGED')
        projection=read_public(r['projection_path'],root=self.core.home,expected=r['projection_sha256'])
        need(type(projection)is dict and set(projection)=={'schema','owner','job_id','original_claim','scope',
             'terminal_sha256','child','public_code','producer_source_sha256','observed_monotonic_ns'}and
             projection['schema']==PROJECTION and projection['owner']==self.birth and projection['job_id']==job['id']and
             projection['original_claim']==job['claim']and projection['scope']==proof['scope']and
             projection['terminal_sha256']==proof['terminal_sha256']and projection['child']==strict(job['child'])and
             projection['public_code']in basis['approval']['public_codes']and
             projection['producer_source_sha256']==basis['approval']['old_producer_source_sha256']and
             type(projection['observed_monotonic_ns'])is int and
             int(projection['child']['start'])*1_000_000_000//os.sysconf('SC_CLK_TCK')<=projection['observed_monotonic_ns']<=r['host_observed_terminal_monotonic_ns'],
             'FORMAL_ALLOWANCE_EXACT_FIXED_PUBLIC_LIFETIME_PROJECTION')
        return dict(job_id=job['id'],scope=proof['scope'],original_claim=job['claim'],
            custody_proof_sha256=proof['custody_proof_sha256'],terminal_sha256=proof['terminal_sha256'],
            public_code=projection['public_code'],same_scope=True,within_child_lifetime=True,
            verified_fixed_public_projection=True,original_public_projection_sha256=r['projection_sha256'])
    def register_tool_exemption(self,job_id,*,repair_basis_path,repair_basis_sha256,approval_path,
                                projection_path,projection_sha256):
        """Requires an actual fixed producer projection plus original persisted proof.

        Current original sanitized child emits no public_code/terminal-bound
        projection, so absent that explicitly connected producer this refuses.
        It never treats a Refused type/frame/name as cause or rewrites costs.
        """
        self.fresh();q=self.core.queue
        with q.mutex:j=q._job(job_id)
        rows,chain,_=self._snapshot(j['point'],j['replicate']);p=next(r['failure_proof']for r in chain if r['job_id']==job_id)
        value=dict(schema=EXEMPT,owner=self.birth,control_sha256=self.reader.pin,job_id=job_id,
            raw_attempt=j.get('attempt',1),scope=p['scope'],original_claim=j['claim'],custody_proof_sha256=p['custody_proof_sha256'],
            repair_basis_path=str(repair_basis_path),repair_basis_sha256=sha(repair_basis_sha256),approval_path=str(approval_path),
            projection_path=str(projection_path),projection_sha256=sha(projection_sha256),
            host_observed_terminal_monotonic_ns=time.monotonic_ns())
        # Validate before exclusive publication. Reuse fixed reader logic with
        # an in-memory value; no temporary self-issued exemption file is written.
        self._validate_exemption_value(j,p,value)
        out=self.home/(job_id+'_EXEMPTION_PUBLIC.json');publish(out,wire(value),mode=0o400);return out


def source_pins():
    names=('allowance_original.py','allowance_control.py','allowance_native.py','allowance_final_child.py','allowance_queue_plan.py')
    return {name:hash_file(Path(__file__).with_name(name))['sha256']for name in names}
