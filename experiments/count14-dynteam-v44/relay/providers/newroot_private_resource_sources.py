"""Prospective new-arm private source choice; no current graph hot-patch.

Original producer validates the complete frozen allocation plan before this
call. Only the exact formal-six/isolated390 contracts may select this bundle;
original OWN-only fixtures explicitly retain their original fixture sampler.
Only child/hash changes. No factory/bootstrap/python/plan/body is substituted.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_HOSTNAME = _count14_os.environ.get('COUNT14_HOSTNAME', 'count14-host')
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
from dataclasses import replace
import hashlib,json,os,stat

HERE=Path(__file__).resolve().parent
FORMAL='9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
RACING='3902509c2b0daf9dea0d7421e26cf7dd29e878aebd6cdd4699615e31bd7fc937'
MANIFEST='725748fdaf94767dff3943465e49bc5130718f6d6579b92b7a26b7ce0883679d'
ORIGINAL_CHILD='137aa6c8dbc863a21ac7f81abca85139b40664d1d149d75701d60b6d4ec0b583'
CHILD='f80a9758323acc3e830b0ad48075f5c6cb2b4d5683862f6ab1f67c325819adf3'
BOOTSTRAP='33b94ab50a4552b23e868508639a24cc534893aee6c08d7a5e5e9f0b9ec461aa'

def need(ok,code):
 if not ok:raise ValueError(code)
def scope(core):
 from common import digest
 c=core.contract;need([a['arm']for a in c['arms']]==['DYNTEAM','DYNTEAM_RACING'],
   'EXACT18_NEWROOT_ONLY_TWO_REGISTERED_NEW_ARMS')
 if c['mode']=='production':
  need(digest(c)==FORMAL and len(core.rows)==6 and
    {(r['arm'],r['block'])for r in core.rows.values()}=={(a,b)for a in('DYNTEAM','DYNTEAM_RACING')for b in(1,2,3)},
    'EXACT18_ONLY_FROZEN_FORMAL_SIX_CONTRACT')
 else:
  need(c['mode']=='smoke'and digest(c)==RACING and len(core.rows)==2 and
   tuple(a['root']for a in c['arms'])==((_C14_SCRATCH + '/ct14-dtr-smoke-20261105/u'),(_C14_SCRATCH + '/ct14-dtr-smoke-20261105/r')),
   'EXACT18_ONLY_FROZEN_ISOLATED390_PAIR_CONTRACT')
 return True
def frozen_source(original,*,directory):
 from native_resource_producer import ResourceSamplerSources
 need(type(original)is ResourceSamplerSources and original.bootstrap_sha256==BOOTSTRAP and
      original.child_sha256==ORIGINAL_CHILD,'EXACT18_ONLY_ORIGINAL_TYPED_CHILD_AND_BOOTSTRAP')
 old=Path(original.child);s=old.lstat()
 need(old.is_absolute()and old.resolve()==old and old.name=='native_resource_sample_child.py'and
      stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_uid in(0,os.geteuid())and not s.st_mode&0o022 and
      hashlib.sha256(old.read_bytes()).hexdigest()==original.child_sha256,
      'EXACT18_ORIGINAL_INPUT_CHILD_STILL_PASSES_ORIGINAL_FROZEN_SOURCE_GUARD')
 prior_bootstrap=old.with_name('native_cold_owner_entry.py')
 need(prior_bootstrap.resolve()==prior_bootstrap and not prior_bootstrap.is_symlink()and
      hashlib.sha256(prior_bootstrap.read_bytes()).hexdigest()==original.bootstrap_sha256,
      'EXACT18_ORIGINAL_INPUT_BOOTSTRAP_NOT_SILENTLY_NORMALIZED')
 home=Path(directory);s=home.lstat()
 need(home.is_absolute()and home.resolve()==home and stat.S_ISDIR(s.st_mode)and
      s.st_uid in(0,os.geteuid())and not s.st_mode&0o022,'EXACT18_CANONICAL_FROZEN_SOURCE_BUNDLE_NOT_RUNTIME_CACHE')
 m=home/'SOURCE_MANIFEST_PUBLIC.json';s=m.lstat();raw=m.read_bytes()
 need(m.resolve()==m and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_uid in(0,os.geteuid())and
      stat.S_IMODE(s.st_mode)==0o444 and hashlib.sha256(raw).hexdigest()==MANIFEST,
      'EXACT18_REVIEWED_FIXED_PRIVATE_SOURCE_MANIFEST')
 value=json.loads(raw);need(len(value['files'])==8,'EXACT18_EXACT_REVIEWED_HELPER_MEMBERS')
 for name,row in value['files'].items():
  p=home/name;s=p.lstat()
  need(Path(name).name==name and p.resolve()==p and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and
       s.st_uid in(0,os.geteuid())and stat.S_IMODE(s.st_mode)==0o444 and
       hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],
       'EXACT18_ALL_PRIVATE_CHILD_HELPERS_REGULAR_RO_EXACT_BYTES')
 need(value['files']['native_resource_sample_child.py']['sha256']==CHILD and
      value['files']['native_cold_owner_entry.py']['sha256']==BOOTSTRAP,'EXACT18_FIXED_CHILD_ORIGINAL_BOOTSTRAP_PAIR')
 return replace(original,child=home/'native_resource_sample_child.py',child_sha256=CHILD)
def select_for_newroot(original,*,core):
 from native_resource_producer import ResourceSamplerSources
 from original_relay_core import OriginalRelayCore
 need(type(original)is ResourceSamplerSources and type(core)is OriginalRelayCore and
      not hasattr(core,'resource_producer')and not core.closed and not core.scientific_activation_qualified and
      not core.ledger.memory_faults and set(core.gate.startup_held)==set(core.rows),
      'EXACT18_ONLY_NEW_UNFAULTED_UNRELEASED_ORIGINAL_CORE_AND_TYPED_SOURCES')
 with core.ledger.mutex:
  need(all(core.ledger.db.execute('SELECT COUNT(*)FROM '+n).fetchone()[0]==0
       for n in('requests','unknown_charges','aux_scopes','aux_permits')),
       'EXACT18_PROSPECTIVE_BEFORE_SCIENCE_UNKNOWN_OR_AUX_ONLY')
 if core.qualification_only:
  need(os.uname().nodename!=(_C14_HOSTNAME)and getattr(core.ledger,'_dynteam_qualification_only',None)is True and
       any(p.startswith('OWN-')for p in Path(core.home).parts),'EXACT18_OWN_FIXTURE_NEVER_A_PRODUCTION_SCOPE_OVERRIDE')
  return original # Explicit original OWN allocation fixtures; no old-root reads.
 scope(core)
 need(os.geteuid()==0 and os.uname().nodename==(_C14_HOSTNAME),
      'EXACT18_PRODUCTION_SOURCE_SELECTION_ON_REGISTERED_HOST_ONLY')
 selected=frozen_source(original,directory=HERE/'exact18-sampler-source-v1')
 from newarms_provider_sources import sampler_after_original_selection
 return sampler_after_original_selection(selected,contract=core.contract)
