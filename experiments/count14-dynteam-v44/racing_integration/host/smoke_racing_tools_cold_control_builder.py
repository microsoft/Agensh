"""Cold-only original ACP control hooks and exact END admission seam.

Each generated overlay has an inverse-AST equality check. Original protocol
lines, prompt/tool bodies, commands, results and forwarded byte arrays are not
modified, serialized to metadata, logged or re-sent by these hooks.
"""
import ast
import copy
from pathlib import Path


def _same(before,after,code):
    if ast.dump(before,include_attributes=False)!=ast.dump(after,include_attributes=False):
        raise ValueError(code)


def _render(tree,name):
    tree=ast.fix_missing_locations(tree);text=ast.unparse(tree)+'\n';compile(text,name,'exec');return text


def end_admission_delta(raw):
    before=ast.parse(raw);tree=copy.deepcopy(before)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeBridgeLifecycleOwner')
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='handle')
    branches=[n for n in fn.body if isinstance(n,ast.If) and ast.dump(n.test)==ast.dump(ast.parse("event == 'END_REQUEST'",mode='eval').body)]
    if len(branches)!=1:raise ValueError('DYNTEAM_ONE_ORIGINAL_END_REQUEST_BRANCH')
    branch=branches[0];old=copy.deepcopy(branch.body)
    expected=ast.parse("""
if cli['end_lease'] is None:
    lease=self.core.membership_fences[t].acquire(role,'NATIVE_END')
    if lease is None:return False
    cli['end_lease']=lease
self.core.roles.hold_end(t,role,anonymous)
return self._clear(key)
""").body
    _same(ast.Module(body=old,type_ignores=[]),ast.Module(body=expected,type_ignores=[]),
          'DYNTEAM_EXACT_ORIGINAL_END_ADMISSION_BODY')
    branch.body=ast.parse("""
self.core.roles.hold_end(t,role,anonymous)
if not self._clear(key):return False
if cli['end_lease'] is None:
    lease=self.core.membership_fences[t].acquire(role,'NATIVE_END')
    if lease is None:return False
    cli['end_lease']=lease
return True
""").body
    rendered=_render(tree,'count14-end-admission.py')
    branch.body=old;_same(before,tree,'DYNTEAM_END_ADMISSION_NO_OTHER_AST_CHANGE')
    return rendered


def bridge_stream_delta(raw):
    before=ast.parse(raw);tree=copy.deepcopy(before)
    server=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='serve_connection')
    edits=[]
    for name,direction in (('observe_requests','input'),('observe_responses','output')):
        fn=next(n for n in server.body if isinstance(n,ast.FunctionDef) and n.name==name)
        hook=ast.parse("_count14_lifecycle.observe_control(proc, lines, "+repr(direction)+")").body[0]
        if any(isinstance(n,ast.Expr) and ast.dump(n)==ast.dump(hook) for n in fn.body):
            raise ValueError('DYNTEAM_NATIVE_CONTROL_STREAM_HOOK_ONLY_ONCE')
        fn.body.insert(0,hook);edits.append((fn,hook))
    result=_render(tree,'count14-native-acp-control.py')
    for fn,hook in edits:fn.body.remove(hook)
    _same(before,tree,'DYNTEAM_NATIVE_STREAM_BODY_AND_BYTE_FORWARDING_AST_UNCHANGED')
    return result


def _observer_nodes():
    source=Path(__file__).with_name('smoke_racing_tools_native_control.py').read_text()
    tree=ast.parse(source)
    # Native client already imports json/threading. Use the reviewed exact
    # observer class; no runtime source/body is read by this cold compiler.
    return [copy.deepcopy(n) for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) or
            isinstance(n,ast.Assign)]


