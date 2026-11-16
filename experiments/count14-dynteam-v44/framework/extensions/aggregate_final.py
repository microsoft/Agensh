"""Independent fork16+4 FINAL input, reuses original v2.1 ABI and K3 queue.

Does NOT fabricate a20M whole-team snapshot,17th worker, git commit or old agent.
Original16M CAS/archived-ledger/records are verified by the original builder (narrow
private16M entrance). New aggregate phase has separate verified frozen workspace,
consistent continuation/ledger backups and explicit fresh-agent provenance.
"""
from pathlib import Path
from decimal import Decimal
import copy,gzip,hashlib,inspect,io,json,os,sqlite3,tarfile,textwrap
from common import need,digest,wire,publish,hash_file,integer
from native_inert_archive import Header,special_kind
from native_candidate_policy import candidate,MAX_FILE,MAX_TOTAL
from collector import mapped_parts
import v21_inputs as V

def original16_builder():
 src=textwrap.dedent(inspect.getsource(V.build));old="d['target_tokens']in (10000000,20000000)"
 need(src.count(old)==1,'AGGREGATE_FINAL_EXACT_ORIGINAL_BOUNDARY_ANCHOR')
 # Private helper only. Original V.build remains unmodified for all10M/natural.
 ns=dict(V.__dict__);exec(compile(src.replace(old,"d['target_tokens']==16000000"),'<original-v21-sealed16M-base-only>','exec'),ns)
 return ns['build']

def scan_archive(cas,ref,*,member_cap):
 need(hash_file(cas.resolve(ref))==ref,'AGGREGATE_FINAL_ARCHIVE_PIN')
 rows={};total=0;seen=set();count=0
 # CRC/EOF validation before accepted data. No extraction / links / content parse.
 with gzip.open(cas.resolve(ref),'rb')as inp:
  for _ in iter(lambda:inp.read(1024*1024),b''):pass
 with tarfile.open(cas.resolve(ref),'r|gz',tarinfo=Header,errorlevel=2)as tar:
  for m in tar:
   count+=1;tar.members.clear();need(count<=member_cap,'AGGREGATE_FINAL_MEMBER_CAP')
   if special_kind(m)is not None or m.issym()or m.islnk()or m.isdir():continue
   need(m.type in(tarfile.REGTYPE,tarfile.AREGTYPE),'AGGREGATE_FINAL_ORDINARY_ONLY')
   ps=mapped_parts(m.name)
   if not candidate(ps):continue
   logical='/'.join(ps);need(logical not in seen,'AGGREGATE_FINAL_DUPLICATE_CANDIDATE_PATH');seen.add(logical)
   total+=m.size;need(0<=m.size<=MAX_FILE and total<=MAX_TOTAL,'AGGREGATE_ORIGINAL_CANDIDATE_CAPS')
   p=cas.temporary();h=hashlib.sha256();n=0
   with tar.extractfile(m)as inp,p.open('xb')as out:
    for b in iter(lambda:inp.read(1024*1024),b''):n+=len(b);need(n<=m.size,'AGGREGATE_CANDIDATE_GREW');h.update(b);out.write(b)
   need(n==m.size,'AGGREGATE_CANDIDATE_TRUNCATED');obj=cas.store(p)
   need(obj=={'sha256':h.hexdigest(),'size':n},'AGGREGATE_CANDIDATE_SHA')
   mt=Decimal(m.pax_headers.get('mtime',str(m.mtime)));need(mt.is_finite()and mt>=0,'AGGREGATE_ORIGINAL_MTIME')
   old=rows.get(obj['sha256']);row={'object':obj,'mtime_ns':int(mt*10**9),'source_path_sha256':hashlib.sha256(os.fsencode(logical)).hexdigest()}
   if old:row['mtime_ns']=max(row['mtime_ns'],old['mtime_ns'])
   rows[obj['sha256']]=row
 return rows

