"""Bind affinity to the native runtime's one HOME, before SEARCH release.

The original worker mounts roles[role]['session'] at /opt/data and the
unchanged native entrypoint uses /opt/data/home as HOME. The extra 'home' is
therefore a mount translation, never a search/fallback over session directories.
No HOME/session contents, prompts, model output or credentials are opened.
"""
from pathlib import Path
import stat
from common import need,digest
from fresh48_session import CliSessions


def bind_runtime_homes(sessions,roles,layout,gate):
 from admission_gate import AdmissionGate
 need(type(sessions)is CliSessions and type(gate)is AdmissionGate,
      'FRESH48_HOME_ORIGINAL_SESSION_MAP_AND_GATE')
 layout=Path(layout);names=list(sessions.homes)
 need(type(roles)is dict and set(roles)==set(names)and
      all(type(row)is dict and set(row)=={'workspace','session'}for row in roles.values()),
      'FRESH48_HOME_EXACT_NATIVE_ROLE_MOUNTS')
 f=gate.ledger.frontier(sessions.t)
 need(f['generation']==1 and f['state']=='RUNNING'and f['actual']==0 and
      f['unresolved']==f['reserved']==f['active_operations']==0,
      'FRESH48_HOME_BEFORE_FIRST_MODEL_ONLY')
 with gate.ledger.mutex:
  need(not gate.ledger.db.execute('SELECT 1 FROM requests WHERE trajectory=?',(sessions.t,)).fetchone(),
       'FRESH48_HOME_NO_RESERVED_OR_SENT_REQUEST')
 desired={};mounts={}
 for role in names:
  mount=Path(roles[role]['session']);expected=layout/'host-workers'/role/'home'
  need(layout.is_absolute()and layout.resolve()==layout and mount==expected and
       mount.resolve()==mount,'FRESH48_HOME_ONE_NATIVE_MANIFEST_MOUNT_NO_FALLBACK')
  st=mount.lstat()
  need(stat.S_ISDIR(st.st_mode)and not mount.is_symlink(),'FRESH48_HOME_NATIVE_MOUNT_DIRECTORY')
  home=mount/'home'
  need(home.resolve()==home,'FRESH48_HOME_CANONICAL_NATIVE_HOME')
  if home.exists()or home.is_symlink():
   s=home.lstat();need(stat.S_ISDIR(s.st_mode)and not home.is_symlink(),
                      'FRESH48_HOME_CANONICAL_NATIVE_HOME')
  desired[role]=home;mounts[role]=mount
 # No ledger/RPC under session-map lock. Original startup admission is still
 # held; no accepted request/session can be rebound. Future CLI-created HOME
 # metadata is checked by the unchanged CliSessions.__getitem__.
 with gate.condition:
  need(sessions.t in gate.startup_held and not gate.closed,
       'FRESH48_HOME_ORIGINAL_STARTUP_HOLD_REQUIRED')
  with sessions.lock:
   need(not sessions.values,'FRESH48_HOME_NEVER_REBIND_OBSERVED_SESSION')
   need(sessions.homes==mounts,'FRESH48_HOME_EXACT_UNBOUND_NATIVE_MOUNTS')
   sessions.homes=desired
 value={'schema':'agensh-v2-fresh48-native-HOME-mount-binding-v1',
        'trajectory':sessions.t,'roles':len(names),'runtime_mounts_sha256':digest({r:str(p)for r,p in mounts.items()}),
        'HOME_relative_to_native_session_mount':'home','metadata_only':True,
        'startup_hold_retained':True,'requests_replayed':0,'session_created_or_rewritten':False}
 sessions.record('FRESH48_NATIVE_RUNTIME_HOME_BOUND_BEFORE_SEARCH_RELEASE',value)
 return value
