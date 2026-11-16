#!/usr/bin/env python3
"""Read-only ALL4x2 actual host endpoint address/dirfd geometry, no socket RPC.

Input is an OPS-created mapping {actual_agent_name: actual_delivery_directory}.
No file contents, models, credentials, bind/unlink/release or service changes.
"""
from pathlib import Path
import argparse,json,os,stat
from common import need,unix_socket_address
from native_delivery import delivery_dir
PURPOSES=('gitea','mattermost','board','git')
def project(actors):
 need(type(actors)is dict and len(actors)==2,'UDS_PROJECTION_EXACT_TEAM2');rows=[]
 for actor,root in sorted(actors.items()):
  for purpose in PURPOSES:
   row={'actor':actor,'purpose':purpose,'ok':False,'code':None}
   try:
    need(type(actor)is str and actor and type(root)is str,'UDS_PROJECTION_ACTOR_ROOT');parent=delivery_dir(Path(root));path=parent/(purpose+'.sock');parent_stat=parent.stat()
    row.update(host_path_bytes=len(os.fsencode(path)),basename_bytes=len(os.fsencode(path.name)),parent_device=parent_stat.st_dev,parent_inode=parent_stat.st_ino,parent_mode=stat.S_IMODE(parent_stat.st_mode),parent_uid=parent_stat.st_uid)
    with unix_socket_address(path)as address:
     row['bind_address_bytes']=len(os.fsencode(address));row['mode']='direct'if str(path)==address else'private-dirfd'
     need(row['bind_address_bytes']<=107,'UDS_PROJECTION_ADDRESS_BOUND')
     need((path.parent.stat().st_dev,path.parent.stat().st_ino)==(parent_stat.st_dev,parent_stat.st_ino),'UDS_PROJECTION_PARENT_CHANGED')
    row['ok']=True
   except Exception as exc:row['code']=getattr(exc,'code','UDS_PROJECTION_METADATA_REFUSED')
   rows.append(row)
 return {'schema':'agensh-native-host-uds-all-endpoints-v1','status':'PASS'if all(r['ok']for r in rows)else'FAIL','rows':rows,'no_bind_connect_or_rpc':True,'models':0,'release':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);a=p.parse_args()
 try:
  raw=Path(a.input).read_bytes();need(len(raw)<=65536,'UDS_PROJECTION_INPUT_BOUND');r=project(json.loads(raw))
 except Exception:r={'schema':'agensh-native-host-uds-all-endpoints-v1','status':'FAIL','rows':[],'no_bind_connect_or_rpc':True,'models':0,'release':False}
 print(json.dumps(r,sort_keys=True,separators=(',',':')));return 0 if r['status']=='PASS'else 1
if __name__=='__main__':raise SystemExit(main())
