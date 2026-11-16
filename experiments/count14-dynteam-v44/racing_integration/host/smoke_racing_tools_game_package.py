"""Finite RO cold Game code closure, pinned nloop/prompts, metadata hashes only."""
from pathlib import Path,PurePosixPath
import hashlib,json,os,stat

BASE='70e2ca54c078597e3314755064d2ef1a83344c8e'
RACING='21a0413e3262cebd5c6ac314974710937b9741b0'
OWN_FILES=('smoke_racing_tools_game_entry.py','smoke_racing_tools_game_runtime.py',
    'smoke_racing_tools_game_package.py','smoke_racing_tools_public_runner.cjs',
    'native_racing_phase_client.py','racing_native_binding.py','count14_public_racing_judge.py',
    'smoke_racing_tools_publication.py','bounded_racing_setup.py')


def need(ok,code):
    if not ok:raise ValueError(code)


def _wire(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def _sha(raw):return hashlib.sha256(raw).hexdigest()


def _safe_name(name):
    p=PurePosixPath(name)
    return type(name) is str and not p.is_absolute() and p.as_posix()==name and all(x not in ('','.','..') for x in p.parts)


def verify_package(directory,*,expected_uid=0):
    """Immutable closed map; production caller separately pins returned hash."""
    root=Path(directory);uid=os.geteuid() if expected_uid is None else expected_uid
    need(root.is_absolute() and root.resolve()==root and root.is_dir(),'DYNTEAM_RACING_PACKAGE_CANONICAL')
    rs=root.lstat();need(rs.st_uid==uid and stat.S_IMODE(rs.st_mode)==0o755,
        'DYNTEAM_RACING_PACKAGE_ROOT_FIXED_OWNER_MODE')
    meta=root/'CODE_MAP_PUBLIC.json';s=meta.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_uid==uid and stat.S_IMODE(s.st_mode)==0o444 and 0<s.st_size<=131072,
         'DYNTEAM_RACING_PACKAGE_CODE_MAP_FIXED_OWNER_MODE')
    raw=meta.read_bytes();value=json.loads(raw)
    need(set(value)=={'schema','base_commit','racing_commit','merged_commit','merged_tree','files'} and
         value['schema']=='count14-racing-guest-code-map-v1' and value['base_commit']==BASE and
         value['racing_commit']==RACING and type(value['files']) is dict,
         'DYNTEAM_RACING_PACKAGE_PINNED_MERGED_SOURCE')
    need(raw==_wire(value)+b'\n','DYNTEAM_RACING_PACKAGE_CANONICAL_MAP_BYTES')
    required=set(OWN_FILES)|{'common.py'}
    need(required<=set(value['files']) and any(k.startswith('nloop/') for k in value['files']) and
         any(k.startswith('prompts/') for k in value['files']), 'DYNTEAM_RACING_COMPLETE_GAME_CODE_CLOSURE')
    actual=set()
    for base,dirs,files in os.walk(root,followlinks=False):
        for name in dirs:
            p=Path(base)/name;ds=p.lstat()
            need(not p.is_symlink() and stat.S_ISDIR(ds.st_mode) and ds.st_uid==uid and not ds.st_mode&0o022,
                 'DYNTEAM_RACING_CODE_NO_ALIAS_OR_WRITABLE_DIRECTORY')
        for name in files:
            p=Path(base)/name;rel=p.relative_to(root).as_posix()
            if rel=='CODE_MAP_PUBLIC.json':continue
            actual.add(rel)
            need(_safe_name(rel) and rel in value['files'] and not p.is_symlink(),
                 'DYNTEAM_RACING_CODE_ONLY_CLOSED_MAP_MEMBERS')
            fs=p.lstat();need(stat.S_ISREG(fs.st_mode) and fs.st_uid==uid and stat.S_IMODE(fs.st_mode)==0o444 and
                 fs.st_size<=2*1024*1024 and _sha(p.read_bytes())==value['files'][rel],
                 'DYNTEAM_RACING_CODE_FROZEN_MEMBER_SHA_MODE')
    need(actual==set(value['files']),'DYNTEAM_RACING_CODE_COMPLETE_CLOSED_MAP')
    return _sha(raw)


def build_package(*,destination,runtime_directory,merged_source,common_source):
    """OFFLINE-only; writes a NEW destination, never changes original source."""
    root=Path(destination);runtime=Path(runtime_directory);merged=Path(merged_source);common=Path(common_source)
    need(root.is_absolute() and not root.exists() and root.parent.resolve()==root.parent,
         'DYNTEAM_RACING_PACKAGE_NEW_COLD_DIRECTORY_ONLY')
    manifest=json.loads((merged/'MERGE_MANIFEST_PUBLIC.json').read_bytes())
    need(manifest['base_commit']==BASE and manifest['racing_source_commit']==RACING,
         'DYNTEAM_RACING_BUILD_EXACT_MERGED_PIN')
    sources={name:runtime/name for name in OWN_FILES};sources['common.py']=common
    prefix='testlead/methods/racing/'
    for dirname,suffix in (('nloop','novelty-loop/nloop'),('prompts','prompts')):
        source=merged/prefix/suffix
        for path in sorted(source.rglob('*')):
            if path.is_dir():continue
            rel=path.relative_to(source).as_posix()
            if '__pycache__' in path.parts:continue
            need(not path.is_symlink() and (path.suffix=='.py' if dirname=='nloop' else path.suffix=='.md'),
                 'DYNTEAM_RACING_ONLY_SCIENTIFIC_ORCHESTRATION_CODE_AND_PROMPTS')
            key=path.relative_to(merged).as_posix()
            need(key in manifest['files'] and _sha(path.read_bytes())==manifest['files'][key]['sha256'],
                 'DYNTEAM_RACING_SELECTED_MERGED_COMPONENT_SHA')
            sources[dirname+'/'+rel]=path
    root.mkdir(mode=0o755);root.chmod(0o755)
    mapping={}
    for rel,path in sources.items():
        need(path.resolve()==path and path.is_file(),'DYNTEAM_RACING_CODE_SOURCE_NO_ALIAS')
        data=path.read_bytes();target=root/rel;target.parent.mkdir(parents=True,mode=0o755,exist_ok=True)
        target.parent.chmod(0o755)
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
        try:os.fchmod(fd,0o444);os.write(fd,data);os.fsync(fd)
        finally:os.close(fd)
        mapping[rel]=_sha(data)
    value=dict(schema='count14-racing-guest-code-map-v1',base_commit=BASE,racing_commit=RACING,
        merged_commit=manifest['merged_commit'],merged_tree=manifest['merged_tree'],files=mapping)
    (root/'CODE_MAP_PUBLIC.json').write_bytes(_wire(value)+b'\n');(root/'CODE_MAP_PUBLIC.json').chmod(0o444)
    return verify_package(root,expected_uid=os.geteuid())
