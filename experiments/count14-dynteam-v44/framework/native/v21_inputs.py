"""Trusted Agensh immutable snapshot -> explicit native v2.1 input view.

Input-role proposal_N/final names are a serialization ABI, not search agents or
legacy scientific setting identities. No model/evaluation is run by this module.
Only original candidate bytes and persisted prior relay records are copied.
Source trees, CLI executables, new prompts/findings, and evaluator data are not
reclassified as records. Actual FINAL execution needs the separate native domain.
"""
from pathlib import Path
from decimal import Decimal
import collections,gzip,hashlib,io,json,os,re,sqlite3,tarfile,uuid
from common import need,integer,sha,wire,digest,publish,hash_file,strict,regular_fd
from native_inert_archive import Header,special_kind,Stop as HeaderStop
from native_candidate_policy import MAX_FILE,MAX_TOTAL

META_MTIME=0
DB_CAP=2*2**30
RECORD_CAP=MAX_FILE


def _database(cas,archive_ref,destination):
    """Extract only the native consistent backup file; never extractall/links."""
    archive=cas.resolve(archive_ref);found=False
    try:
        with gzip.open(archive,'rb')as stream:
            for _ in iter(lambda:stream.read(1024*1024),b''):pass
        with tarfile.open(archive,'r|gz',tarinfo=Header,errorlevel=2)as tar:
            entries=0
            for member in tar:
                entries+=1;tar.members.clear();need(entries<=1000,'FINAL_CONTINUATION_BACKUP_MEMBERS')
                if special_kind(member)is not None or member.issym()or member.isdir():continue
                if member.name!='continuations.sqlite':continue
                need(not found and member.type in (tarfile.REGTYPE,tarfile.AREGTYPE)and 0<member.size<=DB_CAP,'FINAL_CONTINUATION_BACKUP_TYPE_SIZE')
                found=True;n=0
                with tar.extractfile(member)as inp,destination.open('xb')as out:
                    for block in iter(lambda:inp.read(1024*1024),b''):
                        n+=len(block);need(n<=member.size,'FINAL_CONTINUATION_BACKUP_GREW');out.write(block)
                    out.flush();os.fsync(out.fileno())
                need(n==member.size,'FINAL_CONTINUATION_BACKUP_TRUNCATED');destination.chmod(0o400)
    except (tarfile.TarError,HeaderStop,EOFError):need(False,'FINAL_CONTINUATION_ARCHIVE_REFUSED')
    need(found,'FINAL_NATIVE_CONSISTENT_CONTINUATION_BACKUP_REQUIRED')
    need(hash_file(archive)==archive_ref,'FINAL_CONTINUATION_ARCHIVE_CHANGED')
    return destination


def _prior_records(database,trajectory,roles):
    """Read private, hash-sealed original JSON records, no semantic filtering.

    The complete preceding histories are kept as records, not just a chosen
    "best" last message. A parked unsent request includes already completed
    tool results; it is a prior record, not a new model/FINAL action.
    """
    records={role:[]for role in roles};latest={role:None for role in roles};completed_ids={role:set()for role in roles}
    try:
        db=sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            for rowid,response_id,body in db.execute('SELECT rowid,id,body FROM states ORDER BY rowid'):
                need(len(body)<=RECORD_CAP,'FINAL_PRIVATE_RECORD_CAP');value=strict(body);identity=value.get('identity')
                need(type(identity)is list and len(identity)==2,'FINAL_CONTINUATION_IDENTITY')
                if identity[0]!=trajectory:continue
                need(identity[1]in records,'FINAL_UNREGISTERED_ROLE_RECORD');role=identity[1]
                need(type(value.get('history'))is list,'FINAL_HISTORY_RECORD')
                record={'kind':'completed_relay_record','response_id':response_id,'history':value['history']}
                raw=wire(record);need(len(raw)<=RECORD_CAP,'FINAL_PRIVATE_RECORD_CAP');records[role].append((digest({'response_id':response_id})+'.json',raw));latest[role]=record;completed_ids[role].add(response_id)
            for rowid,rid,identity,request,generation in db.execute('SELECT rowid,id,identity,request,generation FROM parked ORDER BY rowid'):
                identity=strict(identity)
                if identity[0]!=trajectory:continue
                need(identity[1]in records,'FINAL_UNREGISTERED_ROLE_RECORD');role=identity[1]
                if generation is not None:continue # successful model records already retained above
                need(len(request)<=RECORD_CAP,'FINAL_PRIVATE_RECORD_CAP');request=strict(request);need(type(request.get('messages'))is list,'FINAL_PARKED_REQUEST_RECORD')
                record={'kind':'unadmitted_next_call_prior_tool_results','response_id':rid,'messages':request['messages'],'not_a_model_execution':True}
                raw=wire(record);need(len(raw)<=RECORD_CAP,'FINAL_PRIVATE_RECORD_CAP');records[role].append((digest({'parked':rid})+'.json',raw));latest[role]=record
        finally:db.close()
    except sqlite3.Error:need(False,'FINAL_NATIVE_CONTINUATION_DATABASE_REFUSED')
    return records,latest,completed_ids


