"""Host custody of original accepted MCP/Git control connections.

A native business pending map excludes framing before dispatch and delivery
following a physical backend terminal. Keep each original accepted socket until
its original handler has finished and the socket has closed. Never cancel it,
close it on a checkpoint, infer native business completion, or inspect payloads.
A zero snapshot is only LOCAL control quiescence, not application/SQL async drain
or shell/descendant terminal proof. Worker-domain fencing is still necessary.
"""
import socketserver
import threading
from common import need


class NativeAcceptedControls(socketserver.ThreadingMixIn):
    daemon_threads = False
    block_on_close = True

    def __init__(self, *args, control_failure, unmanaged_cli=False, **kwargs):
        need(callable(control_failure), 'CONTROL_CUSTODY_TRUSTED_FAULT_SINK')
        self.unmanaged_cli=unmanaged_cli
        self._control_failure = control_failure
        self._controls = threading.Condition(threading.RLock())
        self._accepted_controls = set()
        self._controls_accepted = 0
        self._controls_closed = 0
        self._control_fault = False
        super().__init__(*args, **kwargs)

    def get_request(self):
        # The same mutex covers accept -> registration. A snapshot cannot fall
        # between OS acceptance and strong registration (process_request would
        # be too late). No peer/body bytes are read here. This is the original
        # socketserver accept, invoked only after listener readiness.
        if self.unmanaged_cli:return super().get_request()
        with self._controls:
            request, address = super().get_request()
            self._accepted_controls.add(request)
            self._controls_accepted += 1
            self._controls.notify_all()
            return request, address

    def _control_unknown(self):
        if self.unmanaged_cli:return
        with self._controls:
            self._control_fault = True
            self._controls.notify_all()
        # Never acquire the ledger while holding _controls: original dispatch
        # uses port -> ledger locks, and checkpoint snapshots may hold both.
        # The local fault remains latched even if metadata storage also fails.
        try:
            self._control_failure('NATIVE_CONTROL_HANDLER_OR_CLOSE_UNKNOWN')
        except BaseException:
            pass

    def handle_error(self, request, client_address):
        # No default socketserver traceback: it can include private payloads.
        if self.unmanaged_cli:return
        self._control_unknown()

    def shutdown_request(self, request):
        if self.unmanaged_cli:return super().shutdown_request(request)
        try:
            super().shutdown_request(request)
            need(request.fileno() == -1, 'CONTROL_CUSTODY_SOCKET_NOT_PHYSICALLY_CLOSED')
        except BaseException:
            # Keep the exact original object strongly retained on ambiguity.
            self._control_unknown()
            return
        with self._controls:
            if request not in self._accepted_controls:
                self._control_fault = True
                unknown = True
            else:
                self._accepted_controls.remove(request)
                self._controls_closed += 1
                unknown = False
            self._controls.notify_all()
        if unknown:
            self._control_unknown()

    def control_snapshot(self, *, require_drained=False,
                         code='NATIVE_CONTROL_ACCEPTED_CONNECTIONS_RETAIN_CUSTODY'):
        if self.unmanaged_cli:return {'mode':'UNMANAGED_NATIVE_NO_TOOL_CUSTODY'}
        with self._controls:
            need(not self._control_fault, 'NATIVE_CONTROL_CUSTODY_UNKNOWN')
            value = {'accepted': self._controls_accepted,
                     'closed': self._controls_closed,
                     'active': len(self._accepted_controls)}
            need(value['accepted'] == value['closed'] + value['active'],
                 'NATIVE_CONTROL_CUSTODY_COUNT_IDENTITY')
            if require_drained:
                need(value['active'] == 0, code)
            return value


def require_control_drained(listener, code):
    """Use the original listener's live keeper, never a caller success boolean."""
    need(isinstance(listener.server, NativeAcceptedControls),
         'NATIVE_CONTROL_ORIGINAL_TRACKED_LISTENER_REQUIRED')
    return listener.server.control_snapshot(require_drained=True, code=code)