def bridge_client_delta(raw):
    before=ast.parse(raw);tree=copy.deepcopy(before)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='BridgeLifecycle')
    born=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='born')
    row=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_row')
    context=next(n for n in born.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='context' for t in n.targets))
    hook=ast.parse("context['control_observer'] = NativeToolControlObserver()").body[0]
    born.body.insert(born.body.index(context)+1,hook)
    ret=next(n for n in row.body if isinstance(n,ast.Return));call=ret.value
    if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name) or call.func.id!='dict':
        raise ValueError('DYNTEAM_ORIGINAL_BRIDGE_TYPED_CONTROL_ROW')
    kw=ast.keyword(arg='tool_control',value=ast.parse("context['control_observer'].snapshot() if 'control_observer' in context else None",mode='eval').body)
    call.keywords.append(kw)
    method=ast.parse("""
def observe_control(self,proc,lines,direction):
    with self.lock:
        context=self.children.get(proc.pid)
    if context is None or 'control_observer' not in context:
        raise ValueError('DYNTEAM_NATIVE_CONTROL_OBSERVER_INSTALLED_BEFORE_INPUT')
    context['control_observer'].observe(lines,direction)
""").body[0]
    cls.body.append(method)
    added=_observer_nodes()
    at=tree.body.index(cls);tree.body[at:at]=added
    result=_render(tree,'count14-native-bridge-control-client.py')
    born.body.remove(hook);call.keywords.remove(kw);cls.body.remove(method)
    for n in added:tree.body.remove(n)
    _same(before,tree,'DYNTEAM_NATIVE_CONTROL_CLIENT_NO_OTHER_AST_CHANGE')
    return result


def bridge_protocol_delta(raw):
    before=ast.parse(raw);tree=copy.deepcopy(before)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='checked_lifecycle')
    compare=[n for n in ast.walk(fn) if isinstance(n,ast.Compare) and
             ast.dump(n)==ast.dump(ast.parse('set(row) == FIELDS',mode='eval').body)]
    if len(compare)!=1:raise ValueError('DYNTEAM_ONE_ORIGINAL_PROTOCOL_FIELD_GUARD')
    target=compare[0];old=copy.deepcopy(target)
    target.ops=[ast.In()];target.comparators=[ast.parse("(FIELDS, FIELDS | {'tool_control'})",mode='eval').body]
    extra=ast.parse("""
if 'tool_control' in row and row['tool_control'] is not None:
    _count14_checked_tool_control(row['tool_control'])
""").body[0]
    at=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Return));fn.body.insert(at,extra)
    nodes=_observer_nodes();consts=[n for n in nodes if isinstance(n,ast.Assign)]
    checker=next(n for n in nodes if isinstance(n,ast.FunctionDef) and n.name=='checked_control')
    class Rename(ast.NodeTransformer):
        def visit_Name(self,n):
            if n.id in ('SCHEMA','FIELDS'):n.id='_COUNT14_CONTROL_'+n.id
            return n
    consts=[Rename().visit(n) for n in consts];checker=Rename().visit(checker);checker.name='_count14_checked_tool_control'
    added=consts+[checker];at=tree.body.index(fn);tree.body[at:at]=added
    result=_render(tree,'count14-native-bridge-control-protocol.py')
    target.ops=old.ops;target.comparators=old.comparators;fn.body.remove(extra)
    for n in added:tree.body.remove(n)
    _same(before,tree,'DYNTEAM_NATIVE_CONTROL_PROTOCOL_NO_OTHER_AST_CHANGE')
    return result


def consume_control_snapshot(custody,t,role,child,value):
    """Owner hook only AFTER exact bridge peer/current CLI token validation."""
    from smoke_racing_tools_native_control import checked_control
    from native_peer_registry import ProcessBirth
    if value is None:return False
    checked_control(value)
    if type(child) is not ProcessBirth or custody.core is None:
        raise ValueError('DYNTEAM_NATIVE_CONTROL_EXACT_OWN_CHILD_BINDING')
    key=t,role
    if not hasattr(custody,'native_control_snapshots'):custody.native_control_snapshots={}
    old=custody.native_control_snapshots.get(key)
    if old is not None and old['child']==child:
        if value['sequence']<old['value']['sequence'] or (
                value['sequence']==old['value']['sequence'] and value!=old['value']):
            raise ValueError('DYNTEAM_NATIVE_CONTROL_NO_STALE_OR_CONFLICTING_SNAPSHOT')
    custody.native_control_snapshots[key]={'child':child,'value':dict(value)}
    return True


def control_snapshot_clear(custody,t,role,child):
    row=getattr(custody,'native_control_snapshots',{}).get((t,role))
    return bool(row is not None and row['child']==child and row['value']['control_complete'] is True and
                row['value']['observer_fault'] is False and row['value']['pending_prompts']==0 and
                row['value']['pending_tools']==0)
