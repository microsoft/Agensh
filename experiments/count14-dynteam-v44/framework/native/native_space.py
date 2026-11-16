"""Independent Agensh scope around the original native disk/promise admission.

Original accounting, safety reserve, actual-volume and partial-retention semantics
are retained. Old schema names inside the opaque reservation are an internal ABI;
all actual roots/manifest/trajectory/owner belong to the new Agensh AUX domain.
No fake pilot manifest or unconditional admitted=True port is constructed.
"""
from contextlib import contextmanager
from pathlib import Path
import ast,contextlib,fcntl,hashlib,json,os,time
from common import need,sha,digest,private_dir,wire,publish
from native_materialization import NativeMaterializer
from v21_inputs import verify_input

class NativeSpace:
    def __init__(self,materializer,home,*,manifest_sha256,authorize,free=None,sleeper=time.sleep):
        need(isinstance(materializer,NativeMaterializer),'NATIVE_SPACE_MATERIALIZER_REQUIRED');need(callable(authorize),'NATIVE_SPACE_FRESH_OWNER_PORT')
        self.materializer=materializer;self.home=private_dir(home,create=True);self.manifest=sha(manifest_sha256);self.authorize=authorize;self.sleep=sleeper
        need(not(self.home.is_relative_to(materializer.input_root)or materializer.input_root.is_relative_to(self.home)),'NATIVE_SPACE_NOT_INPUT_ROOT')
        base=Path(__file__).resolve().parent;origin=json.loads((base/'NATIVE_SPACE_ORIGIN.json').read_bytes());text=(base/'native_space_original.py').read_text();nodes=[n for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
        pins={n.name:hashlib.sha256(ast.get_source_segment(text,n).encode()).hexdigest()for n in nodes};need(pins==origin['functions'],'NATIVE_SPACE_ORIGINAL_BODY_PIN')
        constants=origin['constants'];need(constants=={'RESERVE_BYTES':256*2**30,'PER_MEMBER_OVERHEAD':16*1024,'FINALIZER_WRITE_ALLOWANCE':2*2**30},'NATIVE_SPACE_ORIGINAL_RESERVES')
        need({n.name:[ast.unparse(d)for d in getattr(n,'decorator_list',[])]for n in nodes}=={n.name:(['contextlib.contextmanager']if n.name=='locked'else[])for n in nodes},'NATIVE_SPACE_ORIGINAL_DECORATORS')
        changed=0
        for node in nodes:
            if node.name=='try_reserve':
                for n in ast.walk(node):
                    if isinstance(n,ast.ImportFrom)and n.module=='pilot_admission':
                        need([a.name for a in n.names]==['process_identity'],'NATIVE_SPACE_IMPORT_SHAPE');n.module='final_queue';changed+=1
        need(changed==1,'NATIVE_SPACE_IMPORT_SHAPE')
        namespace=dict(contextlib=contextlib,fcntl=fcntl,hashlib=hashlib,json=json,os=os,time=time,Path=Path,need=need,digest=digest,MANIFEST_SHA256=self.manifest,**constants)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(base/'native_space_original.py'),'exec'),namespace)
        self.native=namespace;self.free=free or namespace['free_bytes']
    def scope(self,snapshot,branch,setting):
        self.authorize();branch=Path(branch)
        self.materializer.scope(snapshot,branch/'workspace',setting)
        p=verify_input(self.materializer.input_root,expected_policy_sha=self.materializer.policy_sha,trajectory=self.materializer.trajectory,setting=setting)
        need(p['pins']['manifest']==self.manifest,'NATIVE_SPACE_MANIFEST_PIN')
        return p
    @contextmanager
    def admitted(self,snapshot,branch,setting,**kwargs):
        need(not kwargs,'NATIVE_SPACE_NO_WORKER_OPTIONS');p=self.scope(snapshot,branch,setting);branch=Path(branch)
        need(not branch.exists()and not branch.is_symlink(),'NATIVE_SPACE_FRESH_BRANCH_NO_REPLAY')
        measured=self.native['measured_requirement']({'roles':{r:{'counts':{'bytes':v['bytes'],'members':v['members']}}for r,v in p['roles'].items()}},sum(v['context']['size']for v in p['roles'].values()))
        lease=None
        while lease is None:
            self.scope(snapshot,branch,setting)
            lease=self.native['try_reserve'](self.home,job=str(branch),policy_sha256=self.materializer.policy_sha,measured=measured,free=self.free)
            if lease is None:self.sleep(5) # Original resource HOLD, never failure/retry.
        try:
            parent=branch.parent
            while not parent.exists():parent=parent.parent
            need(parent.stat().st_dev==self.home.stat().st_dev,'NATIVE_SPACE_CROSS_VOLUME')
            # An immutable independent envelope disambiguates the original
            # reservation schema name from a historical pilot allocation.
            publish(self.home/(digest(str(branch))+'.agensh-scope'),wire({'schema':'count14-agensh-native-space-scope-v1','purpose':'AUX_FINALIZATION','trajectory':self.materializer.trajectory,'setting':setting,'manifest_sha256':self.manifest,'input_policy_sha256':self.materializer.policy_sha,'branch':str(branch),'measured':measured,'reservation_sha256':digest(lease.value)}))
            yield lease
        except BaseException:lease.close('RETAINED_PARTIAL');raise
        else:lease.close('MATERIALIZED')
