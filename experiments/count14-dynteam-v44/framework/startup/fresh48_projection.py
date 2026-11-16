"""Reuse TWO qualified future-branch seams; no old owner recovery suffix.

Public Gitea title/name spelling and private physical MySQL inert socket only.
Original visible archive guards and native projection order stay unchanged.
"""
from pathlib import Path
from common import need,hash_file


def install():
 import aggregate_projection as P,aggregate_install as A
 import branch_projection_repair as schema,private_db_repair as private
 from expansion100_contract import NEW_ROOT
 need(NEW_ROOT in('/mnt/ptb-scratch2/ag30v2x48','/mnt/ptb-scratch2/ag30x48g'),'FRESH48_PROJECTION_FIXED_NEW_SCOPE')
 need(not hasattr(P,'_fresh48_qualified_projection'),'FRESH48_FUTURE_PROJECTION_ONCE')
 need(hash_file(Path(P.__file__))['sha256']==schema.PROJECTION_SHA==private.PROJECTION_SHA,
  'FRESH48_SAME_ORIGINAL_PUBLIC_PROJECTION')
 original_unpack=P.unpack
 P.gitea=schema.fix_gitea(P)
 project=private.projector(P)
 P.project=project;A.project=project
 need(P.unpack is original_unpack,'FRESH48_VISIBLE_UNPACK_UNCHANGED')
 P._fresh48_qualified_projection=True
 return {'same_qualified_future_seams':True,'public_schema_title_or_name':True,
  'private_mysql_socket_links_inert_only':True,'original_visible_unpack_unchanged':True,
  'old_root_or_session_recovery_called':False,'models':0}
