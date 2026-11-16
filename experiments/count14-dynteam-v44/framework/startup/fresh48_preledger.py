"""OPS-only append-only V2 prepared dry handoff, before any ledger/worker.

Does not prepare, compile, copy FINAL/keys, read task/candidate/session content,
create an account, or overwrite an original config/receipt.
"""
from pathlib import Path
import copy,os
from common import need,hash_file,wire,publish,strict
from fresh48_scope import selected
from fresh48_bootstrap import child_path,launch_metadata,HERE
from fresh48_configuration import _private
OLD_PID=1758681
OLD_START=1930662787


def rebase(c,branch,meta):
 root,_=selected('zero-model');root=Path(root)
 need(c['manifest']['root']==str(root)and c['driver_directory']==str(root/'d')and
  c['upstream']['base']=='http://127.0.0.1:12578/v1','FRESH48_PRELEDGER_SAME_DRY_CONFIG')
 need(meta['mode']=='zero-model'and meta['root']==str(root),'FRESH48_PRELEDGER_FIXED_PRIOR_MODE')
 v=copy.deepcopy(c);b=copy.deepcopy(branch)
 v['final']['environment']['PYTHONPATH']=child_path(root)
 b['pilot_campaign']=str(HERE/'deps/pilot-campaign.py')
 from aggregate_prompt import PILOT_SHA
 need(hash_file(b['pilot_campaign'])['sha256']==PILOT_SHA,'FRESH48_PRELEDGER_SAME_PILOT_BYTES')
 return v,b


def resume():
 need(False,'FRESH48_PRELEDGER_RETIRED_AFTER_ACTUAL_DRY_LEDGER')
