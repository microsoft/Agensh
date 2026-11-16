"""Compile original authorized raw4 control-table ports; DO NOT install them.

No SQL is executed by this module or its factory. ROOT explicitly retained
actual table creation/installation for a separately authorized cold boundary.
The seven historical ALLOWED pairs and their authorization are NOT imported.
"""
from types import FunctionType,SimpleNamespace
import inspect
from common import need,digest
import final_attempts,final_queue
from formal_ast import globals_clone

TABLE='aux_stall_exempt_replacement_jobs'


def compile_original_raw4_queue_ports(kernels):
    # One private shared original-function global dictionary. No mutation of
    # the original final_attempts module or any other queue instance.
    space=dict(vars(final_attempts))
    for name,value in list(space.items()):
        if inspect.isfunction(value)and value.__module__==final_attempts.__name__:
            clone=FunctionType(value.__code__,space,value.__name__,value.__defaults__,value.__closure__)
            clone.__kwdefaults__=value.__kwdefaults__;space[name]=clone
    private=SimpleNamespace(**space)
    original_installer=globals_clone(kernels.raw4_install,A=private,TABLE=TABLE)
    def forbidden_install(*_args,**_kwargs):
        need(False,'FORMAL_ALLOWANCE_RAW4_COLD_INSTALL_NOT_AUTHORIZED_IN_THIS_WIP')
    # Compile/link every existing ORIGINAL queue control path. Do not construct
    # a q, call the original installer or make any new table/job.
    candidate=globals_clone(final_queue._claim_candidate,attempts=private)
    methods={name:globals_clone(getattr(final_queue.FinalQueue,name),attempts=private,
        _claim_candidate=candidate)for name in('_job','claim','attach','reap','complete','frontier')}
    return SimpleNamespace(table=TABLE,methods=methods,candidate=candidate,
        original_install_body=original_installer,install=forbidden_install,
        original_SQL_schema_reused_verbatim=True,actual_install_executed=False,
        original_attempts_namespace=private,original_source_sha256=kernels.source_sha256['raw4'],
        above4_required_delta=dict(implemented=False,
            exact_site='original aux_allowance.install_queue CREATE TABLE attempt INTEGER CHECK(attempt=4)',
            required_change='a separately approved additive CONTROL attempt domain for authenticated raw ordinal>4; never allowance from ordinal',
            financial_Ledger_schema_or_fee_change_required=False))


def readonly_queue_rows(control,queue,*,effective):
    """One same-scope readonly port for terminal producer/reader/close.

    Current qualified domain is original1..3 ONLY. Never silently omit a new
    additive job table: an unregistered/unfinished domain is an explicit WAIT.
    Future raw4 installation must register one private domain for BOTH methods.
    """
    from allowance_control import FormalAllowanceControl
    need(type(control)is FormalAllowanceControl and queue is control.core.queue and
         type(queue)is final_queue.FinalQueue,'FORMAL_ALLOWANCE_EXACT_SAME_QUEUE_READ_PORT')
    control.fresh()
    with queue.mutex:
        tables=queue.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        required={'id','point','replicate','state','claim','child','terminal','result'}
        for item in tables:
            name=item[0]
            need(type(name)is str and __import__('re').fullmatch('[A-Za-z_][A-Za-z0-9_]*',name),
                 'FORMAL_ALLOWANCE_FIXED_CONTROL_TABLE_NAME')
            columns={r[1]for r in queue.db.execute('PRAGMA table_info("'+name+'")')}
            if required<=columns:
                need(name in('jobs','replacement_jobs'),'FORMAL_ALLOWANCE_UNREGISTERED_NATIVE_JOB_DOMAIN_WAIT')
        return (final_attempts.effective_rows if effective else final_attempts.all_rows)(queue)
