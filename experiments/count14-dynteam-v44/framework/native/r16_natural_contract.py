"""Explicit first-natural-stop ABI. Regular search and 10M/20M are unchanged."""
from pathlib import Path
import ast,copy
from common import need,digest,integer,sha,strict
POLICY_SHA='5dddb69c9be2ae5ffd026cba1b15c53cf0cd458734820b8406d020762b13b7d1'
TEMPLATE='[budget] 本团队预算尚余约 {remaining} token。如有改进空间，可以继续完善候选；无需回复本消息。'
TEMPLATE_SHA='55fa7e2fa748fc2492467400e34dca28e3e2d30afdcd81c38cd86c7fca30aac2'
KIND='NATURAL_STOP'
NATURAL_RNG_POLICY={'schema':'r16-first-natural-stop-rng-v1','algorithm':'original SHA256 canonical key/first8 uint32','domain':'AUX_NATURAL_STOP_FINALIZATION','policy_sha256':POLICY_SHA}

def metadata(trajectory,generation,actual):
    integer(generation,'NATURAL_GENERATION',1);integer(actual,'NATURAL_ACTUAL')
    need(actual<20000000,'NATURAL_BEFORE_20M')
    return dict(point_kind=KIND,trajectory=trajectory,generation=generation,actual_tokens=actual,policy_sha256=POLICY_SHA)

def natural(d):
    pins=d.get('pins',{})
    if 'natural_stop_policy' not in pins:
        need('natural_stop_point'not in pins and 'natural_stop'not in d and d.get('point_kind')!=KIND,'NATURAL_AUTHORITY_MISSING')
        return None
    need(pins['natural_stop_policy']==POLICY_SHA,'NATURAL_AUTHORITY_PIN')
    actual=d.get('actual_search_tokens',d.get('natural_stop',{}).get('actual_tokens'))
    meta=metadata(d['trajectory'],d['generation'],actual)
    need(d['target_tokens']==actual and pins.get('natural_stop_point')==digest(meta),'NATURAL_EXACT_ACTUAL_PIN')
    if 'actual_search_tokens'in d:need(d.get('shortfall',0)==0,'NATURAL_NO_NOMINAL_GAP')
    else:need(d.get('point_kind')==KIND and d.get('natural_stop')==meta,'NATURAL_INPUT_KIND')
    return meta

def label(target,meta=None):
    if meta is not None:
        need(meta==metadata(meta['trajectory'],meta['generation'],target),'NATURAL_LABEL_EXACT')
        return 'n'+str(target)+'t'
    need(target in (10000000,20000000),'REGULAR_POINT_ONLY_10M20M')
    return 's'+str(target//1000000)+'m'

def final_rng(seed,action,repeat,meta):
    need(meta==metadata(meta['trajectory'],meta['generation'],meta['actual_tokens']),'NATURAL_RNG_SCOPE')
    integer(seed,'SEARCH_SEED');need(seed<2**32,'SEARCH_SEED');integer(action,'FINAL_ACTION_INDEX')
    need(action<96 and type(repeat)is int and repeat in (1,2,3),'NATURAL_K3_RNG')
    from scientific_profile import SALT
    key=[SALT,seed,'final',NATURAL_RNG_POLICY['domain'],action,meta['actual_tokens'],repeat]
    return {'seed':int(digest(key)[:8],16),'key_sha256':digest(key),'salt':SALT}

def install_exact_label_abi(engine,code,meta):
    """Natural ONLY: one public AST expression changes the old integer-M ABI.
    Original engine FILE, prompt construction, evaluator, metrics and all other
    statements stay intact. Exact n<token>t, never floor/nominal 10M/20M.
    """
    path=Path(code)/'finalization_engine_v1094.py';tree=ast.parse(path.read_text())
    node=next(x for x in tree.body if isinstance(x,ast.FunctionDef)and x.name=='_finalize_checkpoint')
    expected=ast.dump(ast.parse('int(source_label[1:-1])*1_000_000',mode='eval').body,include_attributes=False)
    count=0
    class Exact(ast.NodeTransformer):
        def visit_BinOp(self,node):
            nonlocal count
            if ast.dump(node,include_attributes=False)==expected:
                count+=1
                return ast.copy_location(ast.Call(func=ast.Name(id='_agensh_natural_checkpoint_tokens',ctx=ast.Load()),args=[ast.Name(id='source_label',ctx=ast.Load())],keywords=[]),node)
            return self.generic_visit(node)
    node=Exact().visit(copy.deepcopy(node));need(count==1,'NATURAL_ONE_EXACT_LABEL_ABI')
    wanted=label(meta['actual_tokens'],meta)
    def checkpoint(text):
        need(text==wanted,'NATURAL_ENGINE_EXACT_LABEL');return meta['actual_tokens']
    space=dict(engine._finalize_checkpoint.__globals__);space['_agensh_natural_checkpoint_tokens']=checkpoint
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(path),'exec'),space)
    engine._finalize_checkpoint=space['_finalize_checkpoint']


def natural_binding(binding):
    if binding.get('point_kind')!='NATURAL_STOP':
        need('natural_stop'not in binding and 'natural_stop_rng_policy_sha256'not in binding,'NATURAL_BINDING_KIND')
        return None
    meta=binding.get('natural_stop');need(type(meta)is dict,'NATURAL_BINDING_METADATA')
    need(meta==metadata(binding['trajectory'],meta.get('generation'),binding['target_tokens'])
         and binding.get('natural_stop_rng_policy_sha256')==digest(NATURAL_RNG_POLICY),'NATURAL_BINDING_AUTHORITY')
    return meta
