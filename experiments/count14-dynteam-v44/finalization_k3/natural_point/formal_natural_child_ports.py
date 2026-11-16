"""CURRENT queue/allowance ports then natural, not a bypass or new reader."""
from pathlib import Path
import os
from formal_natural_scope import augment_scope


def parent():
    name=Path(os.environ['COUNT14_NATURAL_PARENT_CHILD']).name
    if name=='queue_child.py':import queue_native as module
    elif name=='allowance_final_child.py':import allowance_native as module
    else:raise ValueError('FORMAL_NATURAL_EXACT_ORIGINAL_ALLOWANCE_CHILD_PORTS')
    return module


def native_ports(reader=None):return parent().native_ports(reader)


def bind_scope(scope,reader=None):return augment_scope(parent().bind_scope(scope,reader))
