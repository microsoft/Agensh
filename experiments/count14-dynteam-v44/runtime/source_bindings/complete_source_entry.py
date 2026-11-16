#!/usr/bin/env python3
"""Same ONE original entry namespace, two explicit no-argument transport ops."""
from pathlib import Path
import hashlib
import importlib.util
import json

PIN = 'd3c2369d9b30e17e364e59a8f02578fa330e28552bc00a3de300c2aaab6d6e25'
OPS = ('REQUEST_NORMAL_HTTP_TRANSPORT_RETIREMENT', 'POLL_NORMAL_HTTP_TRANSPORT_RETIREMENT')


def parent():
    p = Path(__file__).resolve().parents[1]/'formal100m-normal-cold-sealer-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/normal_cold_entry.py'
    if p.resolve() != p or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != PIN:
        raise ValueError('NORMAL_TRANSPORT_ENTRY_ORIGINAL_SHARED_COLD_ENTRY_PIN')
    spec = importlib.util.spec_from_file_location('count14_transport_current_shared_entry', p)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def private_namespace(original):
    shared = parent().private_namespace(original)
    namespace = vars(shared); preceding_command = namespace['command']
    def command(row):
        if type(row) is dict and row.get('op') in OPS:
            if set(row) != {'op'}:
                raise ValueError('NORMAL_TRANSPORT_ENTRY_ONLY_EXACT_NO_ARGUMENT_OPCODE')
            owner = namespace['RETAINED_OWNER']
            if owner is None:
                raise ValueError('NORMAL_TRANSPORT_ENTRY_SAME_RETAINED_OWNER_REQUIRED')
            from transport_sealer_cold import request, poll
            return request(owner) if row['op'] == OPS[0] else poll(owner)
        return preceding_command(row)
    namespace['command'] = command
    shared._transport_previous_command = preceding_command
    shared._transport_ops = OPS
    return shared


def original_entry():
    return parent().original_entry()


def main(argv=None):
    try:
        return private_namespace(original_entry()).main(argv)
    except Exception as error:
        frames = []; tb = error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                               function=tb.tb_frame.f_code.co_name)); tb = tb.tb_next
        print(json.dumps(dict(PUBLIC_code='NORMAL_TRANSPORT_CHAIN_ENTRY_SOURCE_REFUSED',
            exception_type=type(error).__name__, locations=frames,
            model_activity_observed_by_error_report=False,
            financial_or_request_counts_inferred=False), sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
