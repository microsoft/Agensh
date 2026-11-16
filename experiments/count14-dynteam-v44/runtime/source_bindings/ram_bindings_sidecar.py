"""Prospective-only PUBLIC RAM field binding + original real emitter callsites.

No native/scientific module changes, deployment, Docker, owner or model calls.
Native initial3=216GiB plus explicitly registered infra engineering64GiB gives
280GiB; this is a per-bootstrap forecast, NOT a six-track memory authorization.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import stat

HERE=Path(__file__).resolve().parent
RAM=280*1024**3
INITIAL_PAIR_RAM=216*1024**3
EXPLICIT_ENGINEERING_INFRA_RAM=64*1024**3
OLD_MISWIRED_DISK=575525617664
RACING='frozen-racing-private-config-entire-cold-chain-20261105T2205Z-v2/emit_racing_exact_alias_factory.py'
RACING_SHA='1321dc962dfbd844122c8e4a33f2a627d0a26e6db06573f80194ebfb004e4fa4'
FORMAL='formal100m-two-daemon-private-config-cold-wip-v3-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/emit_http_source_two_daemon_chain.py'
FORMAL_SHA='f4ad7b5bfd1707e812fe65192a660b464f7999d23ec2b8b35ea00ce5947f7535'
SCHEMAS={'RACING_SMOKE':'count14-dynteam-racing-smoke-bindings-v1','FORMAL_SIX':'count14-dynteam-formal100m-bindings-v1'}


def need(ok,code):
 if not ok:raise ValueError(code)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def wire(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def _read(path,pin):
 p=Path(path);s=p.lstat()
 need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and p.name.endswith('PUBLIC.json')and
  stat.S_ISREG(s.st_mode)and s.st_uid in(0,os.geteuid())and not s.st_mode&0o022 and
  s.st_nlink==1 and s.st_size<=4*1024*1024,'PROSPECTIVE_RAM_ORIGINAL_PUBLIC_METADATA_ONLY')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  a=os.fstat(fd);raw=os.read(fd,4*1024*1024+1);b=os.fstat(fd)
  ident=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns)
  need(ident(s)==ident(a)==ident(b)==ident(p.lstat())and len(raw)==s.st_size and hashlib.sha256(raw).hexdigest()==pin,
   'PROSPECTIVE_RAM_ORIGINAL_PUBLIC_RAW_PIN_STABLE_FD')
 finally:os.close(fd)
 return json.loads(raw)


def derive_bindings(bindings_path,bindings_sha256,*,destination,scope):
 """Only a NEW cold PUBLIC copy's RAM parameter. Correct input is reused."""
 need(scope in SCHEMAS,'PROSPECTIVE_RAM_EXACT_NEW_RACING_OR_FORMAL_SCOPE')
 value=_read(bindings_path,bindings_sha256)
 need(type(value)is dict and value.get('schema')==SCHEMAS[scope]and value.get('template_only')is False,
  'PROSPECTIVE_RAM_REAL_COLD_BINDINGS_NOT_DRAFT_OR_EXISTING_OWNER')
 previous=value['projected_additional_bytes'];need(type(previous)is int and previous in(RAM,OLD_MISWIRED_DISK),
  'PROSPECTIVE_RAM_EXPECTED_DISK_MISBIND_OR_ALREADY_CORRECT_ONLY')
 original=dict(path=str(Path(bindings_path)),sha256=bindings_sha256)
 if previous==RAM:
  return dict(bindings=original,original=original,changed=False,already_correct_no_new_file=True,
   original_scientific_schema_and_all_other_fields_preserved=True)
 root=Path(value['code_root']);output=Path(destination)
 need(root.is_absolute()and root.resolve()==root and root.is_dir()and output.is_absolute()and
  output.parent.resolve()==output.parent and output.is_relative_to(root)and
  output.name.endswith('PUBLIC.json')and not output.exists()and not output.is_symlink()and output!=Path(bindings_path),
  'PROSPECTIVE_RAM_NEW_PUBLIC_COPY_IN_ORIGINAL_CODE_ROOT_NO_REPLACE')
 before=copy.deepcopy(value);after=copy.deepcopy(value);after['projected_additional_bytes']=RAM
 inverse=copy.deepcopy(after);inverse['projected_additional_bytes']=previous
 need(wire(inverse)==wire(before),'PROSPECTIVE_RAM_EXACT_ONE_FIELD_DEEP_BYTE_INVERSE')
 raw=wire(after)+b'\n';fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
 with os.fdopen(fd,'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
 return dict(bindings=dict(path=str(output),sha256=hashlib.sha256(raw).hexdigest()),original=original,changed=True,
  only_field='projected_additional_bytes',previous_RAM_input_bytes=previous,new_RAM_input_bytes=RAM,
  source_initial_pair_RAM_bytes=INITIAL_PAIR_RAM,explicit_engineering_infra_RAM_bytes=EXPLICIT_ENGINEERING_INFRA_RAM,
  infra_estimate_not_native_limit_or_measured=True,one_field_inverse_bytes=True,
  disk_resource_plan_reserves_schema_budget_sessions_and_sampler_unchanged=True)


def _load(relative,pin):
 p=HERE.parent/relative;s=p.lstat()
 need(p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode)and not s.st_mode&0o022 and
  s.st_uid in(0,os.geteuid())and sha(p)==pin,'PROSPECTIVE_RAM_EXACT_ORIGINAL_EMITTER_PIN')
 spec=importlib.util.spec_from_file_location('count14_prospective_RAM_original_'+p.stem,p)
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def emit_racing(bindings_path,bindings_sha256,*,ram_bindings_path,original_emitter,typed_emitter,destination,new_bindings=None):
 corrected=derive_bindings(bindings_path,bindings_sha256,destination=ram_bindings_path,scope='RACING_SMOKE')
 ref=corrected['bindings'];emitter=_load(RACING,RACING_SHA)
 result=emitter.emit(original_emitter,ref['path'],ref['sha256'],destination=destination,
  typed_emitter=typed_emitter,new_bindings=new_bindings)
 return dict(original_emission=result,prospective_RAM_binding=corrected,active_smoke_modified=False)


def emit_formal(bindings_path,bindings_sha256,*,ram_bindings_path,destination,
 tester_bindings_path=None,tester_bindings_sha256=None,new_bindings=None):
 corrected=derive_bindings(bindings_path,bindings_sha256,destination=ram_bindings_path,scope='FORMAL_SIX')
 ref=corrected['bindings'];emitter=_load(FORMAL,FORMAL_SHA)
 result=emitter.emit(ref['path'],ref['sha256'],destination=destination,
  tester_bindings_path=tester_bindings_path,tester_bindings_sha256=tester_bindings_sha256,new_bindings=new_bindings)
 return dict(original_emission=result,prospective_RAM_binding=corrected,active_smoke_modified=False,
  six_formal_memory_or_admission_authorization_created=False)
