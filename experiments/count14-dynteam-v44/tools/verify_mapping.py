#!/usr/bin/env python3
"""Verify review source hashes and syntax only. Never import delivered modules.

Without --payload this reads the review tree only. With --payload it additionally
checks the original bytes and reconstructs the unified diffs entirely in memory.
No code under review is executed, no bytecode is written, no service is contacted.
"""
from pathlib import Path
import argparse
import ast
import collections
import difflib
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--payload',type=Path)
    a=p.parse_args()
    m=json.loads((ROOT/'MAPPING.json').read_bytes())
    manifest=None
    if a.payload:
        for name,key in [('MANIFEST_PUBLIC.json','manifest_sha256'),('SOURCE_IMPORT_LAYOUT_PUBLIC.json','source_import_layout_sha256')]:
            raw=(a.payload/name).read_bytes()
            assert sha(raw)==m[key],name
            if name=='MANIFEST_PUBLIC.json':manifest=json.loads(raw)
    counts=collections.Counter(); hashes={}; errors=[]
    def syntax(raw,name):
        suffix=Path(name).suffix
        if suffix=='.py':
            compile(raw,name,'exec',dont_inherit=True);counts['python_syntax']+=1
        elif suffix in {'.js','.mjs','.cjs'}:
            if not shutil.which('node'):raise AssertionError('node required for JavaScript syntax check')
            # Parser only. Input mode avoids package.json/module-resolution effects.
            subprocess.run(['node','--input-type=module','--check'],input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
            counts['javascript_syntax']+=1
        elif suffix=='.sh':
            subprocess.run(['bash','-n'],input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
            counts['shell_syntax']+=1
        elif suffix=='.json':json.loads(raw);counts['json_syntax']+=1
        elif suffix=='.ts':counts['typescript_patch_source_not_compiled']+=1
    def original(origin,pin):
        assert Path(origin).name!='retained_formal_frozen_snapshot_v1.py'
        path=a.payload/'CODE'/origin
        assert not path.is_symlink() and path.resolve()==path
        raw=path.read_bytes()
        assert sha(raw)==pin,origin
        assert manifest['files']['CODE/'+origin]['sha256']==pin,origin
        return raw
    configured=json.loads((ROOT/'CONFIGURED_FILES.json').read_text())
    for name,row in m['files'].items():
        path=ROOT/name
        assert path.is_relative_to(ROOT) and not path.is_symlink()
        raw=path.read_bytes();pin=row.get('source_sha256',row.get('review_sha256'))
        if name in configured:
            # Publication edit: endpoints/keys moved to environment variables (see CONFIGURATION.md).
            assert configured[name]['original_sha256']==pin,('configured file original mismatch',name)
            assert sha(raw)==configured[name]['published_sha256'],('configured file content mismatch',name)
            syntax(raw,name);counts['configured_files']+=1
            continue
        assert sha(raw)==pin and len(raw)==row['bytes'],name
        assert pin not in hashes,('duplicate exported bytes',name,hashes.get(pin))
        hashes[pin]=name
        if 'source_code_path' in row:
            syntax(raw,name);counts['verbatim_source_files']+=1
            if a.payload:
                assert original(row['source_code_path'],pin)==raw,name
                for alias in row.get('equivalent_sources',[]):
                    assert original(alias['source_code_path'],alias['source_sha256'])==raw,name
                    counts['deduplicated_aliases_verified']+=1
        else:
            assert row['kind']=='unified_snapshot_delta',name
            counts['patches']+=1
            if a.payload:
                parts=[]
                for unit in row['sources']:
                    before=unit['baseline_source'];after=unit['modified_source'];relative=unit['relative_path']
                    br=b'' if before is None else original(before,unit['baseline_sha256'])
                    ar=original(after,unit['modified_sha256'])
                    parts.append(''.join(difflib.unified_diff(br.decode().splitlines(True),ar.decode().splitlines(True),fromfile='/dev/null' if before is None else 'a/'+relative,tofile='b/'+relative)))
                    syntax(ar,relative);counts['patch_units_verified']+=1
                assert ''.join(parts).encode()==raw,name
    expected=set(m['files'])|set(m['generated_files'])
    actual=set()
    for path in ROOT.rglob('*'):
        assert not path.is_symlink(),str(path)
        if path.is_file():actual.add(str(path.relative_to(ROOT)))
    assert actual==expected,('unexpected/missing files',sorted(actual-expected),sorted(expected-actual))
    assert not any(re.search(r'(?:msg\d+|held\d+|prefix\d+)',part) for name in actual for part in Path(name).parts[:-1]),'versioned output directory'
    for name in m['generated_files']:
        if name.endswith('.py'):syntax((ROOT/name).read_bytes(),name)
    # Conservative guard, not a substitute for the independent pre-publication scan.
    danger=[r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',r'\bsk-[A-Za-z0-9_-]{20,}\b',r'\bgh[pousr]_[A-Za-z0-9]{20,}\b',r'\bgithub_pat_[A-Za-z0-9_]{20,}\b',r'Bearer\s+[A-Za-z0-9_.-]{16,}',r'https?://[^\s/\"\x27]+:[^\s/@\"\x27]+@',r'https?://[^\s\"\x27]*(?:dashboard|grafana)[^\s\"\x27]*']
    for name in actual:
        raw=(ROOT/name).read_bytes();text=raw.decode()
        assert not re.search(rb'[A-Za-z0-9+/=_-]{4097,}',raw),('opaque run',name)
        for pat in danger:
            assert not re.search(pat,text,re.I),('possible secret/forbidden endpoint; inspect locally',name)
    total=sum((ROOT/name).stat().st_size for name in actual)
    assert total<20_000_000,total
    print(json.dumps({'result':'PASS','checks':'integrity, deduplication, syntax, conservative credential patterns; no runtime qualification','file_count':len(actual),'bytes':total,'counters':dict(counts)},indent=2,sort_keys=True))

if __name__=='__main__':main()