def _write_role(path,candidates,records,provenance):
    """Deterministic, ordinary-only new native ABI archive; original mtimes kept."""
    total=0;members=0;rows=[]
    for name,raw in records:rows.append(('output/agensh-history/'+name,raw,None,META_MTIME))
    rows.append(('output/agensh-provenance.json',wire(provenance),None,META_MTIME))
    for obj,mtime in candidates:rows.append(('pocs/'+obj['sha256']+'.bin',None,obj,mtime))
    with path.open('xb')as raw:
        with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0,compresslevel=1)as gz:
            with tarfile.open(fileobj=gz,mode='w|',format=tarfile.PAX_FORMAT)as tar:
                for name,data,obj,mtime in sorted(rows,key=lambda row:row[0]):
                    integer(mtime,'FINAL_ORIGINAL_MTIME')
                    size=len(data)if data is not None else obj['size'];need(size<=MAX_FILE,'NATIVE_FINAL_FILE_CAP');total+=size;need(total<=MAX_TOTAL,'NATIVE_FINAL_TOTAL_CAP')
                    info=tarfile.TarInfo(name);info.mode=0o444;info.uid=info.gid=0;info.mtime=mtime//10**9;info.pax_headers={'mtime':str(Decimal(mtime)/Decimal(10**9))};info.size=size
                    if data is not None:tar.addfile(info,io.BytesIO(data))
                    else:
                        with regular_fd(obj['path'])as fd,os.fdopen(os.dup(fd),'rb')as stream:
                            class Hashed:
                                def __init__(self):self.hash=hashlib.sha256();self.n=0
                                def read(self,length=-1):
                                    block=stream.read(length);self.hash.update(block);self.n+=len(block);return block
                            reader=Hashed();tar.addfile(info,reader)
                            need(reader.n==size and reader.hash.hexdigest()==obj['sha256'],'NATIVE_FINAL_CANDIDATE_COPY_SHA')
                        need(hash_file(obj['path'])=={'size':size,'sha256':obj['sha256']},'NATIVE_FINAL_CANDIDATE_CHANGED')
                    members+=1
        raw.flush();os.fsync(raw.fileno())
    path.chmod(0o400);return {'members':members,'bytes':total}


def _approved_unknown(db,trajectory,rid,upper,inp,out,receipt_sha):
    """Frozen, user-approved budget settlement ONLY; never model completion.
    Raw request/NULL usage and absent provider response remain unchanged.
    All reads are from the immutable sealed ledger, never a live side channel.
    """
    integer(upper,'FINAL_UNKNOWN_UPPER',1)
    need(inp is None and out is None and receipt_sha is None,'FINAL_UNKNOWN_NO_INVENTED_USAGE')
    policy=db.execute('SELECT singleton,version FROM unknown_policy').fetchall()
    need([tuple(r)for r in policy]==[(1,'USER_20261027_RESERVATION_V1')],'FINAL_UNKNOWN_EXPLICIT_POLICY')
    charges=db.execute('SELECT upper_bound,settlement_seq FROM unknown_charges WHERE request_id=?',(rid,)).fetchall()
    need(len(charges)==1 and charges[0][0]==upper and type(charges[0][1])is int and charges[0][1]>0,'FINAL_UNKNOWN_UNIQUE_UPPER_SETTLEMENT')
    rows=db.execute('SELECT trajectory,kind,metadata FROM events WHERE seq=?',(charges[0][1],)).fetchall()
    expected={'request_id':rid,'search_budget_charge':upper,'usage_available':False,'original_state':'UNKNOWN','physical_terminal_claimed':False,'no_replay':True}
    need(len(rows)==1 and rows[0][0]==trajectory and rows[0][1]=='UNKNOWN_CHARGED_AT_RESERVATION' and strict(rows[0][2])==expected,'FINAL_UNKNOWN_AUTHORIZED_SETTLEMENT_EVENT')
    return upper