def verify_phase(cas,ref,original_ref,original):
 sealed=json.loads(cas.resolve(ref).read_bytes());need(sealed['schema']=='agensh-independent-fork-aggregate-search-v1'and sealed['original16_snapshot']==original_ref,'AGGREGATE_FINAL_PHASE_LINK')
 need(sealed['parent_trajectory']==original['trajectory']and sealed['original16_actual']==original['actual_search_tokens'],'AGGREGATE_FINAL_PARENT_ACCOUNTING')
 need(sealed['aggregate_cap']==4_000_000 and 0<=sealed['aggregate_search_tokens']<=4_000_000 and sealed['original_search_tokens']==original['actual_search_tokens']and sealed['actual_search_tokens']==sealed['original_search_tokens']+sealed['aggregate_search_tokens']<=20_000_000,'AGGREGATE_FINAL_COMBINED_BUDGET')
 need(sealed['freeze']['cgroup_frozen']is True and sealed['freeze']['whole_container']is True and sealed['mainline_can_continue']is True and sealed['shared_original_ledger']is False,'AGGREGATE_FINAL_FORK_ONLY_BRANCH_PHYSICALLY_PARKED')
 database=cas.resolve(sealed['continuations']);roles=['worker-00'];records,latest,ids=V._prior_records(database,sealed['phase_trajectory'],roles)
 db=sqlite3.connect(cas.resolve(sealed['durable_ledger']).as_uri()+'?mode=ro&immutable=1',uri=True)
 try:
  account=db.execute('SELECT actual,state,roles,targets FROM accounts WHERE trajectory=?',(sealed['phase_trajectory'],)).fetchone()
  need(account is not None and account[0]==sealed['aggregate_search_tokens']and account[1]=='DRAINING'and json.loads(account[2])==roles and json.loads(account[3])==[4_000_000],'AGGREGATE_FINAL_DURABLE_PHASE_ACCOUNT')
  need(db.execute('SELECT 1 FROM accounts WHERE trajectory=?',(original['trajectory'],)).fetchone()is None,'AGGREGATE_FINAL_MAIN_ACCOUNT_MUST_NOT_EXIST_IN_BRANCH_LEDGER')
  completed=set();actual=0
  for rid,role,state,upper,inp,out,receipt in db.execute('SELECT id,role,state,upper_bound,input,output,receipt_sha FROM requests WHERE trajectory=?',(sealed['phase_trajectory'],)):
   need(role=='worker-00','AGGREGATE_FINAL_FRESH_SINGLE_ROLE')
   if state=='UNKNOWN':actual+=V._approved_unknown(db,sealed['phase_trajectory'],rid,upper,inp,out,receipt)
   else:
    need(state in('SETTLED','CANCELLED_UNSENT'),'AGGREGATE_FINAL_UNRESOLVED')
    if state=='SETTLED':integer(inp,'AGGREGATE_FINAL_INPUT_TOKENS');integer(out,'AGGREGATE_FINAL_OUTPUT_TOKENS');actual+=inp+out;completed.add(rid)
  need(actual==sealed['aggregate_search_tokens']and completed==ids['worker-00'],'AGGREGATE_FINAL_COMPLETE_ORIGINAL_RECORDS')
 finally:db.close()
 return sealed,records['worker-00'],latest['worker-00']

