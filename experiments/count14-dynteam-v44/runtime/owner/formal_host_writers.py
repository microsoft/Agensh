"""Formal tester and optional original RACING publication host-writer custody.

Only host writer serialization/control sidecar differs. Original model drain,
membership, whole guest/work freeze, snapshot COMMIT, collection, K3 and resume
are still the exact DynamicCheckpointPorts methods. No Game-round drain gate.
"""
from pathlib import Path
from types import MethodType
import copy

from common import need, digest
from native_dynamic_checkpoint import DynamicCheckpointPorts
from formal_count14_tester import FormalCount14Tester
from formal_scope import validate_contract


class FormalHostWriters:
    def __init__(self, checkpoint, *, tester, consumer=None, manager=None):
        need(type(checkpoint) is DynamicCheckpointPorts and type(tester) is FormalCount14Tester,
             'FORMAL_HOST_EXACT_ORIGINAL_CHECKPOINT_AND_NATIVE_TESTER')
        core, t = checkpoint.core, checkpoint.t
        validate_contract(core.contract, digest(core.contract))
        need(not core.qualification_only and t in core.gate.startup_held and
             core.formal_checkpoint_ports[t] is checkpoint and checkpoint.state == 'BOUND_MODELS_HELD' and
             tester.core is core and tester.t == t and
             tester.state == 'TASK_AWARE_NATIVE_CYCLE0_READY_MODELS_HELD' and
             not hasattr(checkpoint, 'formal_host_writers'),
             'FORMAL_HOST_INSTALL_ONLY_TRUE_COLD_TASK_READY_GRAPH')
        if core.rows[t]['arm'] == 'DYNTEAM_RACING':
            from native_racing_shared_tests import RacingSharedPublicTests
            from smoke_racing_tools_game_manager import NativeRacingGameManager
            need(type(consumer) is RacingSharedPublicTests and type(manager) is NativeRacingGameManager and
                 consumer.core is manager.core is core and consumer.t == manager.t == t and
                 consumer.manager is manager and consumer.tester is tester and manager.helper_index == 8 and
                 not manager.games and manager.failure is None,
                 'FORMAL_HOST_TRUE_EIGHT_PREPARED_HELPERS_AND_ORIGINAL_CONSUMER')
        else:
            need(consumer is None and manager is None, 'FORMAL_BASELINE_HAS_NO_FAKE_RACING_COMPONENTS')
        self.checkpoint, self.core, self.t = checkpoint, core, t
        self.tester, self.consumer, self.manager = tester, consumer, manager
        self.original_step, self.original_bridge, self.original_control = checkpoint.step, checkpoint._bridge, checkpoint._bridge_control
        self.held, self.current_capture, self.captures = False, None, {}
        checkpoint.formal_host_writers = self
        checkpoint.step = MethodType(lambda own: self.step(), checkpoint)
        checkpoint._bridge = MethodType(lambda own, destination, exports: self.bridge(destination, exports), checkpoint)
        checkpoint._bridge_control = MethodType(lambda own: self.control(), checkpoint)

    def outside_locks(self):
        need(not self.core.ledger.mutex._is_owned(), 'FORMAL_HOST_NO_IO_OR_WAIT_UNDER_SCIENCE_LOCK')

    def consumer_clear(self):
        return self.consumer is None or self.consumer.checkpoint_ready()

    def hold(self):
        self.outside_locks()
        need(self.tester.state not in ('INITIAL_EXPORT_PARTIAL_RETAINED', 'CYCLE_PARTIAL_RETAINED_NO_RETRY') and
             (self.consumer is None or self.consumer.failure is None), 'FORMAL_HOST_PARTIAL_RETAIN_NO_RETRY')
        if not self.held:
            self.tester.checkpoint_hold()
            if self.consumer is not None:
                self.consumer.request_checkpoint_hold()
            self.held = True
        if self.consumer is not None:
            self.consumer.poll()  # only reaps an already-started original RPC
        return self.tester.physical_clear() and self.consumer_clear()

    def step(self):
        self.outside_locks()
        previous = self.checkpoint.state
        if previous in ('BOUND_MODELS_HELD', 'RUNNING') and self.core.ledger.frontier(self.t)['state'] == 'DRAINING':
            if not self.hold():
                return self.checkpoint.public()
            if self.manager is not None:
                self.manager._control(force=True)
        if previous == 'RELEASING' and self.manager is not None:
            self.manager._control(force=True)  # fresh HOLD before original thaw
        result = self.original_step()
        if previous == 'RELEASING' and self.checkpoint.state == 'RUNNING':
            need(self.held and self.tester.physical_clear() and self.consumer_clear(),
                 'FORMAL_HOST_RESUME_ONLY_SAME_DRAINED_WRITERS')
            self.tester.resume_after_cut()
            if self.consumer is not None:
                self.consumer.resume_after_original_cut()
            self.held, self.current_capture = False, None
        return result

    def roots(self):
        self.outside_locks()
        need(self.held and self.tester.physical_clear() and self.consumer_clear(),
             'FORMAL_HOST_CAPTURE_AFTER_TRUE_HOST_DRAIN_ONLY')
        root = Path(self.core.rows[self.t]['root'])
        paths = (*self.tester.capture_roots(), *(self.consumer.capture_roots() if self.consumer is not None else ()))
        unique = []
        for path in paths:
            path = Path(path)
            need(path.resolve() == path and path.is_dir() and not path.is_symlink() and
                 path != root and path.is_relative_to(root), 'FORMAL_HOST_EXACT_NEW_TRAJECTORY_ROOTS_ONLY')
            if path not in unique:
                unique.append(path)
        return tuple(path for path in unique if not any(path != parent and path.is_relative_to(parent) for parent in unique))

    def bridge(self, destination, exports):
        self.outside_locks()
        cut = self.checkpoint.writer.cut
        need(cut.cut_sha not in self.captures and self.current_capture is None,
             'FORMAL_HOST_CAPTURE_ONCE_PRESERVE_FAILED_PREFIX')
        value = dict(schema='count14-formal-native-host-writer-cut-sidecar-v1', trajectory=self.t,
            cut_sha256=cut.cut_sha, state='CAPTURE_INTENT_RETAIN_ON_FAILURE',
            same_live_only=True, cold_SDK_restore_claimed=False)
        self.captures[cut.cut_sha] = value
        try:
            value.update(state='CAPTURED', root_objects={str(path): cut.cas.capture_tree(path) for path in self.roots()},
                         original_metadata_publisher=None if self.consumer is None else self.consumer.public())
            value['sidecar_sha256'] = digest(value)
            self.current_capture = copy.deepcopy(value)
            return self.original_bridge(destination, exports)
        except BaseException:
            value['state'] = 'PARTIAL_RETAINED_NO_RETRY'
            raise

    def control(self):
        result = self.original_control()
        need(type(result) is dict and 'scientific_host_writers' not in result,
             'FORMAL_HOST_ORIGINAL_CONTROL_UNAMBIGUOUS_SIDECAR')
        result['scientific_host_writers'] = copy.deepcopy(self.current_capture)
        return result
