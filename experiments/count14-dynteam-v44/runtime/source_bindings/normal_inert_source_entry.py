#!/usr/bin/env python3
"""Same actual original entry namespace, explicit no-argument INERT source op."""
from pathlib import Path
import hashlib
import importlib.util
import json

PIN='13be56f0191ca05a42f2df22f98858c89e32d13d8141b3c127a65eb665fc4cbd'
OP='ISSUE_NORMAL_INERT_SOURCE_TICKET'


def parent():
    p=Path(__file__).resolve().parents[1]/'formal100m-complete-source-control-cold-wip-v3-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/complete_source_entry.py'
    if p.resolve()!=p or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=PIN:
        raise ValueError('NORMAL_INERT_SOURCE_ORIGINAL_SHARED_ENTRY_PIN')
    spec=importlib.util.spec_from_file_location('count14_normal_inert_source_shared_entry',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def private_namespace(original):
    shared=parent().private_namespace(original)
    namespace=vars(shared);previous=namespace['command']
    def command(row):
        if type(row) is dict and row.get('op')==OP:
            if set(row)!={'op'}:raise ValueError('NORMAL_INERT_SOURCE_ONLY_EXACT_NO_ARGUMENT_OPCODE')
            owner=namespace['RETAINED_OWNER']
            if owner is None:raise ValueError('NORMAL_INERT_SOURCE_SAME_RETAINED_OWNER_REQUIRED')
            from normal_inert_source_cold import issue
            return issue(owner)
        return previous(row)
    namespace['command']=command
    shared._inert_source_previous_command=previous;shared._inert_source_op=OP
    return shared


def original_entry():return parent().original_entry()


def main(argv=None):
    try:return private_namespace(original_entry()).main(argv)
    except Exception as error:
        frames=[];tb=error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,
                function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='NORMAL_INERT_SOURCE_ENTRY_REFUSED',exception_type=type(error).__name__,
            locations=frames,model_activity_observed_by_error_report=False,
            financial_or_request_counts_inferred=False),sort_keys=True));return 2


if __name__=='__main__':raise SystemExit(main())