def build(cas,original_ref,phase_ref,collection,destination,*,expected,setting,member_cap,branch_manifest):
 original=cas.verify_snapshot(original_ref,expected=expected);need(original['target_tokens']==16_000_000,'AGGREGATE_FINAL_SOURCE16M')
 sealed,records,latest=verify_phase(cas,phase_ref,original_ref,original)
 need(sealed['branch_manifest_sha256']==digest(branch_manifest),'AGGREGATE_FINAL_BRANCH_MANIFEST_BINDING')
 base=original16_builder()(cas,original_ref,collection,destination,expected=expected,setting=setting)
 home=Path(destination);folder=home/'snapshot'/'roles'/'final'
 original_seen={row['object']['sha256']for row in collection['manifest']['candidates']}
 # Frozen Git candidates already assigned to original virtual final are retained.
 old={row['object']['sha256']:row for row in collection['manifest']['candidates']if any(o['kind']=='gitea_ref'for o in row['origins'])}
 pool=[]
 for row in old.values():
  mt=max(o['mtime_ns']for o in row['origins']if o['kind']=='gitea_ref');pool.append(({**row['object'],'path':str(cas.resolve(row['object']))},mt))
 aggregate=scan_archive(cas,sealed['workspace']['archive'],member_cap=member_cap)
 for h,row in aggregate.items():
  if h not in original_seen:pool.append(({**row['object'],'path':str(cas.resolve(row['object']))},row['mtime_ns']))
 total=sum(row['object']['size']for row in collection['manifest']['candidates'])+sum(row['object']['size']for h,row in aggregate.items()if h not in original_seen)
 need(total<=MAX_TOTAL,'AGGREGATE_FINAL_UNION_ORIGINAL_TOTAL_CAP')
 provenance={'schema':'agensh-late-aggregate-final-provenance-v1','original16_snapshot':original_ref,'aggregate_phase_snapshot':phase_ref,
  'search_agent_created':True,'fresh_phase_identity':sealed['phase_trajectory'],'native_input_role':'final',
  'original_worker_identity_reused':False,'original_git_candidates':len(old),'aggregate_candidate_objects':[aggregate[h]for h in sorted(aggregate)],
  'union_dedup':'content-SHA256','no_candidate_predicate_changes':True}
 for name in('workspace.tar.gz','private-context.json','snapshot-receipt.json'):(folder/name).unlink()
 context={'source':'ORIGINAL_PERSISTED_LATE_AGGREGATE_RELAY_RECORDS_NO_SUMMARIZING_MODEL','phase':sealed['phase_trajectory'],'latest_original_record':latest,'original16_snapshot':original_ref,'aggregate_phase_snapshot':phase_ref}
 publish(folder/'private-context.json',wire(context),mode=0o400);os.utime(folder/'private-context.json',ns=(0,0))
 stats=V._write_role(folder/'workspace.tar.gz',pool,records,provenance);archive=hash_file(folder/'workspace.tar.gz')
 publish(folder/'snapshot-receipt.json',wire({'workspace_archive_sha256':archive['sha256'],'workspace_archive_bytes':archive['size']}),mode=0o400)
 policy=base['policy'];policy['roles']['final']={'archive':archive,'members':stats['members'],'bytes':stats['bytes'],'context':hash_file(folder/'private-context.json')}
 saved_path=home/'snapshot'/'saved.json';saved=json.loads(saved_path.read_bytes());saved.update(nominal_budget=20_000_000,actual_search_tokens=sealed['actual_search_tokens'],budget_gap=20_000_000-sealed['actual_search_tokens'],manifest_sha256=digest(branch_manifest),original16_snapshot_sha256=original_ref['sha256'],aggregate_phase_snapshot_sha256=phase_ref['sha256'],original_search_tokens=sealed['original_search_tokens'],aggregate_search_tokens=sealed['aggregate_search_tokens']);saved_path.unlink();publish(saved_path,wire(saved),mode=0o400)
 policy['pins']=copy.deepcopy(policy['pins']);policy['pins']['manifest']=digest(branch_manifest)
 policy.update(trajectory=sealed['phase_trajectory'],target_tokens=20_000_000,saved=hash_file(saved_path),virtual_final_is_not_search_role=False,
  late_aggregate={'schema':'agensh-v2-fork16plus4-final-v1','parent_trajectory':original['trajectory'],'original_manifest_sha256':original['pins']['manifest'],'branch_manifest_sha256':digest(branch_manifest),'fee_category':'综合分支','mainline_search_budget_delta':0,'original16_snapshot':original_ref,'phase_snapshot':phase_ref,'aggregate_phase':sealed['phase_trajectory'],
   'prompt':sealed['prompt'],'aggregate_search_tokens':sealed['aggregate_search_tokens'],'total_search_tokens':sealed['actual_search_tokens'],'same_candidate_policy':True,'phase_fresh_agent':True},
  member_cap=max(1,2*max(row['members']for row in policy['roles'].values())))
 (home/'input-policy.json').unlink();publish(home/'input-policy.json',wire(policy),mode=0o400)
 V.verify_input(home,expected_policy_sha=digest(policy),trajectory=sealed['phase_trajectory'],setting=setting)
 return {'snapshot':home/'snapshot','policy':policy,'input_policy_sha256':digest(policy),'candidate_counts':{'original_unique':len(original_seen),'aggregate_unique':len(aggregate),'union_unique':len(original_seen|set(aggregate))}}
