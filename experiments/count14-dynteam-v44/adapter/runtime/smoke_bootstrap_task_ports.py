"""Minimal SAME-root first-start ports; no model dispatch, replay or new owner.

Runtime may consume approved task bytes and its NEW infrastructure credentials.
DEV only invokes OWN fixtures. Old native modules and their globals are unedited.
"""
from pathlib import Path
from types import MethodType
import ast
import copy
import datetime
import hashlib
import http.client
import inspect
import json
import os
import re
import stat
import textwrap
import urllib.parse

from common import need,digest,hash_file
import native_scientific_bootstrap as original_selector
import native_gitea as original_gitea
from native_gitea import NativeGitea,GiteaBinding
from native_beta_layout import native_aliases
from native_hostpub_prepublication import publication_hostpub_ready, WAITING

BETA_BOOTSTRAP_SHA='5038b07526911b25a1e03d16731cc990edb004009b2f8f5240c0665fec4f323a'
SELECTOR_MODULE_SHA='2fadaec6b49a870db71249312e4d56537b806ec1f215c2f150bb774b6315f569'
GITEA_MODULE_SHA='2bcba395821551195a65d0e3b2532fab2f782d6001b2c9af4e5d2d7e3854c52e'
TASK_HOST_SHA='2cb144cdb2b7aeedff8c804d90222e2ccabb6820ee4f462436911197e38776f4'


def scientific_bootstrap(source):
    """Only a private copy's source SHA changes; selector code is original."""
    need(hash_file(Path(original_selector.__file__).resolve())['sha256']==SELECTOR_MODULE_SHA,
         'DYNTEAM_ORIGINAL_TRUSTED_PUBLISHER_SELECTOR_PIN')
    fn=original_selector.build_scientific_bootstrap
    scope=dict(fn.__globals__);scope['V2_SHA256']=BETA_BOOTSTRAP_SHA
    clone=type(fn)(fn.__code__,scope,fn.__name__,fn.__defaults__,fn.__closure__)
    before=original_selector.V2_SHA256
    result=clone(source)
    need(original_selector.V2_SHA256==before and clone.__code__ is fn.__code__,
         'DYNTEAM_BOOTSTRAP_SELECTOR_ONLY_PRIVATE_INPUT_PIN_DELTA')
    return result


def bootstrap_overlay(source,*,destination):
    """Compile prior to Docker UP; exact bootstrap service only, never science."""
    path=Path(destination)
    need(path.is_absolute() and path.parent.resolve()==path.parent and not path.exists(),
         'DYNTEAM_BOOTSTRAP_NEW_COLD_SCRIPT_ONLY')
    raw=scientific_bootstrap(source)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
    try:
        with os.fdopen(fd,'wb',closefd=False) as out:out.write(raw);out.flush();os.fsync(fd)
        os.fchmod(fd,0o444)
    finally:os.close(fd)
    return {'services':{'bootstrap':{'environment':{'COUNT14_REPOSITORY_OWNER':'trusted-publisher'},
        'volumes':[str(path)+':/usr/local/bin/bootstrap.sh:ro']}}}


def source_only_publication(publisher,bootstrap_root,receipt_pin,*,registered_roles):
    """Original Gitea publication with one exact source-only roster selector.

    No account role/schema/budget mutation. Receipt has zero eager clones; the
    ledger must retain the exact full approved native role catalogue. Every
    API/push/protection/operation/UNKNOWN path executes original code unchanged.
    """
    need(type(publisher) is NativeGitea and type(registered_roles) in (tuple,list) and
         len(registered_roles)>0 and len(set(registered_roles))==len(registered_roles),
         'DYNTEAM_ORIGINAL_PUBLISHER_AND_EXACT_REGISTERED_ROSTER_REQUIRED')
    need(hash_file(Path(original_gitea.__file__).resolve())['sha256']==GITEA_MODULE_SHA,
         'DYNTEAM_ORIGINAL_GITEA_PUBLICATION_PIN')
    text=textwrap.dedent(inspect.getsource(NativeGitea.publication));tree=ast.parse(text);prior=copy.deepcopy(tree)
    guards=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='need'
        and len(n.args)>1 and isinstance(n.args[1],ast.Constant) and n.args[1].value=='GITEA_BOOTSTRAP_ROSTER_BINDING']
    need(len(guards)==1,'DYNTEAM_ONE_ORIGINAL_GITEA_ROSTER_GUARD')
    original_guard=copy.deepcopy(guards[0].args[0])
    guards[0].args[0]=ast.parse("receipt.get('roles') == [] and tuple(json.loads(account['roles'])) == _dynteam_registered_roles",mode='eval').body
    reverted=copy.deepcopy(tree)
    n=next(n for n in ast.walk(reverted) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='need'
        and len(n.args)>1 and isinstance(n.args[1],ast.Constant) and n.args[1].value=='GITEA_BOOTSTRAP_ROSTER_BINDING')
    n.args[0]=original_guard
    need(ast.dump(reverted,include_attributes=False)==ast.dump(prior,include_attributes=False),
         'DYNTEAM_NO_GITEA_API_PUSH_PROTECTION_LEDGER_OR_RETRY_DELTA')
    scope=dict(NativeGitea.publication.__globals__,_dynteam_registered_roles=tuple(registered_roles))
    exec(compile(ast.fix_missing_locations(tree),__file__+':source_only_gitea','exec'),scope)
    return scope['publication'](publisher,bootstrap_root,receipt_pin)


