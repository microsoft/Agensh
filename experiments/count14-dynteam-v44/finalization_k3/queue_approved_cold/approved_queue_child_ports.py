"""Original current queue scope/config/header plus approved reader and natural."""
from formal_ast import globals_clone
from formal_natural_scope import augment_scope
from approved_queue_binding import approved_native_ports
import queue_native


def native_ports(reader=None):return approved_native_ports(reader)


def bind_scope(scope,reader=None):
    value=globals_clone(queue_native.bind_scope,native_ports=approved_native_ports)(scope,reader)
    return augment_scope(value)
