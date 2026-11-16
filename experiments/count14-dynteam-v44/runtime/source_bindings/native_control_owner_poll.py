"""One original-owner native-control tail plus its same-graph guest queue.

No additional thread, dispatcher, timer, science action or source mutation.
Only use while the separately qualified original cold graph remains HELD.
"""
import native_control_host_restore as R
from native_peer_registry import process_birth
import paid_cold_material as M


def poll_registered_native_controls(graph,*,read_budget):
 runtime=R.current_native_controls(graph)
 total=runtime.poll_once(read_budget=read_budget)
 # The original native tail already consumes publisher once. Calling the
 # guest wrapper's graph.poll_metadata_once here would consume it twice.
 plan=graph.guest_plan_control
 from new_owner_sdk_plan_control import NewOwnerGuestPlanControl
 M.need(type(plan)is NewOwnerGuestPlanControl and plan.graph is graph and
  plan.owner==process_birth(__import__('os').getpid()),'NATIVE_RESTORE_SAME_NEW_GUEST_CONTROL_NOT_ANOTHER_DISPATCHER')
 return total+plan.poll_once()
