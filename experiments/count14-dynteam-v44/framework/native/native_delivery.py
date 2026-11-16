"""Dedicated late-published per-role transport export, never an owner directory.

Host-owned 0711 directory is bind-mounted read-only before worker startup. It
contains ONLY that role's four original IPC sockets, optional CLI receipt UDS, private worker config/deny/placeholder
and Git capability. Actual native tokens, Git private files and service state
stay elsewhere. This breaks the real-PID/socket-mount initialization cycle
without changing the worker's PID/start/namespace or mounting nonexistent files.
"""
from pathlib import Path
import os,stat
from common import need,private_dir
REQUIRED_FILES=frozenset(('gitea.sock','mattermost.sock','board.sock','git.sock','mcp.json.tmpl','copilot-deny-tools.json','placeholder.token','git.capability'))
OPTIONAL_FILES=frozenset(('cli-tools.sock',))
FILES=REQUIRED_FILES|OPTIONAL_FILES
def delivery_dir(path):
 p=Path(path);need(p.is_absolute()and p.resolve()==p,'DELIVERY_CANONICAL_DIRECTORY');s=p.lstat()
 need(stat.S_ISDIR(s.st_mode)and s.st_uid==os.geteuid()and stat.S_IMODE(s.st_mode)==0o711,'DELIVERY_HOST_OWNED_0711')
 need(set(x.name for x in p.iterdir())<=FILES,'DELIVERY_EXACT_ROLE_EXPORT_ONLY')
 for child in p.iterdir():
  need(not child.is_symlink(),'DELIVERY_NO_SYMLINK')
  if child.name=='cli-tools.sock':need(stat.S_ISSOCK(child.lstat().st_mode),'DELIVERY_CLI_RECEIPT_SOCKET_TYPE')
 return p

def complete_delivery(path):
 # This checks the export only. Optional receipt UDS is NOT listener readiness;
 # the scientific launcher still proves its registered original peer/listener.
 p=delivery_dir(path);names={x.name for x in p.iterdir()}
 need(REQUIRED_FILES<=names<=FILES,'TEAM_OWNER_DELIVERY_COMPLETE_EXACT8')
 return p

def prepare_delivery(parent,roles):
 parent=private_dir(parent,create=True);need(not any(parent.iterdir()),'DELIVERY_NEW_PARENT');need(type(roles)is list and roles and len(set(roles))==len(roles),'DELIVERY_ROLES')
 from common import ident
 result={}
 for role in roles:
  ident(role);p=parent/role;p.mkdir(mode=0o700);p.chmod(0o711);delivery_dir(p);result[role]=p
 return result
