"""One fixed qualified120s public reader leaf, before any fresh router launch.

The native host still verifies/copies all19 original compiled modules. Replace
only its old10s budget_pause_clock.js by the exact51/51 live qualified120s leaf.
No TypeScript/model/private content is opened; OPS consumes public code only.
"""
from pathlib import Path
import hashlib,os,stat
from common import need,hash_file,publish,wire,digest
from expansion100_contract import NEW_ROOT
OLD='24665c029398a60e4e382ae5c37aad11874a6f6e64d3b75b3a2e953270e65348'
NEW={'size':8341,'sha256':'ee22d21d1285b251aa872e0b3f2a25d5d959b3a910ff9e28db4b4a65b99e2b6f'}
OTHER={'main.js':'708dff3d068c6bef2e9e20cbdd6728333587a2d7caaa5eb8185cc7776a1d4a71',
       'acp_socket_channel.js':'5cbac69c8bec0e8b7e10acb86d4ec49c0622cfacf283b0ae765752e4523dcd86',
       'native_startup_hold.js':'7676e89dca0abe41360cb63b789bedfeba039895f0f7d4b2c6776531200439be'}

def check_metadata(meta):
 need(meta['public_only']if 'public_only'in meta else meta['public_code_hash_only'],'FRESH48_READER_PUBLIC_CODE_METADATA_ONLY')
 rows=meta['rows'];need(len(rows)==51,'FRESH48_READER_ALL51_EXISTING_ROLES')
 for r in rows:
  files={Path(x['container_path']).name:x for x in r['files']}
  need(set(files)==set(OTHER)|{'budget_pause_clock.js'},'FRESH48_READER_FOUR_ORIGINAL_PUBLIC_MODULES')
  need({k:files['budget_pause_clock.js'][k]for k in('size','sha256')}==NEW,
       'FRESH48_READER_ACTUAL_QUALIFIED120_PIN')
  need(all(files[name]['sha256']==pin for name,pin in OTHER.items()),'FRESH48_READER_OTHER_THREE_UNCHANGED')
 return rows

def stage(meta,destination):
 """OPS only, zero requests. Source registeredPID/start is rechecked fresh."""
 from bridge import process_identity
 rows=check_metadata(meta);dest=Path(destination)
 need(dest==Path(NEW_ROOT)/'config/reader120/budget_pause_clock.js'and dest.parent.resolve()==dest.parent,
      'FRESH48_READER_FIXED_PRIVATE_STAGE_DESTINATION')
 need(not dest.exists()and not dest.is_symlink(),'FRESH48_READER_FRESH_STAGE')
 selected=None
 for row in rows:
  try:p=process_identity(row['pid'])
  except FileNotFoundError:continue
  if p['pid']!=row['pid']or p['start_ticks']!=row['start_ticks']:continue
  f=next(v for v in row['files']if Path(v['container_path']).name=='budget_pause_clock.js')
  source=Path(f['read_via']);need(str(source)==f"/proc/{row['pid']}/root/app/count14-source/budget_pause_clock.js",
                             'FRESH48_READER_EXACT_REGISTERED_PUBLIC_PROCESS_LEAF')
  need(hash_file(source)==NEW,'FRESH48_READER_FRESH_PUBLIC_SOURCE_PIN')
  raw=source.read_bytes();need(len(raw)==NEW['size']and hashlib.sha256(raw).hexdigest()==NEW['sha256'],
                            'FRESH48_READER_COPY_CONSISTENCY')
  need(process_identity(row['pid'])==p,'FRESH48_READER_SAME_PROCESS_AFTER_PUBLIC_COPY')
  selected=(row,raw);break
 need(selected is not None,'FRESH48_READER_NO_REGISTERED_ORIGINAL_PUBLIC_CODE_SOURCE')
 dest.parent.mkdir(mode=0o700);publish(dest,selected[1],mode=0o444);dest.chmod(0o444)
 publish(dest.parent/'PUBLIC_READER_BINDING.json',wire({'schema':'agensh-v2-new48-public-reader120-pin-v1',
   'public_module_pin':NEW,'source_registered_pid':selected[0]['pid'],'source_start_ticks':selected[0]['start_ticks'],
   'all51_qualified_same_pin':True,'private_bodies_read':False,'models':0}),mode=0o400)
 return dict(NEW)

def install_host(host,staged,record):
 staged=Path(staged)
 need(staged==Path(NEW_ROOT)/'config/reader120/budget_pause_clock.js'and staged.resolve()==staged
      and hash_file(staged)==NEW,'FRESH48_READER_FIXED_QUALIFIED_STAGE')
 need(not getattr(host,'_fresh48_reader120',False),'FRESH48_READER_HOST_HOOK_ONCE')
 original=host._router_source
 def source(row):
  need(Path(row['layout']).is_relative_to(Path(NEW_ROOT)),'FRESH48_READER_NEW_ROOT_ONLY')
  directory=original(row);target=directory/'budget_pause_clock.js'
  need(directory.resolve()==directory and directory==Path(row['root'])/'router-public-source',
       'FRESH48_READER_ORIGINAL_FRESH_ROUTER_DIRECTORY')
  need(hash_file(target)['sha256']==OLD and target.lstat().st_nlink==1,
       'FRESH48_READER_EXACT_OLD10S_PUBLIC_LEAF')
  need(all(hash_file(directory/n)['sha256']==p for n,p in OTHER.items()),
       'FRESH48_READER_OTHER_THREE_ORIGINAL_MODULE_PINS')
  raw=staged.read_bytes();need(len(raw)==NEW['size']and hashlib.sha256(raw).hexdigest()==NEW['sha256'],
                            'FRESH48_READER_STAGED_BYTES_UNCHANGED')
  directory.chmod(0o755)
  try:
   target.unlink();publish(target,raw,mode=0o444);target.chmod(0o444)
  finally:directory.chmod(0o555)
  need(hash_file(target)==NEW,'FRESH48_READER_FINAL120_BYTES')
  record('USER100M_NEW48_ROUTER_PUBLIC_READER120_BOUND',{'trajectory':row['row']['trajectory_id'],
    'old_public_sha256':OLD,'new_public_pin':NEW,'other18_compiled_modules_unchanged':True,
    'wire_lease_seconds':10,'reader_lease_seconds':120,'CLI_or_router_started_by_hook':False})
  return directory
 host._router_source=source;host._fresh48_reader120=True
 return {'qualified_public_leaf':NEW,'wire_lease_seconds':10,'reader_lease_seconds':120}
