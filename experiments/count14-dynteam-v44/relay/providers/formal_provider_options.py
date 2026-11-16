"""Msg220 base-only AUX bridge for a NEW isolated formal child.

This is not a replacement FINAL runtime, request validator or model client.
It delegates to the original seed/options validator first and preserves its
result except for the registered provider URL. Never install in an owner.
"""
import os as _count14_os  # endpoints/keys come from environment; see CONFIGURATION.md
from pathlib import Path
import hashlib,json,os,stat

CONTRACT_FILE_SHA='9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
CONTRACT_SHA='9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
BINDING_SHA='3547d4013adfbdd88bcec1f748a2f48c056f33045cfb0d70f66c50386d2b72cb'
OLD=_count14_os.environ.get('COUNT14_GLM_LEGACY_BASE_URL', 'https://glm-legacy-gateway.example.invalid/v1')
NEW=_count14_os.environ.get('COUNT14_GLM_BASE_URL', 'https://glm-gateway.example.invalid/v1')
_INSTALLED=None

def need(ok,code):
    if not ok:raise ValueError('MSG220_FORMAL_AUX_'+code)

def frozen(path,pin):
    p=Path(path);s=p.lstat()
    need(p.is_absolute() and p.resolve()==p and not p.is_symlink() and
         stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid in (0,os.geteuid()) and
         not stat.S_IMODE(s.st_mode)&0o222 and hashlib.sha256(p.read_bytes()).hexdigest()==pin,
         'EXACT_FROZEN_REGULAR_SOURCE')
    return p.read_bytes()


def _msg221_alias():
    import importlib.util
    p=Path(__file__).resolve().with_name('provider_model_alias.py')
    s=p.lstat()
    import stat
    if not (p.is_absolute() and p.resolve()==p and not p.is_symlink() and
            stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid in (0,os.geteuid()) and
            stat.S_IMODE(s.st_mode)==0o444 and
            hashlib.sha256(p.read_bytes()).hexdigest()=='5924a5b99af0ebc8f6cfedaa22ea40932300259049f97f513092ded21a54a981'):
        raise ValueError('MSG221_EXACT_FROZEN_PRIVATE_ALIAS_SOURCE')
    spec=importlib.util.spec_from_file_location('count14_msg221_private_provider_alias',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def install(contract_path):
    """Only a standalone child, after its original frozen import bootstrap."""
    global _INSTALLED
    need(_INSTALLED is None,'NEW_CHILD_ONCE_NO_CLASS_REWRAP')
    from final_binding import FinalBinding
    original=FinalBinding.seed_provider_options
    frozen(original.__code__.co_filename,BINDING_SHA)
    c=json.loads(frozen(contract_path,CONTRACT_FILE_SHA))
    canonical=hashlib.sha256(json.dumps(c,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    need(canonical==CONTRACT_SHA and c['mode']=='production' and
         [a['arm'] for a in c['arms']]==['DYNTEAM','DYNTEAM_RACING'] and len(c['trajectories'])==6,
         'ONLY_EXACT_FROZEN_FORMAL_SIX_NOT_SMOKE_OR_OLD_ARMS')
    alias=_msg221_alias();alias.scope(c)
    trajectories=frozenset(r['trajectory_id'] for r in c['trajectories'])
    need(len(trajectories)==6,'SIX_DISTINCT_ORIGINAL_TRACKS')
    pid=os.getpid()
    def options(self,body,value):
        # All original request/seed verification runs before inspecting options.
        # No request ID is decoded and no body/value is copied or reported.
        result=original(self,body,value)
        need(os.getpid()==pid and self.manifest_sha==CONTRACT_SHA and
             self.trajectory in trajectories,'SAME_CHILD_EXACT_ORIGINAL_BOUND_CONTRACT')
        need(type(result) is dict and result.get('base_url') in (OLD,NEW),'ONLY_OLD_OR_ALREADY_NEW_PROVIDER')
        return alias.alias_options(body,result) # after original guard, before native SENT/network
    FinalBinding.seed_provider_options=options
    _INSTALLED=dict(pid=pid,original=original,selected=options,contract_sha256=canonical)
    return dict(schema='count14-msg220-formal-isolated-AUX-base-only-install-v1',
        contract_sha256=canonical,trajectories=6,upstream_base_url=NEW,
        original_request_seed_sampling_headers_KEY_SID_fees_UNKNOWN_unchanged=True,
        upstream_model_id=alias.NEW_MODEL, historical_logical_body_policy_unchanged=True,
        original_request_validator_runs_first=True,actual_AUX_request=None)