def original_task_ports(source,*,native_beta_dm=False):
    """Extract exact original task/channel/API functions without host side effects.

    Avoid importing old deployment config/guard or using its system Docker. The
    six function ASTs below are byte-original; globals contain only standard
    infrastructure helpers and the explicit NEW-root STATE supplied by runtime.
    """
    path=Path(source);raw=path.read_bytes()
    need(hashlib.sha256(raw).hexdigest()==TASK_HOST_SHA,'DYNTEAM_ORIGINAL_TASK_CHANNEL_AND_POST_SOURCE_PIN')
    wanted={'need','now','wire','save','api','channel_setup','task'}
    tree=ast.parse(raw)
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in wanted]
    need({n.name for n in nodes}==wanted and len(nodes)==len(wanted),'DYNTEAM_ORIGINAL_TASK_FUNCTIONS_EXACT')
    scope={'Path':Path,'datetime':datetime,'hashlib':hashlib,'http':__import__('http'),
           'json':json,'os':os,'re':re,'urllib':__import__('urllib'),'STATE':{}}
    if native_beta_dm:
        # Same approved task bytes, original exact-once intent/error behavior;
        # beta's dispatcher requires the native tagged DM transport selector.
        task=next(n for n in nodes if n.name=='task');prior=copy.deepcopy(task)
        sites={'channel':0,'props':0}
        class NativeDM(ast.NodeTransformer):
            def visit_Subscript(self,node):
                if isinstance(node.value,ast.Name) and node.value.id=='record' and isinstance(node.slice,ast.Constant) and node.slice.value=='task_channel':
                    node.slice=ast.Constant('task_dm_channel');sites['channel']+=1
                return self.generic_visit(node)
            def visit_Dict(self,node):
                keys=[n.value if isinstance(n,ast.Constant) else None for n in node.keys]
                if keys==['channel_id','message']:
                    node.keys.append(ast.Constant('props'));node.values.append(ast.Dict(keys=[ast.Constant('agensh_task')],values=[ast.Constant(True)]));sites['props']+=1
                return self.generic_visit(node)
        NativeDM().visit(task)
        need(sites=={'channel':4,'props':1},'DYNTEAM_ONE_NATIVE_DM_ROUTE_AND_TASK_TAG_ONLY')
        reverted=copy.deepcopy(task)
        class Undo(ast.NodeTransformer):
            def visit_Subscript(self,node):
                if isinstance(node.value,ast.Name) and node.value.id=='record' and isinstance(node.slice,ast.Constant) and node.slice.value=='task_dm_channel':node.slice=ast.Constant('task_channel')
                return self.generic_visit(node)
            def visit_Dict(self,node):
                keys=[n.value if isinstance(n,ast.Constant) else None for n in node.keys]
                if keys==['channel_id','message','props']:node.keys.pop();node.values.pop()
                return self.generic_visit(node)
        Undo().visit(reverted)
        need(ast.dump(reverted,include_attributes=False)==ast.dump(prior,include_attributes=False),
             'DYNTEAM_TASK_DM_SELECTOR_NO_PROMPT_RETRY_OR_INTENT_DELTA')
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(path)+':exact_task_ports','exec'),scope)
    return scope


def _private_scalar(path,*,owner_uid):
    path=Path(path);s=path.lstat()
    need(path.is_absolute() and path.resolve()==path and stat.S_ISREG(s.st_mode) and not path.is_symlink() and
         s.st_uid==owner_uid and s.st_nlink==1 and not stat.S_IMODE(s.st_mode)&0o077 and s.st_size<=4096,
         'DYNTEAM_ONLY_NEW_INFRASTRUCTURE_PRIVATE_SCALAR')
    value=path.read_text().strip()
    need(bool(value) and '\n' not in value and '\r' not in value and '\x00' not in value,
         'DYNTEAM_PRIVATE_INFRASTRUCTURE_SINGLE_SCALAR')
    return value


