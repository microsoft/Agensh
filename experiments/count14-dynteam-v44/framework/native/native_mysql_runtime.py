"""Pinned original MySQL8.4.10 ELF closure, never host config or data discovery."""
from pathlib import Path
import os
from common import need, hash_file, digest, strict

BASE=Path(__file__).resolve().parent
HANDOFF=BASE/'NATIVE_MYSQL_PUBLIC_RUNTIME_CONSUMED.json'
SUPPLIED_MANIFEST_SHA256='791c8ed0479ea480ccd15ee2762c19961565aab6b6df33d3f1fb53df699e51d4'
IMAGE='sha256:c831a0f11348d402b43d77453e17d770be2eef356615a2823fe0f5a0d6c8b9af'

class NativeMysqlRuntime:
    def __init__(self,root,manifest,expected_manifest_sha256):
        self.root=Path(root);self.manifest=Path(manifest)
        need(self.root.is_absolute() and self.root.resolve()==self.root and not self.root.is_symlink(),
             'MYSQL_RUNTIME_CANONICAL_ROOT')
        need(hash_file(self.manifest)['sha256']==expected_manifest_sha256,'MYSQL_RUNTIME_ORIGINAL_MANIFEST')
        self.metadata=strict(self.manifest.read_bytes())
        need(self.metadata['schema']=='agensh-owned-original-public-mysql-runtime-closure-local-handoff-v1'
             and self.metadata['original_image_id']==IMAGE,'MYSQL_RUNTIME_ORIGINAL_IMAGE')
        self.entries=self.metadata['regular_runtime_files'];self.manifest_sha=expected_manifest_sha256
        self.entrypoints={'mysql':'usr/bin/mysql','mysqldump':'usr/bin/mysqldump','mysqld':'usr/sbin/mysqld'}
        need(self.metadata['entrypoints']==self.entrypoints and type(self.entries)is list and self.entries,
             'MYSQL_RUNTIME_FIXED_ENTRIES')
        self.pin={'schema':'agensh-original-mysql-runtime-pin-v1','image':IMAGE,
                  'manifest_sha256':self.manifest_sha,'files_sha256':digest(self.entries),
                  'invocation':'original-ld-linux-inhibit-cache-private-library-path'}
        self.pin_sha=digest(self.pin);self.verify()

    @classmethod
    def supplied(cls):
        meta=strict(HANDOFF.read_bytes())
        return cls(BASE.parent/meta['runtime_root'],HANDOFF,SUPPLIED_MANIFEST_SHA256)

    def verify(self):
        need(hash_file(self.manifest)['sha256']==self.manifest_sha,'MYSQL_RUNTIME_MANIFEST_CHANGED')
        expected=set()
        for row in self.entries:
            need(type(row)is dict and set(row)=={'member','bytes','sha256'},'MYSQL_RUNTIME_ENTRY_FIELDS')
            rel=Path(row['member'])
            need(not rel.is_absolute() and '..'not in rel.parts and str(rel)==row['member']
                 and row['member']not in expected,'MYSQL_RUNTIME_ENTRY_PATH')
            expected.add(row['member']);p=self.root/rel
            need(p.resolve()==p and not p.is_symlink() and hash_file(p)=={'size':row['bytes'],'sha256':row['sha256']},
                 'MYSQL_RUNTIME_ORIGINAL_ELF_CHANGED')
        actual={str(p.relative_to(self.root))for p in self.root.rglob('*')if p.is_file()or p.is_symlink()}
        need(actual==expected,'MYSQL_RUNTIME_EXACT_PUBLIC_CLOSURE')
        need(set(self.entrypoints.values())|{'usr/lib64/ld-linux-x86-64.so.2'}<=expected,
             'MYSQL_RUNTIME_REQUIRED_ORIGINAL_EXECUTABLES')
        return dict(self.pin)

    def command(self,name,args):
        need(name in self.entrypoints and type(args)is list and all(type(x)is str and '\0'not in x for x in args),
             'MYSQL_RUNTIME_FIXED_COMMAND')
        self.verify()
        return [str(self.root/'usr/lib64/ld-linux-x86-64.so.2'),'--inhibit-cache','--library-path',
                str(self.root/'usr/lib64')+':'+str(self.root/'usr/lib64/mysql/private'),
                str(self.root/self.entrypoints[name]),*args]
