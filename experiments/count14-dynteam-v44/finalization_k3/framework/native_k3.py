"""Independent Agensh K3 audit around exact original graph/metric/mean functions.

Only native metadata (never candidate/result body text) is opened here. This is a
trusted FINAL-side component; its output must never be routed back to search.
A generic JSON report cannot qualify a K: all raw14-task cells, native reservation
books, separate ledgers, request IDs, and physical-custody attestations are checked.
"""
from pathlib import Path
import ast,hashlib,json,statistics
from common import need,integer,sha,wire,digest,strict,hash_file,publish,ident
import native_evaluation_consistency as consistency
METRICS=('unique_candidates','correct_candidates','successful_tasks','maximum_one_to_one_matches')

def original_functions():
    base=Path(__file__).resolve().parent;origin=strict((base/'NATIVE_K3_ORIGIN.json').read_bytes())
    need(hash_file(base/'native_evaluation_consistency.py')['sha256']==origin['evaluation_consistency_sha256'],'FINAL_NATIVE_MATRIX_READER_CHANGED')
    text=(base/'native_k3_original.py').read_text();nodes=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)]
    pins={n.name:hashlib.sha256(ast.get_source_segment(text,n).encode()).hexdigest()for n in nodes};need(pins==origin['functions'],'FINAL_NATIVE_AGGREGATION_CHANGED')
    space=dict(index=consistency.index,cell=consistency.cell,MetadataError=consistency.MetadataError,pathlib=__import__('pathlib'),statistics=statistics,METRICS=METRICS)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(base/'native_k3_original.py'),'exec'),space)
    return space

def _inside(root,path):
    p=Path(path);need(p.is_absolute()and p.resolve()==p and p.is_relative_to(root),'FINAL_METADATA_OUTSIDE_AUX_ROOT');return p

def _read(path):
    need(not Path(path).is_symlink(),'FINAL_LINKED_METADATA');return strict(Path(path).read_bytes())

