"""Fixed existing-custodian apply-fix prefix. Does NOT resume SEARCH or thaw.

OPS may apply via the current FINAL-only custodian's approved local socket after
pin verification. A separate qualified SEARCH rebind/release suffix is required.
"""
from pathlib import Path
import os
from common import need,hash_file,strict,wire,publish,digest
from bridge import process_identity
from expansion100_contract import OLD_ROOT,OLD_EID,write_authorization,append_existing_targets
from expansion100_quota import install
HERE=Path(__file__).resolve().parent

def apply(c):
 need(os.geteuid()==0 and c.__class__.__module__=='disk_custodian'and c.__class__.__name__=='Custodian',
      'EXP100_EXISTING_FINAL_CUSTODIAN_ONLY_NOT_SCIENTIFIC_DRIVER')
 need(process_identity(os.getpid())==c.identity,'EXP100_CURRENT_CUSTODIAN_IDENTITY')
 need(set(c.ds)=={'main','branch'},'EXP100_ORIGINAL_TWO_DOMAINS')
 main=c.ds['main'];branch=c.ds['branch'];root=Path(OLD_ROOT)
 need(main.ledger.home==root/'d/ledger'and branch.ledger.home==root/'d/late-aggregate-fork/ledger',
      'EXP100_ORIGINAL_LEDGER_PATHS_NO_NEW_DATABASE')
 m=main.configuration.template['manifest']
 need((m['root'],m['experiment_id'])==(OLD_ROOT,OLD_EID)and
      digest(m)=='d514461a18bbecdc207b91947df41a764ce87f23675e86f259391619166833a2',
      'EXP100_ORIGINAL_PINNED_MANIFEST')
 need(c.slots.active()==0,'EXP100_CURRENT_FINAL_POPEN_MUST_NATURALLY_END')
 # Scope guards/old fees/queue/result rows are intentionally never changed.
 policy=write_authorization(m)
 result=append_existing_targets(main.ledger,m)
 quota=install(c.peer,[d.capacity for d in c.ds.values()],final_slots=c.slots,group='existing-1-16')
 record={'schema':'agensh-v2-original-custodian100m-preparation-v1','owner':c.identity,
  'authorization_sha256':digest(policy),'targets':result,'quota':quota,
  'SEARCH_resumed':False,'cgroups_thawed':False,'session_changed':False,
  'required_remaining':'QUALIFIED_SAME_SESSION_SEARCH_OWNER_TAKEOVER'}
 # One append-only preparation receipt; a failed write never implies release.
 path=c.home/'USER100M_PREPARED_NO_SEARCH_RELEASE.json'
 if path.exists():need(strict(path.read_bytes())==record,'EXP100_PREPARATION_RECEIPT_CONFLICT')
 else:publish(path,wire(record),mode=0o400)
 c.record('USER100M_PREPARED_NO_SEARCH_RELEASE',record)
 return record
