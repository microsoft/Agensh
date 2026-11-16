"""Cold-only, PINNED real native bridge/session call-site integration.

No live source is patched. Actual guard is inserted before watcher socket EOF,
before end_child cancellation, before native cleanup and immediately after
real Popen. Only normal TERM of the registered child group remains; no cancel,
SIGKILL, broad UID scan or shared host action. All other science remains native.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from common import need
from native_beta_layout import racing_bridge_role_delta


def bridge_delta(raw):
    original = ast.parse(raw)
    tree = ast.parse(racing_bridge_role_delta(raw))
    server = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'serve_connection')
    stop = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'stop_turn_processes')
    shutdown = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'shutdown')
    position = next(i for i, n in enumerate(tree.body) if isinstance(n, ast.ImportFrom) and n.module == 'worker_session')
    tree.body[position:position] = ast.parse('from native_bridge_client import bridge_lifecycle\n'
                                          '_count14_lifecycle = bridge_lifecycle()\n').body
    startup = [n for n in ast.walk(tree) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and
               isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='finish' and
               n.value.args and isinstance(n.value.args[0],ast.Name) and n.value.args[0].id=='recovery']
    need(len(startup)==1,'DYNTEAM_NATIVE_ONE_STARTUP_RECOVERY_SITE')
    startup[0].value=ast.parse('_count14_lifecycle.preserve_startup(turn_state, recovery)',mode='eval').body
    stop.body = ast.parse('return _count14_lifecycle.stop_normal(proc)').body
    # Closing the listening socket prevents new clients, but accepted clients
    # and their paid model stacks are left to the guarded original watcher.
    shutdown.body = ast.parse('bridge_stopping.set()\n'
                              'try:\n    server.close()\nexcept OSError:\n    pass\n').body
    # Birth hook before input/stop/prompt locks or transport threads exist.
    birth_at = next(i for i, n in enumerate(server.body) if isinstance(n, ast.Assign) and
                    any(isinstance(t, ast.Name) and t.id == 'end_reason' for t in n.targets))
    server.body.insert(birth_at, ast.parse('_count14_lifecycle.born(proc, identity, turn)').body[0])
    end = next(n for n in server.body if isinstance(n, ast.FunctionDef) and n.name == 'end_child')
    end.body = ast.parse('nonlocal end_reason\n'
        '_count14_lifecycle.before_end(proc)\n'
        'with stop_lock:\n'
        '    if stopping.is_set():\n        return\n'
        '    stopping.set()\n'
        '    if bridge_stopping.is_set() and end_reason == "disconnect":\n        end_reason = "shutdown"\n'
        'stop_turn_processes(proc)\n'
        'with input_lock:\n'
        '    try:\n        proc.stdin.close()\n'
        '    except (BrokenPipeError, OSError):\n        pass\n').body
    watcher = next(n for n in server.body if isinstance(n, ast.FunctionDef) and n.name == 'watch_session')
    loop = next(n for n in watcher.body if isinstance(n, ast.While))
    chooser = next(n for n in loop.body if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == 'is_tester')
    pos = loop.body.index(chooser)
    loop.body[pos] = ast.If(test=ast.parse('bridge_stopping.is_set()',mode='eval').body,
        body=ast.parse('reason = "shutdown"').body, orelse=[chooser])
    reason = next(n for n in loop.body if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == 'reason')
    record_at = next(i for i, n in enumerate(reason.body) if isinstance(n, ast.Expr) and
                     isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) and n.value.func.id == 'record_session_end')
    reason.body.insert(record_at, ast.parse('_count14_lifecycle.before_end(proc)').body[0])
    # Successful original archive/cleanup must precede the terminal receipt.
    finish = [n for n in ast.walk(server) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and
              isinstance(n.value.func, ast.Attribute) and isinstance(n.value.func.value, ast.Name) and
              n.value.func.value.id == 'turn_state' and n.value.func.attr == 'finish']
    need(len(finish) == 2, 'DYNTEAM_NATIVE_REAL_FINISH_TWO_SITES')
    final = next(n for n in finish if len(n.value.args) == 2 and isinstance(n.value.args[1], ast.Name))
    containers = [n for n in ast.walk(server) if hasattr(n,'body') and isinstance(n.body,list) and final in n.body]
    need(len(containers) == 1, 'DYNTEAM_NATIVE_FINISH_CONTAINING_BRANCH')
    body = containers[0].body
    body.insert(body.index(final)+1, ast.parse('_count14_lifecycle.archived(proc, identity, turn, end_reason)').body[0])
    ast.fix_missing_locations(tree)
    text = '#!/usr/bin/env python3\n' + ast.unparse(tree)+'\n'
    compile(text,'count14-cold-guarded-acp-bridge.py','exec')
    need('session/cancel' not in text and 'SIGKILL' not in text and "Path('/proc').iterdir" not in text,
         'DYNTEAM_NATIVE_BRIDGE_NO_CANCEL_KILL_OR_GLOBAL_SCAN')
    # Every untouched top-level function retains the exact original AST.
    changed = {'stop_turn_processes','serve_connection','shutdown'}
    after = {n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    for n in original.body:
        if isinstance(n,ast.FunctionDef) and n.name not in changed:
            need(ast.dump(n,include_attributes=False)==ast.dump(after[n.name],include_attributes=False),
                 'DYNTEAM_NATIVE_UNTOUCHED_FUNCTION_BODY_PRESERVED')
    return text


def session_delta(raw):
    tree = ast.parse(raw)
    cls = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='TurnState')
    fn = next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_finish')
    calls = [n for n in fn.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and
             isinstance(n.value.func,ast.Name) and n.value.func.id=='seal']
    need(len(calls)==1,'DYNTEAM_NATIVE_ONE_ARCHIVE_SEAL_SITE')
    at=fn.body.index(calls[0])+1
    fn.body[at:at]=ast.parse('from native_bridge_client import bridge_lifecycle\n'
                            'bridge_lifecycle().before_cleanup(turn, reason)\n').body
    ast.fix_missing_locations(tree)
    result=ast.unparse(tree)+'\n'
    compile(result,'count14-cold-guarded-worker-session.py','exec')
    return result


def build(source_root, destination, *, expected):
    source_root,destination=Path(source_root),Path(destination)
    need(not destination.exists() and set(expected)=={'acp-bridge.py','worker_session.py'},
         'DYNTEAM_NEW_COLD_NATIVE_OVERLAY_ONLY')
    sources={}
    for name,pin in expected.items():
        path=source_root/name;raw=path.read_bytes()
        need(not path.is_symlink() and hashlib.sha256(raw).hexdigest()==pin,'DYNTEAM_EXACT_NATIVE_BRIDGE_SOURCE_PIN')
        sources[name]=raw.decode()
    result={'acp-bridge.py':bridge_delta(sources['acp-bridge.py']),
            'worker_session.py':session_delta(sources['worker_session.py'])}
    destination.mkdir(mode=0o700)
    for name,text in result.items():
        (destination/name).write_text(text)
        (destination/name).chmod(0o755 if name=='acp-bridge.py' else 0o644)
    return {name:hashlib.sha256(text.encode()).hexdigest() for name,text in result.items()}
