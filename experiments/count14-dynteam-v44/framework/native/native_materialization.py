"""Explicit independent-domain binding for original mtime-fixed materializer.

Only its two pilot infrastructure lookups are replaced by a verified independent
Agensh input policy/scope. The original ordinary/link/path/type/copy/mtime/count
checks execute unchanged. No fake pilot manifest, mutable monkeypatch of shared
runtime, source lookup, network, or hidden evaluation occurs here.
"""
from pathlib import Path,PurePosixPath
from decimal import Decimal
import ast,copy,hashlib,json,os,shutil,tarfile
from common import need,sha
from native_inert_archive import Header,special_kind
from v21_inputs import verify_input

class NativeMaterializer:
    def __init__(self,input_root,auxiliary_root,*,policy_sha,trajectory,setting):
        self.input_root=Path(input_root);self.auxiliary_root=Path(auxiliary_root);self.policy_sha=sha(policy_sha);self.trajectory=trajectory;self.setting=setting
        for p in (self.input_root,self.auxiliary_root):need(p.is_absolute()and p.resolve()==p,'NATIVE_MATERIALIZATION_CANONICAL_ROOT')
        need(not(self.auxiliary_root.is_relative_to(self.input_root)or self.input_root.is_relative_to(self.auxiliary_root)),'NATIVE_FINAL_WRITABLE_ROOT_SEPARATE')
        base=Path(__file__).resolve().parent;origin=json.loads((base/'NATIVE_TERMINAL_ORIGIN.json').read_bytes());text=(base/'native_terminal_original.py').read_text();tree=ast.parse(text)
        original=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='materialize_terminal')
        need(hashlib.sha256(ast.get_source_segment(text,original).encode()).hexdigest()==origin['function_source_sha256'],'NATIVE_TERMINAL_BODY_PIN')
        node=copy.deepcopy(original);changed=0
        for i,statement in enumerate(node.body):
            if isinstance(statement,ast.Assign)and any(isinstance(t,ast.Tuple)for t in statement.targets)and isinstance(statement.value,ast.Call)and isinstance(statement.value.func,ast.Name)and statement.value.func.id=='load_binding':
                # Assignment and following setting guard were one physical source
                # line but separate AST statements. Preserve the guard by giving
                # it the exact verified independent setting, not a legacy row.
                node.body[i]=ast.parse("row={'setting':setting}").body[0];changed+=1
            if isinstance(statement,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='policy'for t in statement.targets):
                node.body[i]=ast.parse('policy=verified_scope(snapshot,workspace,setting)').body[0];changed+=1
        need(changed==2,'NATIVE_TERMINAL_INFRASTRUCTURE_SHAPE_CHANGED');ast.fix_missing_locations(node)
        namespace={'need':need,'Path':Path,'PurePosixPath':PurePosixPath,'Decimal':Decimal,'os':os,'tarfile':tarfile,'shutil':shutil,'Header':Header,'special_kind':special_kind,'verified_scope':self.scope}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(base/'native_terminal_original.py'),'exec'),namespace)
        self.function=namespace['materialize_terminal'];self.function_source_sha256=origin['function_source_sha256']
    def scope(self,snapshot,workspace,setting):
        p=verify_input(self.input_root,expected_policy_sha=self.policy_sha,trajectory=self.trajectory,setting=setting)
        snapshot=Path(snapshot);workspace=Path(workspace)
        need(setting==self.setting and snapshot==self.input_root/'snapshot'and workspace.resolve()==workspace,'NATIVE_MATERIALIZATION_IDENTITY')
        allowed={self.auxiliary_root/f'k{k}'/'workspace'for k in (1,2,3)};need(workspace in allowed,'NATIVE_MATERIALIZATION_BRANCH')
        return {'member_cap':p['member_cap'],'roles':{r:{'counts':{'members':v['members']}}for r,v in p['roles'].items()}}
    def materialize_terminal(self,snapshot,workspace,setting):return self.function(snapshot,workspace,setting)
