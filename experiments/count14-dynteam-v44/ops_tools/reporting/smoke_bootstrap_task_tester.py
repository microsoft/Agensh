"""Original tester's real initial assignment in a SAME new smoke root.

This invokes native configure+release(0), including private tests-repository
archive, original frozen interval template rendering and original tester_cycle
publication. No empty/fabricated suite/input/prompt/result or ProgramBench main.
Later periodic evaluation/worker-start host writers are NOT started by this port;
full formal deployment must separately bind their whole-domain custody first.
"""
from pathlib import Path
import ast
import copy
import hashlib
import os
import stat
import time
from types import FunctionType,MethodType

from common import need,digest
from native_system_probe_child import append

TESTER_SOURCE_SHA='f8572c4a3bb01557450a830e043b264793dce7d785c08a78b70d8acbfddb335a'
RUNNER_SOURCE_SHA='94eb3c30f8698f42ea8aee1842c18c9e6dbdda71fcdfb61210548f1c74c5df12'
TOKEN_CONTROLLED_WALL_SENTINEL_SECONDS=2**31-1


def original_tester_namespace(source,*,configuration,docker_argv):
    """Private original module; only config location/daemon are host selectors."""
    path=Path(source);raw=path.read_bytes()
    need(path.is_absolute() and path.resolve()==path and hashlib.sha256(raw).hexdigest()==TESTER_SOURCE_SHA,
         'DYNTEAM_ORIGINAL_NATIVE_TESTER_SOURCE_PIN')
    runner=path.with_name('pbench_test_runner.py');raw_runner=runner.read_bytes()
    need(hashlib.sha256(raw_runner).hexdigest()==RUNNER_SOURCE_SHA,'DYNTEAM_ORIGINAL_NATIVE_TEST_RUNNER_PIN')
    # Trusted runtime imports the exact frozen public test harness, NEVER reads
    # the scientific tester suite here. Its cases() executes only downstream.
    helper={'__name__':'count14_frozen_original_native_test_runner','__file__':str(runner)}
    exec(compile(raw_runner,str(runner),'exec'),helper)
    tree=ast.parse(raw);prior=copy.deepcopy(tree)
    dependencies=[n for n in tree.body if isinstance(n,ast.ImportFrom) and n.module=='pbench_test_runner']
    need(len(dependencies)==1 and len(dependencies[0].names)==1 and
         dependencies[0].names[0].name=='cases' and dependencies[0].names[0].asname=='discover_cases',
         'DYNTEAM_ONE_NATIVE_TESTER_FROZEN_HARNESS_IMPORT')
    tree.body.remove(dependencies[0])
    scope={'__name__':'count14_frozen_original_native_tester','__file__':str(path),
           'discover_cases':helper['cases']}
    exec(compile(tree,str(path),'exec'),scope)
    cls=scope['TesterRun']
    init=next(n for n in ast.parse(raw).body if isinstance(n,ast.ClassDef) and n.name=='TesterRun')
    init=copy.deepcopy(next(n for n in init.body if isinstance(n,ast.FunctionDef) and n.name=='__init__'))
    before=copy.deepcopy(init)
    sites=[n for n in ast.walk(init) if isinstance(n,ast.Assign) and len(n.targets)==1 and
        isinstance(n.targets[0],ast.Attribute) and isinstance(n.targets[0].value,ast.Name) and
        n.targets[0].value.id=='self' and n.targets[0].attr=='config']
    need(len(sites)==1,'DYNTEAM_ONE_NATIVE_TESTER_NEW_ENVFILE_SELECTOR')
    old=copy.deepcopy(sites[0].value);sites[0].value=ast.Name(id='_count14_configuration',ctx=ast.Load())
    undone=copy.deepcopy(init)
    n=next(n for n in ast.walk(undone) if isinstance(n,ast.Assign) and len(n.targets)==1 and
        isinstance(n.targets[0],ast.Attribute) and isinstance(n.targets[0].value,ast.Name) and
        n.targets[0].value.id=='self' and n.targets[0].attr=='config')
    n.value=old
    need(ast.dump(undone,include_attributes=False)==ast.dump(before,include_attributes=False),
         'DYNTEAM_NATIVE_TESTER_INIT_ONLY_GENERATED_ENV_LOCATION_DELTA')
    scope['_count14_configuration']=dict(configuration)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[init],type_ignores=[])),
        str(path)+':count14_newroot_env','exec'),scope)
    cls.__init__=scope.pop('__init__')
    # Same exact daemon used by the native role containers and these read-only
    # initial Git archive / board publication ports; never system Docker.
    need(type(docker_argv) in (tuple,list) and len(docker_argv)==3 and
         docker_argv[1]=='--host' and (docker_argv[2].startswith('unix:///mnt/ptb-scratch2/') or
         docker_argv[2].startswith('unix:///mnt/ptb-scratch/')),
         'DYNTEAM_NATIVE_TESTER_EXACT_PRIVATE_DOCKER_ROUTE')
    scope['DOCKER']=list(docker_argv)
    return scope