def audit_three(aux_root,runs,*,trajectory,setting,target_tokens,source_sha256,protocol_sha256,input_policy_sha256,natural_stop=None):
    root=Path(aux_root);need(root.is_absolute()and root.resolve()==root,'FINAL_AUX_CANONICAL_ROOT')
    from r16_natural_contract import metadata,label as point_label
    if natural_stop is not None:need(natural_stop==metadata(trajectory,natural_stop['generation'],target_tokens),'FINAL_NATURAL_EXACT_SCOPE')
    need(setting in ('Agensh-16','Agensh-1')and type(target_tokens)is int and (natural_stop is not None or target_tokens in (10000000,20000000)),'FINAL_EXACT_SCIENCE_SCOPE')
    for v in (source_sha256,protocol_sha256,input_policy_sha256):sha(v)
    need(type(runs)is list and len(runs)==3,'FINAL_EXACT_K3');native=original_functions();records=[];graphs=[];task_map={};used_ids=set();evidence=[]
    for k,paths in enumerate(runs,1):
        need(set(paths) in ({'branch','aggregate','matrix','custody'},{'branch','aggregate','matrix','custody','attempt'}),'FINAL_AUDIT_PATH_FIELDS')
        attempt=paths.get('attempt',1);need(type(attempt)is int and 1<=attempt<=3,'FINAL_K_ATTEMPT')
        runroot=root if attempt==1 else root/'replacement-attempts'/f'k{k}-a{attempt}'
        branch=_inside(root,paths['branch']);need(branch==runroot/f'k{k}','FINAL_INDEPENDENT_K_BRANCH')
        aggregate=_inside(root,paths['aggregate']);matrix=_inside(root,paths['matrix']);custody_path=_inside(root,paths['custody'])
        label=point_label(target_tokens,natural_stop)+f'-k{k}'
        need(matrix==runroot/'evaluator-private'/setting/label and aggregate==runroot/'results'/setting/label/'aggregate.json'and custody_path==branch/'physical-custody.json','FINAL_K_OUTPUT_PATHS')
        r=_read(aggregate);custody=_read(custody_path);ledger=_read(branch/'ledger.json')
        if attempt>1:
            key={'trajectory':trajectory,'target':target_tokens}
            if natural_stop is not None:key.update(point_kind='NATURAL_STOP',policy_sha256=natural_stop['policy_sha256'])
            need(r.get('replicate_attempt')==custody.get('replicate_attempt')==attempt and r.get('point_id')==custody.get('point_id')==digest(key),'FINAL_REPLACEMENT_REPORT_SCOPE')
        if natural_stop is not None:need(r.get('point_kind')=='NATURAL_STOP' and r.get('natural_stop')==natural_stop,'FINAL_NATURAL_REPORT_SCOPE')
        need(r.get('trajectory')==trajectory and r.get('setting')==setting and type(r.get('replicate_index'))is int and r['replicate_index']==k and r.get('nominal_budget')==target_tokens and r.get('input_policy_sha256')==input_policy_sha256,'FINAL_K_IDENTITY')
        need(r.get('source_sha256')==source_sha256 and r.get('protocol_sha256')==protocol_sha256,'FINAL_K_SOURCE_PROTOCOL')
        for key in ('initial_input_sha256','frozen_catalog_sha256'):sha(r.get(key))
        need(r.get('complete')is True and r.get('evaluation_complete')is True and r.get('unknown_requests')==0,'FINAL_PARTIAL_NOT_ZERO')
        need(custody.get('schema')=='count14-agensh-final-physical-custody-v1'and custody.get('trajectory')==trajectory and custody.get('replicate_index')==k and custody.get('target_tokens')==target_tokens and custody.get('input_policy_sha256')==input_policy_sha256 and custody.get('native_model_and_evaluator_scopes_terminal')is True and type(custody.get('unresolved'))is int and custody['unresolved']==0,'FINAL_PHYSICAL_CUSTODY_REQUIRED')
        need(custody.get('aggregate_sha256')==hash_file(aggregate)['sha256'],'FINAL_CUSTODY_WRONG_RESULT')
        requests=ledger.get('requests');need(type(requests)is dict and ledger.get('setting')=='single','FINAL_ORIGINAL_AUX_LEDGER_ABI')
        # 'single' is the original engine's AUX ledger role ABI, never a fake
        # Agensh scientific setting/search-role registration.
        need(type(ledger.get('actual_tokens'))is int and ledger['actual_tokens']>=0 and ledger.get('unknown_requests')==0 and ledger.get('model_calls')==len(requests)and r.get('finalization_model_calls')==len(requests),'FINAL_NATIVE_LEDGER_UNSETTLED')
        tokens=0;charged=0
        for rid,row in requests.items():
            ident(rid)
            need(rid not in used_ids,'FINAL_K_REUSED_REQUEST_ID');used_ids.add(rid)
            need(row.get('role')=='single'and row.get('state')in ('COMPLETED','UNKNOWN_CHARGED','REJECTED_PREGEN','RETRYABLE_REJECTED'),'FINAL_NATIVE_REQUEST_UNSETTLED')
            integer(row.get('tokens'),'FINAL_NATIVE_REQUEST_TOKENS');tokens+=row['tokens']
            if row['state']=='UNKNOWN_CHARGED':charged+=row['tokens']
            if row['state']in ('REJECTED_PREGEN','RETRYABLE_REJECTED'):need(row['tokens']==0,'FINAL_REJECT_MUST_NOT_CHARGE')
            directory=branch/'requests'/rid
            terminal=_read(_inside(root,directory/'receipt-terminal.json'));sent=_read(_inside(root,directory/'receipt-sent.json'))
            need(sent.get('request_id')==terminal.get('request_id')==rid and sent.get('state')=='SENT'and terminal.get('state')==row['state']and sent.get('accounting')==terminal.get('accounting')=='excluded-checkpoint-finalization','FINAL_NATIVE_RECEIPT_IDENTITY')
            request_hash=hash_file(_inside(root,directory/'request.json'))['sha256']
            need(sent.get('request_sha256')==terminal.get('request_sha256')==request_hash,'FINAL_NATIVE_REQUEST_FILE_CHANGED')
            if row['state']=='COMPLETED':
                usage=terminal.get('usage');need(type(usage)is dict,'FINAL_NATIVE_USAGE_RECEIPT')
                integer(usage.get('prompt_tokens'),'FINAL_NATIVE_USAGE_RECEIPT');integer(usage.get('completion_tokens'),'FINAL_NATIVE_USAGE_RECEIPT')
                need(usage['prompt_tokens']+usage['completion_tokens']==row['tokens']and terminal.get('response_sha256')==hash_file(_inside(root,directory/'response.json'))['sha256'],'FINAL_NATIVE_RESPONSE_RECEIPT_CHANGED')
            else:need(terminal.get('usage_reported')is False and terminal.get('charged_tokens')==row['tokens']and terminal.get('possible_server_execution')is (row['state']=='UNKNOWN_CHARGED'),'FINAL_NATIVE_CLASSIFICATION_RECEIPT')
        requests_home=branch/'requests'
        if requests_home.exists():
            for directory in requests_home.iterdir():
                _inside(root,directory)
                if directory.name not in requests:need(not(directory/'receipt-sent.json').exists(),'FINAL_ORPHAN_SENT_REQUEST')
        need(tokens==ledger['actual_tokens']==r.get('finalization_tokens')and r.get('finalization_reported_tokens')==tokens-charged and r.get('finalization_conservatively_charged_tokens')==charged,'FINAL_NATIVE_COST_MISMATCH')
        book=branch/'ledger.json.reservations-v52.json'
        if book.exists():
            reservation=_read(book);need(reservation.get('schema')==1 and reservation.get('active')=={} and reservation.get('halted')is False,'FINAL_NATIVE_ACTIVE_RESERVATION')
        else:need(not requests and tokens==0,'FINAL_NATIVE_RESERVATION_BOOK_MISSING')
        graph,tasks=native['graph'](matrix)
        for task,identity in tasks.items():need(task not in task_map or task_map[task]==identity,'FINAL_K_TASK_ORDER_CHANGED');task_map[task]=identity
        actual=native['metrics'](graph)
        need(all(type(r.get(m))is int and r[m]>=0 for m in METRICS)and actual=={m:r[m]for m in METRICS},'FINAL_NATIVE_REPORT_MATRIX_MISMATCH')
        records.append(r);graphs.append(graph)
        evidence.append({'replicate_index':k,'replicate_attempt':attempt,'aggregate':hash_file(aggregate),'ledger':hash_file(branch/'ledger.json'),'custody':hash_file(custody_path)})
    value=native['aggregate_runs'](records,graphs)
    value.update(schema='count14-agensh-v21-k3-summary-v1',trajectory=trajectory,setting=setting,nominal_budget=target_tokens,input_policy_sha256=input_policy_sha256,source_sha256=source_sha256,protocol_sha256=protocol_sha256,initial_input_sha256=records[0]['initial_input_sha256'],frozen_catalog_sha256=records[0]['frozen_catalog_sha256'],complete=True,evaluation_complete=True,replicates_complete=3,evidence=evidence,billing_domain='AUX_FINALIZATION',search_feedback=False)
    if natural_stop is not None:value.update(point_kind='NATURAL_STOP',natural_stop=natural_stop,report_label='自然停止点 @ 实际 token')
    return value

def publish_summary(aux_root,runs,**scope):
    value=audit_three(aux_root,runs,**scope);publish(Path(aux_root)/'k3-summary.json',wire(value),mode=0o400);return value
