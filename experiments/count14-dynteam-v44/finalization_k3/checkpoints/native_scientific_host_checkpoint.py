"""Cold-only host-writer seam on the SAME original checkpoint instance.

No model/HTTP/ledger/schema/retry changes. The original controller continues
to drain models, request membership cuts, freeze ALL native /work domains,
perform backups, COMMIT snapshots, select candidates and enqueue K3. This seam
only serializes the extra host tester writer and original metadata publisher,
then adds their immutable CAS references to the original native control backup.
It NEVER requires an ongoing guest Game/round/future to finish before a cut.
This is same-live snapshot custody, not a cold SDK restore qualification.
"""
from pathlib import Path
from types import MethodType
import copy

from common import need,digest


class ScientificHostCheckpoint:
    def __init__(self,checkpoint,*,tester,consumer,manager):
        from native_dynamic_checkpoint import DynamicCheckpointPorts
        from formal_count14_tester import FormalCount14Tester
        from native_racing_shared_tests import RacingSharedPublicTests
        from smoke_racing_tools_game_manager import NativeRacingGameManager
        need(type(checkpoint) is DynamicCheckpointPorts and type(tester) is FormalCount14Tester and
             type(consumer) is RacingSharedPublicTests and type(manager) is NativeRacingGameManager,
             'RACING_HOST_CHECKPOINT_EXACT_ORIGINAL_AND_COLD_PORT_TYPES')
        core,t=checkpoint.core,checkpoint.t
        need(t in core.gate.startup_held and checkpoint.state=='BOUND_MODELS_HELD' and
             core.rows[t]['arm']=='DYNTEAM_RACING' and not core.qualification_only and
             core.smoke_checkpoint_ports[t] is checkpoint and
             tester.core is consumer.core is manager.core is core and tester.t==consumer.t==manager.t==t and
             consumer.manager is manager and consumer.tester is tester and
             tester.state=='TASK_AWARE_NATIVE_CYCLE0_READY_MODELS_HELD' and
             manager.helper_index==8 and not manager.games and not manager.failure and
             not hasattr(checkpoint,'scientific_host_checkpoint'),
             'RACING_HOST_CHECKPOINT_INSTALL_ONLY_NEW_HELD_SAME_PREPARED_GRAPH')
        self.checkpoint,self.core,self.t=checkpoint,core,t
        self.tester,self.consumer,self.manager=tester,consumer,manager
        self.original_step=checkpoint.step;self.original_bridge=checkpoint._bridge
        self.original_control=checkpoint._bridge_control
        self.held=False;self.captures={};self.current_capture=None
        checkpoint.scientific_host_checkpoint=self
        # Instance-local cold ports only; source/global/class methods stay
        # byte-original, and no existing owner is retrofitted.
        checkpoint.step=MethodType(lambda own:self.step(),checkpoint)
        checkpoint._bridge=MethodType(lambda own,destination,exports:self.bridge(destination,exports),checkpoint)
        checkpoint._bridge_control=MethodType(lambda own:self.control(),checkpoint)

    def outside_locks(self):
        need(not self.core.ledger.mutex._is_owned(),
             'RACING_HOST_CHECKPOINT_NO_IO_OR_WAIT_UNDER_SCIENCE_LOCK')

    def hold(self):
        self.outside_locks()
        need(self.consumer.failure is None and self.tester.state not in
             ('INITIAL_EXPORT_PARTIAL_RETAINED','CYCLE_PARTIAL_RETAINED_NO_RETRY'),
             'RACING_HOST_WRITER_PARTIAL_RETAINED_NO_RETRY')
        if not self.held:
            self.consumer.request_checkpoint_hold()
            self.tester.checkpoint_hold()
            self.held=True
        self.consumer.poll() # normal reap of ONLY its already-started metadata RPC
        return self.tester.physical_clear() and self.consumer.checkpoint_ready()

    def step(self):
        self.outside_locks();checkpoint=self.checkpoint
        previous=checkpoint.state
        if previous in ('BOUND_MODELS_HELD','RUNNING') and self.core.ledger.frontier(self.t)['state']=='DRAINING':
            if not self.hold():return checkpoint.public()
            # Last fresh HOLD before original whole-domain freeze. Nothing
            # here starts/stops a Game or waits on any scientific guest future.
            self.manager._control(force=True)
        if previous=='RELEASING':
            # A long COMMITTED cut can exceed guest control's wall TTL. Refresh
            # metadata BEFORE original thaw, not via a second model/dispatcher.
            self.manager._control(force=True)
        value=self.original_step()
        if previous=='RELEASING' and checkpoint.state=='RUNNING':
            need(self.held and self.tester.physical_clear() and self.consumer.checkpoint_ready(),
                 'RACING_HOST_RESUME_ONLY_SAME_DRAINED_RETAINED_WRITERS')
            self.tester.resume_after_cut();self.consumer.resume_after_original_cut()
            self.held=False;self.current_capture=None
        return value

    def roots(self):
        self.outside_locks()
        need(self.held and self.tester.physical_clear() and self.consumer.checkpoint_ready(),
             'RACING_HOST_CAPTURE_ONLY_AFTER_EXTRA_HOST_WRITERS_DRAINED')
        root=Path(self.core.rows[self.t]['root'])
        unique=[]
        for path in (*self.tester.capture_roots(),*self.consumer.capture_roots()):
            path=Path(path)
            need(path.resolve()==path and path.is_dir() and not path.is_symlink() and
                 path!=root and path.is_relative_to(root),
                 'RACING_HOST_ONLY_EXACT_NEW_TRAJECTORY_SUBDIRECTORIES')
            if path not in unique:unique.append(path)
        # Capture nested leaves once, without eliding any of their content.
        return tuple(path for path in unique if not any(path!=parent and path.is_relative_to(parent)
                                                       for parent in unique))

    def bridge(self,destination,exports):
        self.outside_locks();cut=self.checkpoint.writer.cut;key=cut.cut_sha
        need(key not in self.captures and self.current_capture is None,
             'RACING_HOST_CAPTURE_ONCE_NO_PREFIX_RETRY')
        record={'schema':'count14-native-host-writer-cut-sidecar-v1','trajectory':self.t,
            'cut_sha256':key,'state':'CAPTURE_INTENT_RETAIN_ON_FAILURE',
            'same_live_only':True,'cold_SDK_restore_claimed':False}
        self.captures[key]=record
        try:
            objects={str(path):cut.cas.capture_tree(path) for path in self.roots()}
            record.update(state='CAPTURED',root_objects=objects,
                          original_metadata_publisher=self.consumer.public())
            self.current_capture=copy.deepcopy(record)
            record['sidecar_sha256']=digest(self.current_capture)
            self.current_capture=copy.deepcopy(record)
            # Original _bridge now includes these CAS references in BOTH
            # before/after control equality and original bridge_journal backup.
            return self.original_bridge(destination,exports)
        except BaseException:
            record['state']='PARTIAL_RETAINED_NO_RETRY'
            raise

    def control(self):
        result=self.original_control()
        need(type(result) is dict and 'scientific_host_writers' not in result,
             'RACING_HOST_ORIGINAL_CONTROL_UNAMBIGUOUS_NEW_SIDECAR')
        result['scientific_host_writers']=copy.deepcopy(self.current_capture)
        return result


def install_host_writer_checkpoint(checkpoint,*,tester,consumer,manager):
    return ScientificHostCheckpoint(checkpoint,tester=tester,consumer=consumer,manager=manager)
