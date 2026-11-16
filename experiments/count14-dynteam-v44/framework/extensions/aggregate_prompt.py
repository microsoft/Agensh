"""Pure AST extraction: never import campaign (would activate pilot bindings)."""
import ast,hashlib
from pathlib import Path
from common import need,digest
PILOT_SHA='b81b0ea52a8edc8e0bc927261352fddf5a090b47c5cbb1d543b771061fd3f5f7'
def render(path):
 raw=Path(path).read_bytes();need(hashlib.sha256(raw).hexdigest()==PILOT_SHA,'AGGREGATE_PILOT_SOURCE_PIN')
 tree=ast.parse(raw);role=next(x for x in tree.body if isinstance(x,ast.ClassDef)and x.name=='Role')
 fn=next(x for x in role.body if isinstance(x,ast.FunctionDef)and x.name=='prompt')
 common=next(ast.literal_eval(x.value)for x in fn.body if isinstance(x,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='common'for t in x.targets))
 behavior=next(ast.literal_eval(x.value.orelse)for x in fn.body if isinstance(x,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='behavior'for t in x.targets))
 ret=fn.body[-1];need(isinstance(ret,ast.Return),'AGGREGATE_PROMPT_RETURN')
 ns={'common':common,'behavior':behavior};text=eval(compile(ast.Expression(ret.value),'pilot-aggregate-expression','eval'),{'__builtins__':{}},ns)
 need(text==common+text[len(common):] and '/workspace/proposals/round-XXXX' in text,'AGGREGATE_ORIGINAL_COMMON_AND_HANDOFF')
 mapped=text.replace('/workspace','/work')
 return mapped,{'schema':'agensh-late-aggregate-prompt-v1','pilot_campaign_sha256':PILOT_SHA,
  'original_utf8_sha256':hashlib.sha256(text.encode()).hexdigest(),'rendered_utf8_sha256':hashlib.sha256(mapped.encode()).hexdigest(),
  'mapping':{'/workspace':'/work'},'branch':'aggregate-not-select','common_bytes':len(common.encode()),
  'same_all_six':True,'additional_instructions':False}
