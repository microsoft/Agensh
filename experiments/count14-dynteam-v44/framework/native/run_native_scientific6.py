#!/usr/bin/env python3
"""Concrete six-trajectory original-science driver; trusted OPS lifecycle ports.

No Docker/SSH implementation, synthetic hook or alternate scientific loop. The
pinned OPS host module implements only named native process/network lifecycle
ports documented in shortest-driver-v1/OPS_HOST_ABI.md. All scientific objects,
source publication, two cuts and real independent K3 are constructed here.
"""
from pathlib import Path
import copy,importlib.util,os,secrets,stat,sys,threading,time
from common import need,digest,hash_file,strict,wire,publish,private_dir,regular_fd,sha,publish_readonly_metadata,sync_dir,stamp
from manifest import compile_manifest
from bootstrap import bootstrap
from budget import Ledger
from snapshot import CAS
from final_queue import FinalQueue
from model_capacity import ModelCapacity
from final_host_rpc import HostServer
from native_final_profile import compile_profile
from native_images import ORIGINAL_INVENTORY
from native_unmanaged_cli import NativeTools
from native_delivery import prepare_delivery
from native_gitea import NativeGitea,GiteaBinding
from native_team_owner import NativeTeamOwner,postflight
from native_scientific_launch import NativeScientificLaunch,original_cli_receipts
from native_final_dispatch import NativeFinalDispatcher
from scientific_profile import SearchProfile,RNG_POLICY_SHA
from scientific_relay import Bounds
from feasibility_relay import ChatTransport

HOST_METHODS=('admit','backend','workers','cli','inventory','ready','task')
FIELDS={'schema','manifest','model_policy','bounds','bounds_sha256','upstream',
        'maximum_output','source','final','host_module','host_module_sha256',
        'launch_order','driver_directory'}
BACKEND_FIELDS={'organization','repository','admin_username','writers_team',
    'service_instance_sha256','bootstrap_receipt_sha256','gitea_origin','mm_origin',
    'gitea_admin_token','mm_admin_token','role_tokens','board_origin','board_ids','repository_root','relay_listen'}
WORKER_FIELDS={'peers','roles','delivery_roots','sandbox','sdk_identity','sdk_launches',
               'registered_refs','member_cap'}
LEGACY_TOOL_FIELDS={'shell_context_roots','git_front_urls'}

def private_input(path,expected):
    p=Path(path);need(p.is_absolute()and p.resolve()==p and not p.is_symlink(),'DRIVER_CANONICAL_PRIVATE_INPUT')
    with regular_fd(p)as fd:
        s=os.fstat(fd);need(s.st_uid in (0,os.geteuid())and stat.S_IMODE(s.st_mode)==0o600
                           and s.st_nlink==1,'DRIVER_PRIVATE_INPUT_OWNER_MODE')
    need(hash_file(p)['sha256']==sha(expected),'DRIVER_PRIVATE_INPUT_PIN');return p

