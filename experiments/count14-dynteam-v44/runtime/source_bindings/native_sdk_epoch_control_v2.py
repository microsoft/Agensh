"""Finite plain-Lock source RAM reads for the frozen original control encoder.

V1 capture/normal guards/graph codec stay unchanged. Original domain/session
RAM methods run on per-call read views borrowing the SAME source set/dict; only
their lock context is finite. No source lock/method/data/guard is replaced.
"""
from contextlib import contextmanager
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace
import hashlib
import importlib
import threading

import native_sdk_epoch_control as C
from native_sdk_startup_epochs import NativeSdkStartupEpochs
from formal_full_used_domain import FullUsedDomainProducer
import bounded_metadata_ro as B

SCHEMA='count14-native-sdk-epoch-control-finite-ram-lock-read-v2'
PINS=dict(native_sdk_epoch_control='6a813f5a8726c1d60a54411da8f7a0e477ec9f96a52022235db24b0f3a39bd44',
    dynteam_sessions='c80000d66a4958a3c2d5854d188242806ef305aaee73d2be879571e31c3909dd',
    bounded_metadata_ro='621cd0db6da2d1e6422537f6ae2188ac8466627efe803d8b4d39f260bfb7c249')
_ACTIVE=threading.local()


class EpochControlReadWait(RuntimeError): pass


def need(ok,code):
    if not ok:raise EpochControlReadWait(code)


def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_sources():
    for name,pin in PINS.items():
        p=Path(importlib.import_module(name).__file__)
        need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and file_sha(p)==pin,
             'SDK_EPOCH_V2_FROZEN_ORIGINAL_SOURCE_PIN')
    C.verify_sources()
    top=compile(Path(C.__file__).read_bytes(),C.__file__,'exec',dont_inherit=True)
    codes={c.co_name:c for c in top.co_consts if isinstance(c,CodeType)}
    for name in ('_capture','_registered','_history','capture_registered','capture_OWN_components'):
        fn=getattr(C,name)
        need(fn.__code__==codes[name]and fn.__globals__ is vars(C),
             'SDK_EPOCH_V2_FROZEN_ORIGINAL_CAPTURE_METHOD_CODE')
    return dict(PINS)


def _outside_source_ram():
    need(getattr(_ACTIVE,'count',0)==0,'SDK_EPOCH_V2_NO_IO_WHILE_OWNING_SOURCE_SESSION_OR_DOMAIN_LOCK')


class _FiniteRamLock:
    """One context acquisition, never recursive; actual source is plain Lock."""
    def __init__(self,lock,budget,core,kind):
        need(type(lock)is type(threading.Lock()),'SDK_EPOCH_V2_EXACT_ORIGINAL_PLAIN_LOCK')
        self.lock,self.budget,self.core,self.kind=lock,budget,core,kind
        self.entered=False;self.wait_code=None
    def __enter__(self):
        C._check_budget(self.budget,self.core)
        need(callable(getattr(self.budget,'remaining',None)), 'SDK_EPOCH_V2_FINITE_REMAINING_BUDGET_REQUIRED')
        need(not self.entered,'SDK_EPOCH_V2_NO_RECURSIVE_PLAIN_LOCK_READ')
        timeout=min(.2,self.budget.remaining())
        if not self.lock.acquire(timeout=timeout):
            self.wait_code='SDK_EPOCH_V2_'+self.kind+'_RAM_LOCK_DEADLINE_WAIT'
            raise EpochControlReadWait(self.wait_code)
        self.entered=True;_ACTIVE.count=getattr(_ACTIVE,'count',0)+1
        return self
    def __exit__(self,typ,value,traceback):
        need(self.entered,'SDK_EPOCH_V2_OWN_ACQUIRED_LOCK_CONTEXT_REQUIRED')
        self.entered=False;self.lock.release();_ACTIVE.count-=1
        # All checks/IO after the source lock has been released.
        C._check_budget(self.budget,self.core)
        return False


