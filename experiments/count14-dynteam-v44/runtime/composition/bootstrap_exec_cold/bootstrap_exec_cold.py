"""Future NEW-owner deployment: preserve executable bootstrap overlay mode.

Never modify an existing script, instance, source, class or module global.
Original bootstrap bytes and all scientific/accounting code remain identical.
Not installed in current131/R3; this API alone is not a deployment authority.
"""
from pathlib import Path
from types import FunctionType
import ast,copy,hashlib,inspect,textwrap
PORTS_SHA='4e4409db99d89ea171dfd1874a4e1b261b575d6a5d7f232e24153271b607831f'
ENV_SHA='a4c7d84cd2226372a9e94e978b9f9f21e6957d68f035209484cc1e69507e209b'
OWNER_SHA='22af3bfe52f711ee27bb4e523ed8ab13d375528b05f927afcb64c921095b5ddf'

def need(ok,code):
    if not ok:raise ValueError(code)
def pin(module,expected):
    p=Path(module.__file__)
    need(p.resolve()==p and not p.is_symlink()and hashlib.sha256(p.read_bytes()).hexdigest()==expected,'PROSPECTIVE_EXEC_EXACT_ORIGINAL_SOURCE_BYTES')
def _compile(fn,tree,extras):
    ns={};exec(compile(ast.fix_missing_locations(tree),__file__+':prospective-new-deployment-only','exec'),dict(fn.__globals__,**extras),ns)
    return ns[fn.__name__]

def compiled_bootstrap_overlay():
    import smoke_bootstrap_task_ports as p
    pin(p,PORTS_SHA);fn=p.bootstrap_overlay
    tree=ast.parse(textwrap.dedent(inspect.getsource(fn)));old=copy.deepcopy(tree);changes=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Call)and ast.unparse(node.func)in('os.open','os.fchmod'):
            index=2 if ast.unparse(node.func)=='os.open'else 1
            need(len(node.args)>index and isinstance(node.args[index],ast.Constant)and node.args[index].value==0o444,
                'PROSPECTIVE_EXEC_EXACT_TWO_ORIGINAL_MODE_LITERALS')
            node.args[index].value=0o555;changes.append((ast.unparse(node.func),index))
    need(sorted(changes)==[('os.fchmod',1),('os.open',2)],'PROSPECTIVE_EXEC_TWO_UNIQUE_CREATE_AND_SAME_FD_MODE_SITES')
    inverse=copy.deepcopy(tree)
    for node in ast.walk(inverse):
        if isinstance(node,ast.Call)and ast.unparse(node.func)in('os.open','os.fchmod'):
            node.args[2 if ast.unparse(node.func)=='os.open'else 1].value=0o444
    need(ast.dump(inverse,include_attributes=False)==ast.dump(old,include_attributes=False),'PROSPECTIVE_EXEC_ALL_BOOTSTRAP_BYTES_SOURCE_GUARDS_AND_O_EXCL_UNCHANGED')
    return _compile(fn,tree,{}),dict(mode_sites=2,inverse_AST_equal=True,new_same_FD_create_only=True,original_generated_script_bytes_unchanged=True)

def compiled_environment():
    import native_host_environment as e
    pin(e,ENV_SHA);overlay,proof=compiled_bootstrap_overlay();fn=e.prepare
    tree=ast.parse(textwrap.dedent(inspect.getsource(fn)));old=copy.deepcopy(tree)
    sites=[n for n in ast.walk(tree)if isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='bootstrap_overlay']
    need(len(sites)==1,'PROSPECTIVE_EXEC_ONE_ORIGINAL_HOST_COMPILER_CALL')
    sites[0].func.id='_cold_executable_bootstrap_overlay'
    inverse=copy.deepcopy(tree)
    for n in ast.walk(inverse):
        if isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='_cold_executable_bootstrap_overlay':n.func.id='bootstrap_overlay'
    need(ast.dump(inverse,include_attributes=False)==ast.dump(old,include_attributes=False),'PROSPECTIVE_EXEC_NO_ENV_CREDENTIAL_NETWORK_SCIENCE_DELTA')
    return _compile(fn,tree,dict(_cold_executable_bootstrap_overlay=overlay)),dict(bootstrap=proof,environment_call_sites=1,inverse_AST_equal=True)

def prepare_new_owner(**kwargs):
    import native_cold_owner as n
    pin(n,OWNER_SHA);fn=n.NativeColdOwner.prepare.__func__;environment,_=compiled_environment()
    inspect.signature(fn).bind(n.NativeColdOwner,**kwargs)
    # SAME original constructor code and class; only this private callable's
    # environment compiler input differs. No .prepare or active object patch.
    selected=FunctionType(fn.__code__,dict(fn.__globals__,prepare_environment=environment),fn.__name__,fn.__defaults__,fn.__closure__)
    selected.__kwdefaults__=fn.__kwdefaults__
    need(n.NativeColdOwner.prepare.__func__ is fn,'PROSPECTIVE_EXEC_ORIGINAL_CLASS_METHOD_UNTOUCHED')
    return selected(n.NativeColdOwner,**kwargs)