def load_host(path,expected):
    p=private_input(path,expected)
    spec=importlib.util.spec_from_file_location('agensh_ops_exact_host_'+expected[:16],p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    need(all(callable(getattr(module,n,None))for n in HOST_METHODS),'DRIVER_HOST_NAMED_LIFECYCLE_PORTS')
    return module

def read_configuration(path,pin):
    c=strict(private_input(path,pin).read_bytes());need(type(c)is dict and set(c)==FIELDS
        and c['schema']=='agensh-native-scientific6-driver-v1','DRIVER_EXACT_CONFIG')
    return c

def compile_configuration(configuration):
    """Metadata-only concrete profile/compiler, no host load/runtime/model start.

    Original source/task/model/RNG pins must already agree or be explicitly null
    in the trusted template. Other protocol pins remain supplied original facts.
    """
    c=copy.deepcopy(configuration);_exact(c,FIELDS,'DRIVER_EXACT_CONFIG')
    # User authorization: missing platform facts are NOT a launch prerequisite.
    # This is an explicit LOCAL planning policy; never fabricate a server proof.
    if c['bounds']is None and c['bounds_sha256']is None:
        c['bounds']=Bounds.configured(c['model_policy']['model'],c['maximum_output'])
        c['bounds_sha256']=digest(c['bounds'])
    Bounds(c['bounds'],c['bounds_sha256'])
    m=c['manifest'];f=c['final'];protocol=m['protocol']
    derived={'source_bundle':hash_file(Path(c['source']['archive']))['sha256'],
        'task_description':hash_file(Path(c['source']['description']))['sha256'],
        'model_configuration':digest(c['model_policy']),'rng_policy':RNG_POLICY_SHA}
    for key,value in derived.items():
        need(protocol.get(key)in (None,value),'DRIVER_APPROVED_TEMPLATE_PIN_CHANGED')
        protocol[key]=value
    profile=compile_profile(f['native_directory'],source_bundle_sha256=protocol['source_bundle'],
        model_policy_sha256=derived['model_configuration'],evaluator_root=f['evaluator_root'],
        image_mapping_sha256=f['image_mapping_sha256'],dependency_freeze_sha256=f['dependency_freeze_sha256'])
    protocol['final_v21']=digest(profile)
    compiled=compile_manifest(m)
    if c['launch_order']==[]:
        c['launch_order']=[r['trajectory_id']for r in sorted(compiled['trajectories'],key=lambda r:(r['block'],len(r['roles'])))]
    return c

def _exact(value,fields,code):
    need(type(value)is dict and set(value)==set(fields),code);return value

def _copy_opaque(source,destination,pin=None):
    """Trusted runtime copy only; never decode scientific/evaluator/key bytes."""
    import shutil
    source=Path(source);destination=Path(destination)
    with regular_fd(source)as fd:
        before=os.fstat(fd)
        need(not destination.exists()and not destination.is_symlink(),'DRIVER_NEW_OPAQUE_COPY')
        with destination.open('xb')as out,os.fdopen(os.dup(fd),'rb')as src:
            shutil.copyfileobj(src,out,1024*1024);out.flush();os.fsync(out.fileno())
        after=os.fstat(fd)
    destination.chmod(0o400)
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
         (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),
         'DRIVER_OPAQUE_SOURCE_CHANGED')
    need(hash_file(destination)==hash_file(source),'DRIVER_OPAQUE_COPY_BYTES')
    if pin is not None:need(hash_file(destination)['sha256']==pin,'DRIVER_OPAQUE_COPY_PIN')