class NewRootSourceTaskPorts:
    """Same owner source/Gitea/private-channel/task ports, no hidden activate."""
    def __init__(self,core,*,original_task_host_source):
        need(hasattr(core,'native_host_environment') and hasattr(core,'source_bootstraps') and
             not hasattr(core,'source_task_ports'),'DYNTEAM_SAME_COLD_CORE_SOURCE_TASK_PORTS_ONLY_ONCE')
        self.core=core;self.ports=original_task_ports(original_task_host_source,native_beta_dm=True);self.rows={}
        core.source_task_ports=self

    def prepare(self,t):
        need(t in self.core.rows and t in self.core.gate.startup_held and
             self.core.source_bootstraps[t]['state']=='SOURCE_ONLY_READY',
             'DYNTEAM_SOURCE_BEFORE_PUBLISH_AND_MODEL_RELEASE')
        if t in self.rows:
            need(self.rows[t]['state']=='SOURCE_TASK_CHANNEL_READY',
                 'DYNTEAM_SOURCE_TASK_PARTIAL_RETAINED_NO_REPLAY')
            return self.public(t)
        need(self.core.cold_bootstrap._infra_ready(t),
             'DYNTEAM_ORIGINAL_TRUSTED_PUBLISHER_BOOTSTRAP_MUST_BE_PHYSICALLY_COMPLETE')
        # A stale original resource observation is an UNADMITTED wait before
        # any first header/15s receipt or Gitea publication effect. Refresh the
        # same cached original resource pointer; no probe/census is added here.
        producer=getattr(self.core,'resource_producer',None)
        if producer is not None:producer.poll()
        self.core.cohort_resources.refresh()
        if not self.core.cohort_resources.system_open():
            return dict(trajectory=t,state=WAITING,models_dispatched_by_host=0,no_automatic_retry=True)
        if not publication_hostpub_ready(self.core,t):
            return dict(trajectory=t,state=WAITING,models_dispatched_by_host=0,no_automatic_retry=True)
        # Keep the original post-header predicate too: time/health can change
        # during the real headers. Never restamp or reuse an expired receipt.
        producer=getattr(self.core,'resource_producer',None)
        if producer is not None:producer.poll()
        self.core.cohort_resources.refresh()
        if not self.core.cohort_resources.system_open():
            return dict(trajectory=t,state=WAITING,models_dispatched_by_host=0,no_automatic_retry=True)
        row=self.core.rows[t];host=self.core.native_host_environment['trajectories'][t]
        layout=self.core.native_layout.current(t)
        record={'state':'SOURCE_PUBLICATION_PARTIAL_RETAINED','publisher':None,'task_invoked':False}
        self.rows[t]=record
        # All paths belong to the NEW layout; no old owner private config.
        data=Path(layout['profile_root']);tokens=data/'tokens';uid=os.geteuid()
        envpath=Path(host['envfile']);s=envpath.lstat()
        need(envpath.resolve()==envpath and stat.S_ISREG(s.st_mode) and s.st_uid==uid and
             s.st_nlink==1 and stat.S_IMODE(s.st_mode)==0o400 and s.st_size<=65536,
             'DYNTEAM_SAME_NEW_NATIVE_ENV_GENERATED_BY_HOST_COMPILER')
        env={}
        wanted={'MATTERMOST_ADMIN_USER','MATTERMOST_ADMIN_PASSWORD','GITEA_ADMIN_USER','EDGE_HTTP_PORT','EDGE_MM_PORT'}
        for line in envpath.read_text().splitlines():
            key,sep,value=line.partition('=')
            if key in wanted:need(sep and key not in env,'DYNTEAM_NATIVE_ENV_EXACT_INFRA_FIELDS');env[key]=value
        need(set(env)==wanted and env['GITEA_ADMIN_USER']=='chairman' and
             all(env[k].isdigit() and 0<int(env[k])<65536 for k in ('EDGE_HTTP_PORT','EDGE_MM_PORT')),
             'DYNTEAM_FIXED_NEW_NATIVE_LOOPBACK_EDGE_ORIGINS')
        # Original native nginx passes these exact APIs/Git smart HTTP through.
        origins={'gitea':'http://127.0.0.1:'+env['EDGE_HTTP_PORT'],
                 'mattermost':'http://127.0.0.1:'+env['EDGE_MM_PORT']}
        root=Path(row['root']);private=root/'native-source-publication';private.mkdir(mode=0o700)
        binding=GiteaBinding(t,1,digest({'contract':digest(self.core.contract),'trajectory':t,'origins':origins}),
            origins['gitea'],layout['org'],'main',env['GITEA_ADMIN_USER'],'coders',
            _private_scalar(tokens/'admin.token',owner_uid=uid))
        publisher=NativeGitea(binding,self.core.ledger,private/'gitea-private');record['publisher']=publisher
        source_root=Path(self.core.source_bootstraps[t]['receipt']['source_root'])
        publication=source_only_publication(publisher,source_root,hash_file(source_root/'bootstrap-receipt.json'),
                                            registered_roles=row['roles'])
        aliases=native_aliases(row['arm'])
        # Native checker/tester/racing helper accounts deliberately have NO
        # Mattermost identity. Only unchanged native workers see this channel;
        # helper communication stays in its original private Gitea protocols.
        actors={r:layout['org']+'-'+a['native_short'] for r,a in aliases.items() if a['kind']=='worker'}
        role_tokens={r:{'mattermost':_private_scalar(tokens/('agent-'+actor+'-mm.token'),owner_uid=uid)}
                     for r,actor in actors.items()}
        state={'layout':private,'origins':origins,'p':{'organization':layout['org']},'actors':actors}
        self.ports['STATE'][t]=state
        self.ports['channel_setup'](state,list(actors),role_tokens,env)
        admin=state['mm_admin_token'];origin=origins['mattermost']
        st,admin_user,_=self.ports['api'](origin,'GET','/api/v4/users/me',token=admin)
        need(st==200 and admin_user.get('username')==env['MATTERMOST_ADMIN_USER'],
             'DYNTEAM_EXACT_NATIVE_DM_ADMIN_IDENTITY')
        st,worker,_=self.ports['api'](origin,'GET','/api/v4/users/me',token=role_tokens['worker-00']['mattermost'])
        need(st==200 and worker.get('username')==actors['worker-00'],
             'DYNTEAM_EXACT_FIRST_NATIVE_WORKER_DM_IDENTITY')
        ids=[admin_user['id'],worker['id']]
        need(all(type(v) is str and re.fullmatch('[a-z0-9]{26}',v) for v in ids) and len(set(ids))==2,
             'DYNTEAM_EXACT_TWO_NATIVE_DM_IDENTITIES')
        self.ports['save'](private/'ORIGINAL_FIRST_WORKER_DM_CREATE_INTENT.json',
            {'at':self.ports['now'](),'identity_pair_sha256':digest(ids),'no_auto_retry':True})
        st,dm,_=self.ports['api'](origin,'POST','/api/v4/channels/direct',token=admin,body=ids)
        need(st in (200,201) and dm.get('type')=='D' and type(dm.get('id')) is str and
             re.fullmatch('[a-z0-9]{26}',dm['id']), 'DYNTEAM_ORIGINAL_NATIVE_DIRECT_CHANNEL_NO_RETRY')
        state['task_dm_channel']=dm['id']
        self.ports['save'](private/'ORIGINAL_FIRST_WORKER_DM_READY.json',
            {'at':self.ports['now'](),'channel_id':dm['id'],'HTTP':st,'model_calls':0})
        record.update(state='SOURCE_TASK_CHANNEL_READY',publication=publication,source_root=source_root)
        return self.public(t)

    def task(self,t,launch):
        record=self.rows[t]
        from smoke_bootstrap_task_launch import NativeSameCoreSmokeLaunch
        need(type(launch) is NativeSameCoreSmokeLaunch and launch.core is self.core and launch.t==t and
             record['state']=='SOURCE_TASK_CHANNEL_READY' and not record['task_invoked'] and
             t not in self.core.gate.startup_held and launch.released is True,
             'DYNTEAM_ORIGINAL_TASK_ONLY_AFTER_REAL_SAME_CORE_GATE_RELEASE_ONCE')
        # Set before call: even transport/metadata failure retains an exactly-once
        # attempt, never repeat a task POST whose server acceptance is unknown.
        record['task_invoked']=True
        self.ports['task'](self.core.rows[t],launch,record['source_root'])
        record['state']='ORIGINAL_TASK_POST_TERMINAL'
        return self.public(t)

    def public(self,t):
        r=self.rows[t]
        return dict(trajectory=t,state=r['state'],task_invoked=r['task_invoked'],
            gitea_published=r.get('publication',{}).get('gitea_published',False),
            models_dispatched_by_host=0,no_automatic_retry=True)