def build(cas,snapshot_ref,collection,destination,*,expected,setting):
    d=cas.verify_snapshot(snapshot_ref,expected=expected);m=collection['manifest'];receipt=collection['receipt']
    need(setting in ('Agensh-16','Agensh-1')and len(d['roles'])==(16 if setting=='Agensh-16'else 1),'FINAL_SETTING_ROSTER')
    from r16_natural_contract import natural
    nm=natural(d)
    need(nm is not None or d['target_tokens']in (10000000,20000000),'FINAL_ONLY_10M20M')
    need(m['schema']=='count14-agensh-candidates-v1' and m['snapshot_sha256']==snapshot_ref['sha256'] and m['pins']==d['pins'] and m['trajectory']==d['trajectory']and m['generation']==d['generation'],'FINAL_COLLECTION_IDENTITY')
    need(digest(m)==receipt['manifest_sha256']and receipt['snapshot_sha256']==snapshot_ref['sha256'],'FINAL_COLLECTION_SEAL')
    destination=Path(destination);need(destination.is_absolute()and destination.resolve()==destination and not destination.exists(),'ABSENT_FINAL_INPUT_ROOT');destination.mkdir(mode=0o700)
    database=_database(cas,d['shared']['relay_continuation']['archive'],destination/'private-continuations.sqlite')
    native_roles={worker:f'proposal_{i:02d}'for i,worker in enumerate(sorted(d['roles']),1)}
    records,latest,completed_ids=_prior_records(database,d['trajectory'],native_roles)
    # No "idle" assertion can hide a missing settled model response record.
    try:
        ledger_db=sqlite3.connect(cas.resolve(d['durable_ledger']).as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            recorded={role:set()for role in native_roles}
            for rid,role,state,upper,inp,out,receipt_sha in ledger_db.execute('SELECT id,role,state,upper_bound,input,output,receipt_sha FROM requests WHERE trajectory=?',(d['trajectory'],)):
                need(role in recorded,'FINAL_LEDGER_UNRESOLVED')
                if state=='UNKNOWN':_approved_unknown(ledger_db,d['trajectory'],rid,upper,inp,out,receipt_sha)
                else:need(state in ('SETTLED','CANCELLED_UNSENT'),'FINAL_LEDGER_UNRESOLVED')
                if state=='SETTLED':recorded[role].add(rid)
            need(recorded==completed_ids,'FINAL_SETTLED_RESPONSE_RECORDS_MISSING_OR_FOREIGN')
        finally:ledger_db.close()
    except sqlite3.Error:need(False,'FINAL_DURABLE_LEDGER_DATABASE_REFUSED')
    pool={role:{}for role in (*native_roles.values(),'final')};origins={role:[]for role in pool}
    seen=set()
    for row in m['candidates']:
        obj=row['object'];sha(obj['sha256']);need(obj['sha256']not in seen and row['origins'],'FINAL_CANDIDATE_UNIQUE_PROVENANCE');seen.add(obj['sha256']);path=cas.resolve(obj)
        for origin in row['origins']:
            if origin['kind']=='worker':need(origin['origin']in native_roles,'FINAL_CANDIDATE_ROLE');role=native_roles[origin['origin']]
            else:need(origin['kind']=='gitea_ref','FINAL_CANDIDATE_SOURCE_KIND');role='final'
            mt=origin['mtime_ns'];integer(mt,'FINAL_ORIGINAL_MTIME')
            old=pool[role].get(obj['sha256']);pool[role][obj['sha256']]=({'size':obj['size'],'sha256':obj['sha256'],'path':str(path)},max(mt,old[1])if old else mt);origins[role].append({'sha256':obj['sha256'],**origin})
    snapshot=destination/'snapshot';snapshot.mkdir(mode=0o700);census={};aggregate_bytes=0
    role_index=[]
    for worker,native in native_roles.items():role_index.append({'worker':worker,'input_role':native,'record':'/workspace/__finalization_v2/records/'+native+'/saved-private-context.json','has_completed_model_record':latest[worker]is not None})
    for role in pool:
        folder=snapshot/'roles'/role;folder.mkdir(mode=0o700,parents=True)
        worker=next((w for w,r in native_roles.items()if r==role),None)
        context={'source':'ORIGINAL_PERSISTED_AGENSH_RECORDS_NO_SUMMARIZING_MODEL','worker':worker,'latest_original_record':latest[worker]}if worker else{'source':'ADAPTER_INPUT_INDEX_NOT_A_SEARCH_AGENT','role_records':role_index,'shared_git_candidates':len(pool[role]),'no_free_aggregate_search':True}
        raw=wire(context);need(len(raw)<=MAX_FILE,'NATIVE_FINAL_CONTEXT_CAP');publish(folder/'private-context.json',raw,mode=0o400);os.utime(folder/'private-context.json',ns=(META_MTIME,META_MTIME))
        stats=_write_role(folder/'workspace.tar.gz',list(pool[role].values()),records[worker]if worker else[],{'schema':'agensh-native-final-provenance-v1','virtual_input_role':role,'search_worker':worker,'search_agent_created':False,'origins':origins[role]})
        aggregate_bytes+=stats['bytes']+len(raw);need(aggregate_bytes<=MAX_TOTAL,'NATIVE_FINAL_TOTAL_CAP')
        r=hash_file(folder/'workspace.tar.gz');publish(folder/'snapshot-receipt.json',wire({'workspace_archive_sha256':r['sha256'],'workspace_archive_bytes':r['size']}),mode=0o400)
        census[role]={'archive':r,'members':stats['members'],'bytes':stats['bytes'],'context':hash_file(folder/'private-context.json')}
    saved={'setting':setting,'nominal_budget':d['target_tokens'],'actual_search_tokens':d['actual_search_tokens'],'budget_gap':d['shortfall'],'original_snapshot_sha256':snapshot_ref['sha256'],'manifest_sha256':d['pins']['manifest']};publish(snapshot/'saved.json',wire(saved),mode=0o400)
    policy={'schema':'count14-agensh-v21-input-v1','setting':setting,'trajectory':d['trajectory'],'generation':d['generation'],'snapshot_sha256':snapshot_ref['sha256'],'pins':d['pins'],'target_tokens':d['target_tokens'],'roles':census,'saved':hash_file(snapshot/'saved.json'),'worker_to_native_input_role':native_roles,'virtual_final_is_not_search_role':True,'member_cap':max(1,2*max(row['members']for row in census.values())),'K':3,'native_final_executed':False,'no_live_sources':True}
    if nm is not None:policy.update(point_kind='NATURAL_STOP',natural_stop=nm)
    publish(destination/'input-policy.json',wire(policy),mode=0o400)
    return {'snapshot':snapshot,'policy':policy,'input_policy_sha256':digest(policy)}


def verify_input(destination,*,expected_policy_sha,trajectory,setting):
    destination=Path(destination);policy=strict((destination/'input-policy.json').read_bytes())
    need(digest(policy)==sha(expected_policy_sha)and policy['trajectory']==trajectory and policy['setting']==setting,'NATIVE_FINAL_INPUT_POLICY_PIN')
    from r16_natural_contract import natural
    nm=natural(policy)
    need(policy['schema']=='count14-agensh-v21-input-v1'and policy['K']==3 and (nm is not None or policy['target_tokens']in (10000000,20000000)),'NATIVE_FINAL_INPUT_SCOPE')
    if nm is not None:
        saved=strict((destination/'snapshot'/'saved.json').read_bytes())
        need(saved['actual_search_tokens']==saved['nominal_budget']==nm['actual_tokens'] and saved['budget_gap']==0,'NATURAL_SAVED_EXACT_ACTUAL')
    need(set(policy['roles'])=={'final',*(policy['worker_to_native_input_role'].values())},'NATIVE_FINAL_ALL_INPUT_ROLES')
    actual=set(p.name for p in (destination/'snapshot'/'roles').iterdir());need(actual==set(policy['roles']),'NATIVE_FINAL_ALL_INPUT_ROLES')
    need(hash_file(destination/'snapshot'/'saved.json')==policy['saved'],'NATIVE_FINAL_SAVED_ACCOUNTING_CHANGED')
    for role,row in policy['roles'].items():
        folder=destination/'snapshot'/'roles'/role
        need(hash_file(folder/'workspace.tar.gz')==row['archive']and hash_file(folder/'private-context.json')==row['context'],'NATIVE_FINAL_FROZEN_INPUT_CHANGED')
        receipt=strict((folder/'snapshot-receipt.json').read_bytes());need(receipt['workspace_archive_sha256']==row['archive']['sha256'],'NATIVE_FINAL_ROLE_RECEIPT')
    return policy
