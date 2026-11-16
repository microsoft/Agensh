"""Frozen search model/host-RNG policy, independent of roots and arm names.

Sending a provider seed is optional only with already-approved evidence. Even
an accepted seed parameter does not prove backend determinism. No paid probe is
performed and no worker-supplied seed, model or sampling override is accepted.
"""
import copy,re
from common import need,digest,integer,sha
from manifest import compile_manifest
SALT='count14-agensh-host-domain-v1'
RNG_POLICY={'schema':'count14-agensh-rng-policy-v1','salt':SALT,'algorithm':'SHA256 canonical JSON key, first 8 lowercase hex digits interpreted uint32','key':['salt','search_seed','role','domain','action_index','checkpoint','repeat'],'root_and_setting_in_key':False,'unknown_no_replay':True}
RNG_POLICY_SHA=digest(RNG_POLICY)

def action_seed(search_seed,role,action_index,*,domain='SEARCH',checkpoint=0,repeat=None):
    integer(search_seed,'SEARCH_SEED');need(search_seed<2**32,'SEARCH_SEED');integer(action_index,'ACTION_INDEX')
    need(type(role)is str and (re.fullmatch(r'worker-(?:0[0-9]|1[0-5])',role)or role=='final'),'RNG_ROLE')
    if domain=='SEARCH':need(role!='final' and type(checkpoint)is int and checkpoint==0 and repeat is None,'SEARCH_RNG_NO_FINAL_FIELDS')
    else:need(role=='final' and domain=='AUX_FINALIZATION' and type(checkpoint)is int and checkpoint in (10000000,20000000) and type(repeat)is int and repeat in (1,2,3),'FINAL_RNG_IDENTITY')
    key=[SALT,search_seed,role,domain,action_index,checkpoint,repeat]
    return {'seed':int(digest(key)[:8],16),'key_sha256':digest(key),'salt':SALT}

class SearchProfile:
    FIELDS={'schema','model','temperature','top_p','reasoning_effort','provider_seed_status','provider_seed_evidence_sha256'}
    def __init__(self,manifest,policy,policy_sha):
        self.compiled=compile_manifest(manifest);need(manifest['protocol']['rng_policy']==RNG_POLICY_SHA,'RNG_POLICY_PIN');need(set(policy)==self.FIELDS and policy['schema']=='count14-agensh-model-policy-v1','MODEL_POLICY_FIELDS')
        need(digest(policy)==sha(policy_sha) and manifest['protocol'].get('model_configuration')==policy_sha,'MODEL_POLICY_PIN')
        need(type(policy['model'])is str and 0<len(policy['model'])<=128,'MODEL_POLICY_MODEL')
        need(type(policy['temperature'])in (int,float) and type(policy['top_p'])in (int,float) and policy['temperature']==policy['top_p']==1 and policy['reasoning_effort']=='max','BASELINE_MODEL_SAMPLING')
        need(policy['provider_seed_status']in ('UNSUPPORTED','SEND_ACCEPTED_NOT_DETERMINISM_PROVEN'),'PROVIDER_SEED_STATUS')
        if policy['provider_seed_status']!='UNSUPPORTED':sha(policy['provider_seed_evidence_sha256'])
        else:need(policy['provider_seed_evidence_sha256']is None,'NO_INVENTED_SEED_EVIDENCE')
        self.manifest=copy.deepcopy(manifest);self.policy=copy.deepcopy(policy);self.sha=policy_sha;self.rows={r['trajectory_id']:r for r in self.compiled['trajectories']}
    def normalize(self,request):
        r=copy.deepcopy(request);p=self.policy;need(r.get('model')==p['model'],'MODEL_NOT_CONFIGURED')
        for key in ('temperature','top_p'):
            need(key not in r or type(r[key])in (int,float) and r[key]==p[key],'SAMPLING_OVERRIDE_FORBIDDEN');r[key]=p[key]
        reasoning=r.get('reasoning',{});need(type(reasoning)is dict and reasoning.get('effort','max')=='max','REASONING_OVERRIDE_FORBIDDEN');r['reasoning']={**reasoning,'effort':'max'}
        return r
    def row(self,trajectory):
        if trajectory not in self.rows:
            from r16_attempt_identity import resolve_row
            self.rows[trajectory]=resolve_row(self.manifest,trajectory)
        return self.rows[trajectory]
    def reserve_rng(self,ledger,t,role,rid):
        need(role in self.row(t)['roles'],'PROFILE_TRAJECTORY_ROLE')
        # Called under durable ledger mutex, after one reservation and before
        # SENT. Cancelled-unsent ordinals are never reused; UNKNOWN never replayed.
        count=ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=? AND role=?',(t,role)).fetchone()[0];need(count>0,'RNG_WITHOUT_RESERVATION')
        r=action_seed(self.rows[t]['seed'],role,count-1)
        metadata={**r,'request_id':rid,'role':role,'action_index':count-1,'model_configuration_sha256':self.sha,'provider_seed_status':self.policy['provider_seed_status']}
        with ledger.tx():ledger.event(t,'SEARCH_RNG_INTENT',metadata)
        return metadata
    def upstream(self,chat,rng):
        value=copy.deepcopy(chat)
        if self.policy['provider_seed_status']=='SEND_ACCEPTED_NOT_DETERMINISM_PROVEN':value['seed']=rng['seed']
        return value