class ScientificSixDriver:
    def __init__(self,configuration,host):
        self.config=copy.deepcopy(configuration);c=self.config
        _exact(c,FIELDS,'DRIVER_EXACT_CONFIG');need(c['schema']=='agensh-native-scientific6-driver-v1','DRIVER_CONFIG_SCHEMA')
        need(all(callable(getattr(host,n,None))for n in HOST_METHODS),'DRIVER_HOST_NAMED_LIFECYCLE_PORTS')
        self.host=host;self.retained=[];self.records={};self.failed=False;self.finished=False
        self.source=_exact(c['source'],{'archive','description','index','index_sha256'},'DRIVER_SOURCE_FIELDS')
        index_path=Path(self.source['index']);index=strict(index_path.read_bytes())
        need(digest(index)==sha(self.source['index_sha256']),'DRIVER_SOURCE_INDEX_PIN');self.source_index=index
        f=_exact(c['final'],{'native_directory','evaluator_root','image_mapping','image_mapping_sha256',
            'dependency_freeze_sha256','framework_root','docker_config','python_command','environment',
            'credential_source'},'DRIVER_FINAL_FIELDS');self.final=f
        m=copy.deepcopy(c['manifest']);root=Path(m['root']);need(root.is_absolute()and root.resolve()==root,'DRIVER_ROOT')
        # Original runtime requires code/framework/Docker config under this new
        # experiment root. OPS may copy/reflink approved public inputs there;
        # canonical symlink aliases are NOT accepted by the original runtime.
        for name in ('native_directory','framework_root','docker_config'):
            p=Path(f[name]);need(p.is_absolute()and p.resolve()==p and p.is_relative_to(root)and p.is_dir(),
                               'DRIVER_ORIGINAL_FINAL_PATH_INSIDE_EXPERIMENT')
        need(hash_file(Path(self.source['archive']))['sha256']==m['protocol']['source_bundle']
             and hash_file(Path(self.source['description']))['sha256']==m['protocol']['task_description'],
             'DRIVER_SAME_APPROVED_SOURCE_TASK')
        need(m['protocol']['model_configuration']==digest(c['model_policy'])
             and m['protocol']['rng_policy']==RNG_POLICY_SHA,'DRIVER_MODEL_RNG_PINS')
        mapping=strict(Path(f['image_mapping']).read_bytes());need(type(mapping)is list and digest(mapping)==f['image_mapping_sha256'],
                                                                 'DRIVER_ORIGINAL_IMAGE_ROWS_PIN')
        profile=compile_profile(f['native_directory'],source_bundle_sha256=m['protocol']['source_bundle'],
            model_policy_sha256=digest(c['model_policy']),evaluator_root=f['evaluator_root'],
            image_mapping_sha256=f['image_mapping_sha256'],dependency_freeze_sha256=f['dependency_freeze_sha256'])
        need(m['protocol']['final_v21']==digest(profile),'DRIVER_EXACT_COMPILED_FINAL_PROFILE')
        self.profile=profile;self.manifest=m;self.compiled=compile_manifest(m);SearchProfile(m,c['model_policy'],digest(c['model_policy']))
        self.bounds=Bounds(c['bounds'],c['bounds_sha256'])
        need(self.bounds.matches_model(c['model_policy']['model'])and
             ((self.bounds.context_limit is not None and c['maximum_output']is None)or
              (self.bounds.context_limit is None and type(c['maximum_output'])is int and
               0<c['maximum_output']<=c['bounds']['maximum_output_tokens'])),
             'DRIVER_ACTUAL_MODEL_OUTPUT_BOUND')
        self.rows={r['trajectory_id']:r for r in self.compiled['trajectories']}
        order=c['launch_order'];need(type(order)is list and len(order)==6 and set(order)==set(self.rows),'DRIVER_EXACT_SIX_ORDER')
        self.pending=list(order);home=Path(c['driver_directory'])
        need(home.is_absolute()and home.resolve()==home and home.is_relative_to(root),'DRIVER_PRIVATE_STATE_ROOT')
        self.root=private_dir(home,create=True);need(not any(self.root.iterdir()),'DRIVER_NEW_STATE_NO_RESTART')
        self.upstream=_exact(c['upstream'],{'base','token_file','auth_style','timeout_seconds'},'DRIVER_UPSTREAM_FIELDS')
        need(type(self.upstream['timeout_seconds'])in (int,float)and 0<self.upstream['timeout_seconds']<=86400,'DRIVER_ORIGINAL_TRANSPORT_TIMEOUT')
        self.state='PREPARED';self.shared_started=False
        publish(self.root/'MANIFEST.json',wire(m));publish(self.root/'COMPILED.json',wire(self.compiled))
        publish(self.root/'FINAL_PROFILE.json',wire(profile))
        publish(self.root/'RESERVATION_POLICY.json',wire({'policy':self.bounds.proof,
            'policy_sha256':self.bounds.sha,'kind':self.bounds.kind,
            'server_token_ceiling_verified':self.bounds.server_token_ceiling_verified}))
    def admit(self,row,phase):
        value=self.host.admit(row,phase)
        if value is None:return None
        _exact(value,{'current_owner_authorized','gateway_health_sha256','allocation_sha256'},'DRIVER_ACTUAL_ADMISSION_FIELDS')
        need(value['current_owner_authorized']is True,'DRIVER_ACTUAL_OWNER_ADMISSION')
        sha(value['gateway_health_sha256']);sha(value['allocation_sha256']);return value
    def initialize_shared(self,evidence):
        need(not self.shared_started,'DRIVER_SHARED_ONCE');self.shared_started=True
        self.ledger=Ledger(self.root/'ledger');self.ledger.native_unmanaged_cli=True
        self.ledger.enable_unknown_reservation_policy();self.cas=CAS(self.root/'cas')
        self.queue=FinalQueue(self.root/'final-queue',manifest_sha256=digest(self.manifest),
            global_cap=self.manifest['scheduling']['final_global_cap'])
        self.capacity=ModelCapacity(self.ledger,
            native_transport_sha256=hash_file(Path(self.final['native_directory'])/'cc_streaming.py')['sha256'],
            native_classifier_sha256=hash_file(Path(self.final['native_directory'])/'request_policy.py')['sha256'],
            global_allocated_cap=self.manifest['scheduling']['global_gateway_cap'],
            auxiliary_cap=self.manifest['scheduling']['auxiliary_cap'])
        self.capacity.release(owner_evidence=evidence)
        self.parents=NativeTools(self.ledger);self.receipts=None
        self.server=HostServer(self.root/'final-host.sock',self.capacity);self.server.start()
        self.dispatcher=NativeFinalDispatcher(self.ledger,self.queue,self.capacity,self.server,
            directory=self.root/'final-children',configuration=self.final_configuration,
            python_command=tuple(self.final['python_command']),environment=self.final['environment'])
        self.points={};self.state='RUNNING'
    def final_configuration(self,job):
        point=job['point']
        if point not in self.points:
            home=private_dir(self.root/'final-points'/digest(point),create=True)
            need(not any(home.iterdir()),'DRIVER_FRESH_FINAL_POINT')
            self.points[point]={'home':home,'ready':False} # retain before fallible copies
            ev=private_dir(home/'evaluator-private',create=True);cr=private_dir(home/'credentials',create=True)
            for name,pin in self.profile['evaluator_assets'].items():
                _copy_opaque(Path(self.final['evaluator_root'])/name,ev/name,pin['sha256'])
            _copy_opaque(self.final['credential_source'],cr/'glm_api_key')
            self.points[point]['ready']=True
        record=self.points[point];need(record['ready'],'DRIVER_FINAL_POINT_PREPARATION_FAILED_NO_RETRY')
        return {'manifest':self.manifest,'model_policy':self.config['model_policy'],'input_root':job['input_root'],
            'input_policy_sha256':job['input_policy'],'trajectory':job['trajectory'],'k':job['replicate'],
            'aux_root':str(record['home']),'native_directory':self.final['native_directory'],'profile':self.profile,
            'services':{'schema':'count14-agensh-final-services-v1','purpose':'AUX_FINALIZATION',
                'framework_root':self.final['framework_root'],'docker_host':'unix:///var/run/docker.sock',
                'docker_config':self.final['docker_config'],'dependency_freeze_sha256':self.final['dependency_freeze_sha256']},
            'image_freeze':{'schema':'count14-agensh-images-v1','manifest_sha256':digest(self.manifest),
                'docker_host':'unix:///var/run/docker.sock','original_inventory_sha256':ORIGINAL_INVENTORY,
                'images':strict(Path(self.final['image_mapping']).read_bytes())},'space_home':str(self.root/'final-space')}
    def launch_one(self,trajectory):
        need(self.shared_started and not self.failed and trajectory in self.pending,'DRIVER_FIRSTSTART_PENDING_ONCE')
        row=self.rows[trajectory];layout=Path(row['root']);layout.mkdir(parents=True,exist_ok=True)
        self.pending.remove(trajectory);record={'row':row,'layout':layout,'phase':'ALLOCATED'};self.records[trajectory]=record
        # Original ledger is registered before trusted native source publication.
        self.ledger.register(trajectory,row['roles'],digest(self.manifest),request_cap=len(row['roles']))
        try:
            b=self.host.backend(row,layout);_exact(b,BACKEND_FIELDS,'DRIVER_BACKEND_FIELDS');record['backend']=b
            boot=layout/'bootstrap';bootstrap(self.source['archive'],self.source['description'],self.source_index,
                self.source['index_sha256'],boot,row['roles'])
            publication=NativeGitea(GiteaBinding(trajectory,1,b['service_instance_sha256'],b['gitea_origin'],
                b['organization'],b['repository'],b['admin_username'],b['writers_team'],b['gitea_admin_token']),
                self.ledger,layout/'publication');record['publication']=publication
            publication.publication(boot,hash_file(boot/'bootstrap-receipt.json'))
            parents=self.parents;delivery=prepare_delivery(layout/'transport-exports',row['roles'])
            identities={secrets.token_hex(32):(trajectory,role)for role in row['roles']}
            # Provider credentials remain in private runtime memory, never logs.
            token=Path(self.upstream['token_file']).read_text().strip()
            transport=ChatTransport(self.upstream['base'],token,auth_style=self.upstream['auth_style'],timeout=self.upstream['timeout_seconds'])
            launch=NativeScientificLaunch.prepare_transport(ledger=self.ledger,parents=parents,trajectory=trajectory,
                manifest=self.manifest,model_policy=self.config['model_policy'],bounds=self.bounds,transport=transport,
                directory=layout/'scientific',http_address=tuple(b['relay_listen']),identities=identities,
                maximum_output=self.config['maximum_output']);record['launch']=launch;record['identities']=identities
            # No worker-selected credentials; unique OPS injects the role's own
            # opaque relay capability by this dedicated trusted lifecycle input.
            record['phase']='HELD_TRANSPORT'
            startup={}
            for role in row['roles']:
                leaf=layout/'router-startup'/role;leaf.mkdir(mode=0o700,parents=True,exist_ok=False)
                # Only this role's public, readonly startup leaf crosses the
                # worker mount. Private ancestors retain the caller's077.
                leaf.chmod(0o755)
                binding={'schema':'agensh-original-router-startup-binding-v1','trajectory':trajectory,
                         'role':role,'manifest_sha256':digest(self.manifest),'owner_pid':os.getpid()}
                startup[role]={'directory':str(leaf),'binding_sha256':digest(binding),'owner_uid':os.geteuid(),
                    'container_directory':'/run/count14/startup',
                    'clock_container_file':'/run/count14/budget-clock/'+role+'.json'}
            launch.startup_bindings=startup

            workers=self.host.workers(row,layout,boot,delivery,launch);record['workers']=workers
            need(type(workers)is dict and set(workers)in(WORKER_FIELDS,WORKER_FIELDS|LEGACY_TOOL_FIELDS),'DRIVER_WORKER_FIELDS')
            need(workers['delivery_roots']==delivery,'DRIVER_ORIGINAL_PREMOUNTED_DELIVERY')
            gb,mb,pf=postflight(trajectory,row['roles'],service_instance_sha256=b['service_instance_sha256'],
                bootstrap_receipt_sha256=b['bootstrap_receipt_sha256'],organization=b['organization'],repository=b['repository'],
                gitea_origin=b['gitea_origin'],mm_origin=b['mm_origin'],gitea_admin_token=b['gitea_admin_token'],
                mm_admin_token=b['mm_admin_token'],role_tokens=b['role_tokens'],
                workspaces={role:str(v['workspace'])for role,v in workers['roles'].items()})
            publish(layout/'POSTFLIGHT_METADATA.json',wire(pf))
            team=NativeTeamOwner(self.ledger,layout/'team-owner',gb,mb,role_tokens=b['role_tokens'],peers=workers['peers'],
                board_origin=b['board_origin'],board_ids=b['board_ids'],parent_tool_provider=parents,delivery_roots=delivery,
                sandbox=workers['sandbox'],sdk_identity=workers['sdk_identity'],sdk_launches=workers['sdk_launches'])
            record['team']=team;team.start();cli=self.host.cli(team,workers,launch)
            need(type(cli)is dict and set(cli)in(set(),{'cli_peers','cli_socket_paths'}),'DRIVER_CLI_FIELDS')
            inventory=self.host.inventory(team,workers,b);_exact(inventory,{'services','backend_names','writer_domains'},'DRIVER_INVENTORY_FIELDS')
            pins={'manifest':digest(self.manifest),'protocol':self.manifest['protocol']['final_v21'],
                  'source':self.manifest['protocol']['source_bundle'],'task_description':self.manifest['protocol']['task_description']}
            launch.attach(team=team,publication=publication,repository_root=b['repository_root'],cas=self.cas,final_queue=self.queue,
                roles=workers['roles'],pins=pins,registered_refs=tuple(workers['registered_refs']),member_cap=workers['member_cap'],
                services=inventory['services'],backend_names=tuple(inventory['backend_names']),writer_domains=inventory['writer_domains'],
                cli_peers=cli.get('cli_peers'),cli_socket_paths=cli.get('cli_socket_paths'),shell_context_roots=workers.get('shell_context_roots'),
                git_front_urls=workers.get('git_front_urls'))
            bindings=launch.start();need(self.host.ready(launch,workers,bindings)is True,'DRIVER_ORIGINAL_CLOCK_NETWORK_READY')
            for role,v in startup.items():
                publish_readonly_metadata(Path(v['directory'])/'CLOCK_READY.json',wire({
                    'schema':'agensh-original-router-clock-release-v1','binding_sha256':v['binding_sha256'],
                    'budget_pause_file':v['clock_container_file'],
                    'budget_pause_binding_sha256':bindings[role]['binding_sha256'],
                    'budget_pause_owner_uid':v['owner_uid']}))

            # Actual fresh admission after the potentially long native startup,
            # not the old pre-batch metric. Failure retains held original team.
            need(self.admit(row,'release-search')is not None,'DRIVER_FRESH_RELEASE_ADMISSION')
            launch.release_search();record['phase']='SEARCH_RELEASED'
            def run():
                try:
                    status=launch.run();record['terminal']=status
                    if status['owner_state']=='FAULT':self._fault(trajectory)
                except BaseException:self._fault(trajectory)
            thread=threading.Thread(target=run,name='science-'+digest(trajectory)[:12],daemon=False)
            record['thread']=thread;thread.start()
            # Exactly original task route; no provider/model send in the driver.
            self.host.task(row,launch,boot);record['phase']='ORIGINAL_TASK_RELEASED'
            return trajectory
        except BaseException:self._fault(trajectory);raise
    def _fault(self,trajectory):
        self.failed=True;self.state='FAULT_RETAINED_NO_RETRY'
        self.ledger.latch_fault(trajectory,'SCIENTIFIC6_DRIVER_FAILURE_RETAINED_NO_RETRY')
        # All original model waiters see durable admission faults. No SENT
        # cancellation, kill, queue completion, lock release or native cleanup.
        for t in self.records:
            self.ledger.latch_fault(t,'SCIENTIFIC6_DRIVER_ADMISSION_SEALED_AFTER_FAILURE')
    def _publish_status(self,status):
        """Only this private, mutable projection replaces an earlier version.

        Immutable configs/receipts still use original publish() no-clobber.
        Single driver writer, private owned directory, exact0600 single inode;
        readers see a whole old or new value, never a partial JSON document.
        """
        private_dir(self.root)
        target=self.root/'DRIVER_STATUS.json'
        try:before=target.lstat()
        except FileNotFoundError:before=None
        if before is not None:
            need(stat.S_ISREG(before.st_mode)and before.st_uid==os.geteuid()
                 and stat.S_IMODE(before.st_mode)==0o600 and before.st_nlink==1,
                 'DRIVER_STATUS_PRIVATE_SINGLE_FILE')
            with regular_fd(target)as fd:
                current=os.fstat(fd)
                need((stamp(before),before.st_uid)==(stamp(current),current.st_uid),
                     'DRIVER_STATUS_FILE_CHANGED')
        temporary=self.root/('.driver-status-'+secrets.token_hex(16)+'.partial')
        try:
            publish(temporary,wire(status))
            # publish() retains the process umask; ensure exact0600 before
            # replacement, without changing the process-wide private umask.
            with regular_fd(temporary)as fd:os.fchmod(fd,0o600);os.fsync(fd)
            if before is None:
                need(not target.exists()and not target.is_symlink(),'DRIVER_STATUS_FILE_CHANGED')
            else:
                current=target.lstat()
                need((stamp(before),before.st_uid)==(stamp(current),current.st_uid),
                     'DRIVER_STATUS_FILE_CHANGED')
            os.replace(temporary,target);sync_dir(self.root)
        finally:
            if temporary.exists():temporary.unlink();sync_dir(self.root)
    def tick(self):
        need(not self.failed,'DRIVER_FAULT_NO_RETRY')
        if not self.shared_started:
            evidence=self.admit(None,'initialize-shared')
            if evidence is None:return self.status()
            self.initialize_shared(evidence)
        self.dispatcher.poll()
        if self.admit(None,'new-final-claims')is not None:
            while self.dispatcher.dispatch_one()is not None:pass
        if self.pending:
            row=self.rows[self.pending[0]]
            if self.admit(row,'new-trajectory')is not None:self.launch_one(row['trajectory_id'])
        if not self.pending and len(self.records)==6:
            terminal=all(r.get('terminal',{}).get('owner_state')=='FINAL_PARKED'for r in self.records.values())
            if terminal and self.queue.frontier()=={'COMPLETE':36+3*getattr(self,'_r16_natural_point_count',0)} and self.ledger.global_logical_unresolved()==0:
                self.finished=True;self.state='SCIENCE_COMPLETE_NATIVE_RETIREMENT_OPS_OWNED'
        status=self.status();self._publish_status(status);return status
    def status(self):
        return {'schema':'agensh-scientific6-driver-status-v1','state':self.state,'failed':self.failed,
            'launched':len(self.records),'pending':len(self.pending),'finished':self.finished,
            'original_handles_retained':True,'queue':self.queue.frontier()if self.shared_started else{},
            'trajectories':{t:{'phase':r['phase'],'owner_state':r.get('terminal',{}).get('owner_state')}
                            for t,r in self.records.items()}}
    def run(self):
        while not self.finished:
            self.tick();time.sleep(.25)
        return self.status()

def main():
    if len(sys.argv)==5 and sys.argv[1]=='--compile-config':
        c=compile_configuration(read_configuration(sys.argv[2],sys.argv[3]));out=Path(sys.argv[4])
        need(not out.exists()and not out.is_symlink(),'DRIVER_COMPILED_CONFIG_NEW_FILE')
        publish(out,wire(c));print(wire({'configuration':str(out),'sha256':hash_file(out)['sha256'],
            'model_requests':0,'host_module_loaded':False}).decode());return 0
    need(len(sys.argv)==3,'DRIVER_CONFIG_AND_SHA_REQUIRED')
    c=read_configuration(sys.argv[1],sys.argv[2]);host=load_host(c['host_module'],c['host_module_sha256'])
    driver=ScientificSixDriver(c,host)
    try:driver.run()
    except BaseException:
        publish(driver.root/'DRIVER_RETAINED_FAILURE.json',wire({'schema':'agensh-driver-retained-failure-v1',
            'original_handles_retained':True,'retry':False,'state':driver.state}))
        # Preserve owning interpreter, locks, Popen and RPC while OPS handles
        # the retained original instance. No automatic cleanup/restart/retry.
        while True:time.sleep(60)
    return 0

if __name__=='__main__':sys.exit(main())
