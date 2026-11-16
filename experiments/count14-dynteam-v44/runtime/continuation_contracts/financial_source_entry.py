#!/usr/bin/env python3
"""Original current entry, plus one explicit metadata-only no-argument op."""
from pathlib import Path
import hashlib
import importlib.util
import json

PIN = 'aa4fccdb0779bec30116c44765b0eb51ee576701784aaa6d51520f9856c233f8'
OP = 'PUBLISH_NORMAL_INERT_FINANCIAL_CONTROLS'


def parent():
    path = Path(__file__).resolve().parents[1] / 'formal100m-normal-inert-source-cold-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/normal_inert_source_entry.py'
    if path.resolve() != path or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != PIN:
        raise ValueError('FINANCIAL_SOURCE_ORIGINAL_SHARED_ENTRY_PIN')
    spec = importlib.util.spec_from_file_location('count14_financial_source_shared_entry', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def private_namespace(original):
    shared = parent().private_namespace(original)
    namespace = vars(shared); previous = namespace['command']

    def command(row):
        if type(row) is dict and row.get('op') == OP:
            if set(row) != {'op'}:
                raise ValueError('FINANCIAL_SOURCE_ONLY_EXACT_NO_ARGUMENT_OPCODE')
            owner = namespace['RETAINED_OWNER']
            if owner is None:
                raise ValueError('FINANCIAL_SOURCE_SAME_RETAINED_OWNER_REQUIRED')
            from financial_source_cold import publish
            return publish(owner)
        return previous(row)

    namespace['command'] = command
    shared._financial_source_previous_command = previous
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
                               function=tb.tb_frame.f_code.co_name))
            tb = tb.tb_next
        print(json.dumps(dict(PUBLIC_code='FINANCIAL_SOURCE_COLD_ENTRY_REFUSED',
                              exception_type=type(error).__name__, locations=frames,
                              message_or_private_body_exported=False), sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
