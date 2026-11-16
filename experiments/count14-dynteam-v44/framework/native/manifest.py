"""Independent Agensh schema/compiler, deliberately not a legacy moa setting."""
from common import need,ident,integer,sha,wire,digest
from pathlib import Path
SCHEMA='count14-agensh-manifest-v1'
# This profile is the user-approved paired comparison, not a generic seed generator.
BASELINE_SEEDS=(4287909351,1636023914,2619738241)
REQUIRED_PINS=frozenset(('agensh_commit_tree','cli','image','relay','bridge','collector','source_bundle','task_description','collaboration_prompt','model_configuration','rng_policy','billing_mapping','final_v21','evaluator'))

def validate(m):
    need(type(m)is dict and set(m)=={'schema','experiment_id','revision','root','owner','protocol','settings','blocks','budget','scheduling','restore'},'MANIFEST_FIELDS')
    need(m['schema']==SCHEMA,'MANIFEST_SCHEMA');ident(m['experiment_id']);ident(m['owner']);integer(m['revision'],'REVISION',1)
    p=Path(m['root']);need(p.is_absolute() and str(p)==str(p.resolve()),'EXPERIMENT_ROOT')
    need(type(m['protocol'])is dict and set(m['protocol'])==REQUIRED_PINS,'PROTOCOL_PINS')
    for v in m['protocol'].values():sha(v)
    need(type(m['settings'])is list and len(m['settings'])==2,'TWO_SETTINGS')
    for s,n in zip(m['settings'],(16,1)):
        need(type(s)is dict,'SETTING_FIELDS');integer(s.get('workers'),'WORKERS',1)
        need(s=={'id':f'Agensh-{n}','family':'agensh','workers':n,'path':'team','process_feedback':'disabled'},'AGENT_ROSTER_NO_HIDDEN_COORDINATOR')
    need(type(m['blocks'])is list and len(m['blocks'])==3,'THREE_BLOCKS')
    for b,n in zip(m['blocks'],(1,2,3)):
        need(type(b)is dict and set(b)=={'block','seed'} and type(b['block'])is int and b['block']==n,'BLOCK_ORDER')
        integer(b['seed'],'SEARCH_SEED');need(b['seed']<2**32,'SEARCH_SEED')
        need(b['seed']==BASELINE_SEEDS[n-1],'PAIRED_BASELINE_SEED')
    need(len({b['seed'] for b in m['blocks']})==3,'DISTINCT_SEEDS')
    b=m['budget'];need(type(b)is dict,'BUDGET_FIELDS')
    for k in ('search_tokens','feedback_charge','K'):integer(b.get(k),k)
    need(type(b.get('checkpoints'))is list,'CHECKPOINTS')
    for v in b['checkpoints']:integer(v,'CHECKPOINT',1)
    need(m['budget']=={'search_tokens':20000000,'checkpoints':[10000000,20000000],'feedback_charge':0,'barrier_policy':'no_overshoot_reserve_then_drain','finalization_protocol':'v2.1','K':3},'USER_1026_10M20M_K3')
    s=m['scheduling'];need(type(s)is dict and set(s)=={'global_gateway_cap','search_cap','auxiliary_cap','final_global_cap','memory_reserve_GiB'},'SCHEDULING')
    for k,v in s.items():integer(v,k,1)
    need(s['search_cap']+s['auxiliary_cap']<=s['global_gateway_cap']<=96 and s['final_global_cap']<=12 and s['memory_reserve_GiB']>=64,'SHARED_CAPACITY')
    need(type(m['restore'])is dict and type(m['restore'].get('cold_continuation_supported'))is bool and type(m['restore'].get('live_stage_resume'))is bool,'RESTORE_TYPES')
    need(m['restore']=={'level':'L1','cold_continuation_supported':False,'live_stage_resume':True},'DO_NOT_INFER_L2')
    return m

def compile_manifest(m):
    validate(m);h=digest(m);out=[]
    for b in m['blocks']:
        for s in m['settings']:
            trajectory=f"{m['experiment_id']}/{s['id']}/block-{b['block']}/seed-{b['seed']}"
            out.append({'trajectory_id':trajectory,'manifest_sha256':h,'setting':s['id'],'block':b['block'],'seed':b['seed'],'roles':[f'worker-{i:02d}' for i in range(s['workers'])],'root':str(Path(m['root'])/s['id']/f"block-{b['block']}"),'checkpoints':list(m['budget']['checkpoints']),'K':3})
    return {'schema':'count14-agensh-compiled-v1','manifest_sha256':h,'trajectories':out}