class NativeTesterInitialRelease:
    def __init__(self,core,trajectory,source_task_ports,*,pbench_tester_source):
        need(core.contract.get('mode')=='smoke' and trajectory in core.rows and
             core.rows[trajectory]['arm']=='DYNTEAM' and source_task_ports is getattr(core,'source_task_ports',None) and
             source_task_ports.core is core and trajectory in core.gate.startup_held and
             source_task_ports.rows[trajectory]['state']=='SOURCE_TASK_CHANNEL_READY',
             'DYNTEAM_REAL_TESTER_INITIAL_ASSIGNMENT_SAME_HELD_SMOKE_OWNER')
        self.core,self.t,self.ports=core,trajectory,source_task_ports
        self.source=Path(pbench_tester_source);self.state='BOUND_NOT_INVOKED';self.run=None
        if not hasattr(core,'native_tester_initial'):core.native_tester_initial={}
        need(trajectory not in core.native_tester_initial,'DYNTEAM_NATIVE_TESTER_INITIAL_RELEASE_ONCE')
        core.native_tester_initial[trajectory]=self

    def prepare(self):
        need(self.state=='BOUND_NOT_INVOKED' and self.t in self.core.gate.startup_held,
             'DYNTEAM_NATIVE_TESTER_NO_INITIAL_RELEASE_REPLAY')
        producer=getattr(self.core,'resource_producer',None)
        if producer is not None:producer.poll()
        self.core.cohort_resources.refresh()
        if not (self.core.cohort_resources.system_open() and self.core.cold_bootstrap._infra_ready(self.t)):
            return None  # BOUND_NOT_INVOKED; no tester/native effect consumed.
        host=self.core.native_host_environment['trajectories'][self.t]
        layout=self.core.native_layout.current(self.t);root=Path(self.core.rows[self.t]['root'])
        need(self.source.parent.parent==Path(host['project_root']),
             'DYNTEAM_TESTER_SAME_FROZEN_NATIVE_PROJECT_ROOT')
        env=Path(host['envfile']);s=env.lstat()
        need(env.resolve()==env and stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid() and
             s.st_nlink==1 and stat.S_IMODE(s.st_mode)==0o400 and s.st_size<=65536,
             'DYNTEAM_TESTER_ONLY_NEW_NATIVE_HOST_ENVFILE')
        configuration=dict(line.split('=',1) for line in env.read_text().splitlines() if line)
        docker=self.core.native_containers.docker;docker.verify_daemon()
        scope=original_tester_namespace(self.source,configuration=configuration,docker_argv=docker.argv())
        run=scope['TesterRun'](host['profile']);self.run=run
        need(run.data==Path(layout['profile_root']) and run.org==layout['org'] and len(run.workers)==32 and
             run.testers==[layout['org']+'-tester1'] and run.tester==layout['org']+'-tester1' and
             configuration['AGENT_IMAGE']==host['image_ids']['agent'],
             'DYNTEAM_NATIVE_TESTER_EXACT_ORIGINAL_NEWROOT_INPUT_CATALOGUE')
        need(not (run.inbox/'0000').exists() and not (run.data/'control/run.json').exists(),
             'DYNTEAM_TESTER_INITIAL_NEW_ASSIGNMENT_NO_REPLAY_OR_DIRECTORY_DELETE')
        channel=self.ports.ports['STATE'][self.t]
        # Original private channel setup has already positively verified this
        # team's ID; project only that PUBLIC control metadata, not content.
        from common import strict
        ready=strict((channel['layout']/'ORIGINAL_PRIVATE_TASK_CHANNEL_READY.json').read_bytes())
        self.state='INITIAL_RELEASE_PARTIAL_RETAINED'
        append(root/'NATIVE_TESTER_INITIAL_INTENT_PUBLIC.json',dict(schema='count14-native-tester-initial-v1',
            trajectory=self.t,contract_sha256=digest(self.core.contract),release_number=0,model_calls_by_host=0,
            automatic_retry=False,periodic_or_startup_observers_started=False))
        # Core token accounting / native model and membership gates are the
        # authoritative end boundary. Native's wall-only refresh sentinel must
        # not independently expire during a token-budgeted trajectory.
        run.configure(int(time.time()*1000),TOKEN_CONTROLLED_WALL_SENTINEL_SECONDS,
                      mm_team_id=ready['team_id'],task_channel_id=ready['channel_id'])
        release=run.release(0) # REAL native archive/template/tester_cycle, never fabricated input.
        need(release['number']==0 and release['tester']==run.tester and
             (run.inbox/'0000/release.json').is_file() and (run.inbox/'0000/interval-prompt.md').is_file() and
             (run.inbox/'latest').is_symlink(), 'DYNTEAM_REAL_NATIVE_TESTER_INITIAL_RELEASE_READY')
        self.state='ORIGINAL_TESTER_CYCLE0_PUBLISHED_MODELS_HELD'
        value=self.public();append(root/'NATIVE_TESTER_INITIAL_READY_PUBLIC.json',value);return value

    def public(self):
        return dict(schema='count14-native-tester-initial-public-v1',trajectory=self.t,state=self.state,
            original_native_release_number=0,model_calls_by_host=0,empty_or_synthetic_input=False,
            periodic_or_startup_observers_started=False,formal_tester_run_custody_still_required=True,
            token_budget_end_is_original_core_gate=True)