class _EpochReadPort:
    def __init__(self,original,budget):self.original,self.budget=original,budget
    def __getattr__(self,name):return getattr(self.original,name)
    def _session(self,key):
        source=self.original;track=source.core.sessions.tracks[key[0]]
        lock=_FiniteRamLock(track._lock,self.budget,source.core,'TRACK')
        # Original `_session` code sees the SAME mapping, only a finite context.
        view=SimpleNamespace(core=SimpleNamespace(sessions=SimpleNamespace(tracks={
            key[0]:SimpleNamespace(_lock=lock,_current=track._current)})))
        return NativeSdkStartupEpochs._session(view,key)


class _ProducerReadPort:
    def __init__(self,original,budget,core):self.original,self.budget,self.core=original,budget,core
    def __getattr__(self,name):return getattr(self.original,name)
    def _domain_values(self):
        source=self.original;lock=_FiniteRamLock(source.domain.lock,self.budget,self.core,'DOMAIN')
        # `_domain_values` may latch a diagnostic on its own view; NEVER set
        # source.failure, including when a diagnostic lock deadline expires.
        view=SimpleNamespace(domain=SimpleNamespace(lock=lock,used=source.domain.used),failure=None)
        try:return FullUsedDomainProducer._domain_values(view)
        except Exception:
            if lock.wait_code is not None:raise EpochControlReadWait(lock.wait_code)from None
            C._check_budget(self.budget,self.core)
            raise


def _clone(fn,delta):
    out=FunctionType(fn.__code__,dict(fn.__globals__,**delta),fn.__name__,fn.__defaults__,fn.__closure__)
    out.__kwdefaults__=fn.__kwdefaults__;return out


def _capture_finite(epochs,bridge,producer,*,read_budget):
    verify_sources()
    ep=_EpochReadPort(epochs,read_budget);pp=_ProducerReadPort(producer,read_budget,epochs.core)
    def registered(actual_epochs,actual_bridge,actual_producer,budget):
        need(actual_epochs is ep and actual_bridge is bridge and actual_producer is pp and budget is read_budget,
             'SDK_EPOCH_V2_PRIVATE_RAM_PORT_BINDING')
        # Every V1 exact registered-source type/identity/thread/contract guard
        # executes against the actual originals, never the temporary views.
        return C._registered(epochs,bridge,producer,budget)
    def history(*args,**kwargs):
        _outside_source_ram();result=C._history(*args,**kwargs);_outside_source_ram();return result
    @contextmanager
    def readonly(*args,**kwargs):
        _outside_source_ram()
        with B.readonly(*args,**kwargs)as db:
            _outside_source_ram();yield db;_outside_source_ram()
    capture=_clone(C._capture,dict(_registered=registered,_history=history,B=SimpleNamespace(readonly=readonly)))
    need(capture.__code__ is C._capture.__code__,'SDK_EPOCH_V2_ORIGINAL_CAPTURE_CODE_UNCHANGED')
    # Original producer._operation remains the original NONBLOCKING metadata
    # serial lock. Only its explicit pure RAM reads use the finite read port.
    result=capture(ep,bridge,pp,read_budget=read_budget)
    result['bounded_source_metadata_read']=dict(schema=SCHEMA,adapter_source_sha256=file_sha(__file__),
        source_pins=dict(PINS),source_lock_types=dict(domain='threading.Lock',track='threading.Lock'),
        maximum_single_source_RAM_lock_wait_seconds=.2,
        no_source_lock_replacement_or_recursive_acquire=True,
        same_source_set_and_mapping_original_RAM_code=True,
        source_science_session_domain_lock_held_during_history_file_or_SQL_IO=False)
    return result


def capture_registered(owner,*,read_budget):
    """Drop-in aggregation API; unchanged V1 schema + stable V2 reader section.

    No timestamp/nonce/diagnostic duration is inserted. Not NEW-owner import.
    """
    fn=_clone(C.capture_registered,dict(_capture=_capture_finite))
    return fn(owner,read_budget=read_budget)


def capture_OWN_components(epochs,bridge,producer,*,read_budget):
    fn=_clone(C.capture_OWN_components,dict(_capture=_capture_finite))
    return fn(epochs,bridge,producer,read_budget=read_budget)


def consume_into_NEW_owner(*args,**kwargs):return C.consume_into_NEW_owner(*args,**kwargs)
