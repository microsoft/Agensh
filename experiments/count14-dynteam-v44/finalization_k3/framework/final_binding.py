"""Explicit AUX_FINALIZATION request binding for the unmodified native engine.

The native ledger's 'single' role is an internal serial AUX accounting ABI only;
this never registers Agensh as a single/moa search trajectory. Final K3 uses the
same frozen model profile and distinct checkpoint/repeat host-RNG domains.
No model transport, evaluator or production authority is supplied by this file.
"""
import copy
from pathlib import Path
from common import need,integer,digest,sha,stamp
from scientific_profile import SearchProfile,action_seed,RNG_POLICY_SHA
from v21_inputs import verify_input

class FinalBinding:
    def __init__(self,manifest,model_policy,model_policy_sha256,*,trajectory,input_root,input_policy_sha256,replicate_index,authorize,replicate_attempt=1,point_id=None):
        need(type(replicate_attempt)is int and replicate_attempt in (1,2,3),'FINAL_REPLICATE_ATTEMPT')
        self.replicate_attempt=replicate_attempt;self.point_id=point_id
        self.profile=SearchProfile(manifest,model_policy,model_policy_sha256)
        self.row=copy.deepcopy(self.profile.row(trajectory));self.trajectory=trajectory
        need(type(replicate_index)is int and replicate_index in (1,2,3),'FINAL_REPEAT_IDENTITY');self.repeat=replicate_index
        need(callable(authorize),'FINAL_NATIVE_OWNER_PORT_REQUIRED');self.owner_port=authorize
        self.input_root=input_root;self.input_sha=sha(input_policy_sha256);self.manifest_sha=self.profile.compiled['manifest_sha256']
        self.policy=verify_input(input_root,expected_policy_sha=self.input_sha,trajectory=trajectory,setting=self.row['setting'])
        need(self.policy['pins']['manifest']==self.manifest_sha,'FINAL_MANIFEST_INPUT_MISMATCH')
        # Check frozen-file identity around the initial full SHA verification.
        # Per-request checks use inode/mode/size/mtime/ctime/link count, avoiding
        # rehashing many GiB per native model attempt. Worker has no input-root
        # write capability; native owner must retain that confinement.
        self.files=[Path(input_root)/'input-policy.json',Path(input_root)/'snapshot/saved.json']
        for role in self.policy['roles']:
            self.files.extend(Path(input_root)/'snapshot/roles'/role/name for name in ('workspace.tar.gz','private-context.json','snapshot-receipt.json'))
        before=self._stamps();verify_input(input_root,expected_policy_sha=self.input_sha,trajectory=trajectory,setting=self.row['setting']);need(before==self._stamps(),'FINAL_INPUT_CHANGED_DURING_BINDING');self.frozen_stamps=before
        from r16_natural_contract import natural
        self.natural_stop=natural(self.policy)
        self.target=self.policy['target_tokens'];self.identity={'schema':'count14-agensh-native-final-binding-v1','purpose':'AUX_FINALIZATION','trajectory':trajectory,'setting':self.row['setting'],'target_tokens':self.target,'replicate_index':self.repeat,'input_policy_sha256':self.input_sha,'manifest_sha256':self.manifest_sha,'model_policy_sha256':model_policy_sha256,'rng_policy_sha256':RNG_POLICY_SHA,'provider_seed_status':self.profile.policy['provider_seed_status']}
        if self.natural_stop is not None:
            from r16_natural_contract import NATURAL_RNG_POLICY
            self.identity.update(point_kind='NATURAL_STOP',natural_stop=self.natural_stop,natural_stop_rng_policy_sha256=digest(NATURAL_RNG_POLICY))
        if replicate_attempt>1:
            from final_attempts import RNG_POLICY
            key={'trajectory':trajectory,'target':self.target}
            if self.natural_stop is not None:key.update(point_kind='NATURAL_STOP',policy_sha256=self.natural_stop['policy_sha256'])
            need(point_id==digest(key),'FINAL_REPLACEMENT_POINT_ID')
            self.identity.update(point_id=point_id,replicate_attempt=replicate_attempt,replacement_rng_policy_sha256=digest(RNG_POLICY))
    def _stamps(self):
        need(Path(self.input_root).resolve()==Path(self.input_root),'FINAL_INPUT_ROOT_CHANGED')
        values=[]
        for path in self.files:
            need(path.resolve()==path,'FINAL_INPUT_PATH_CHANGED');values.append(stamp(path.lstat()))
        return tuple(values)
    def authorize(self):
        # Real implementation must check current child/owner/lock/resource scope.
        # No cached historical approval or a model/worker assertion is sufficient.
        receipt=self.owner_port(copy.deepcopy(self.identity))
        need(type(receipt)is dict and receipt.get('binding_sha256')==digest(self.identity) and receipt.get('current_native_owner_authorized')is True,'FINAL_NATIVE_OWNER_NOT_AUTHORIZED')
        need(self._stamps()==self.frozen_stamps,'FINAL_FROZEN_INPUT_METADATA_CHANGED')
    def bind_request(self,body,*,role,action_index,phase,checkpoint_tokens,finalization_repeat_id,finalization_attempt_ordinal):
        self.authorize();integer(action_index,'FINAL_ACTION_INDEX');need(action_index<96,'FINAL_ACTION_GUARD96')
        need(role=='final'and phase=='finalization'and type(checkpoint_tokens)is int and checkpoint_tokens==self.target and type(finalization_repeat_id)is int and finalization_repeat_id==self.repeat and type(finalization_attempt_ordinal)is int and finalization_attempt_ordinal==1,'FINAL_REQUEST_EXACT_SCOPE')
        need(type(body)is dict and not any(k in body for k in ('seed','_pilot','_calibration','_agensh_final')),'FINAL_FRESH_NATIVE_BODY')
        p=self.profile.policy
        need(body.get('model')==p['model']and type(body.get('temperature'))in (int,float)and body['temperature']==1 and type(body.get('top_p'))in (int,float)and body['top_p']==1 and body.get('reasoning_effort')=='max'and body.get('stream')is True,'FINAL_NATIVE_SAMPLING_CHANGED')
        if self.replicate_attempt>1:
            from final_attempts import request_rng
            rng=request_rng(self.row['seed'],self.point_id,self.repeat,self.replicate_attempt,action_index)
        elif self.natural_stop is not None:
            from r16_natural_contract import final_rng
            rng=final_rng(self.row['seed'],action_index,self.repeat,self.natural_stop)
        else:rng=action_seed(self.row['seed'],'final',action_index,domain='AUX_FINALIZATION',checkpoint=self.target,repeat=self.repeat)
        value=copy.deepcopy(body);value['seed']=rng['seed'];value['_agensh_final']={**copy.deepcopy(self.identity),'action_index':action_index,'host_rng_key_sha256':rng['key_sha256']};return value
    def verify_request(self,body,*,setting,role,finalization):
        self.authorize();need(setting==self.row['setting']and role=='single'and finalization is True,'FINAL_NO_SEARCH_REQUEST')
        m=body.get('_agensh_final');need(type(m)is dict,'FINAL_NATIVE_DOMAIN_REQUIRED')
        clean={k:copy.deepcopy(v)for k,v in body.items()if k not in ('seed','_agensh_final')}
        expected=self.bind_request(clean,role='final',action_index=m.get('action_index'),phase='finalization',checkpoint_tokens=self.target,finalization_repeat_id=self.repeat,finalization_attempt_ordinal=1)
        need(body==expected,'FINAL_REQUEST_BINDING_CHANGED');return body['seed']
    def seed_provider_options(self,body,options):
        self.verify_request(body,setting=self.row['setting'],role='single',finalization=True)
        need(type(options)is dict and 'seed'not in options and 'seed'not in options.get('extra_body',{}),'FINAL_PROVIDER_SEED_OVERRIDE')
        # Host RNG intent is always recorded; provider seed is sent only under
        # its frozen supported policy. Accepted is not deterministic proof.
        out=copy.deepcopy(options)
        if self.profile.policy['provider_seed_status']=='SEND_ACCEPTED_NOT_DETERMINISM_PROVEN':out['seed']=body['seed']
        return out
