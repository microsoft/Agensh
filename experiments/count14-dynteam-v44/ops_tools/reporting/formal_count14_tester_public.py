"""Task-aware tester's non-reference public execution, scientific runtime only.

Keep the existing original SDK/Docker/UID10000 runner, result ABI, physical
custody, deadlines and no-replay methods byte-identical. Only the constructor's
new-arm/tester registration scope and per-slot custody leaf differ privately.
No global class, old arm, accounting code or live source is patched.
"""
from __future__ import annotations

from pathlib import Path
from types import MethodType
import ast
import copy
import inspect
import textwrap
import threading

from common import need
from count14_public_racing_judge import NativePublicProbePort, Count14PublicRacingJudge
from smoke_racing_tools_public_exec import NativePublicDockerExec, PublicProgramBinding


def native_tester_public_exec(core, *, binding, scope, existing_cases, active_now):
    """One actual tester+slot binding through the original public-tool runtime.

    Programs are explicit scientific PUBLIC /work executables, not guessed
    official oracle paths. Factory must mount the same pinned runner read-only
    and enroll these original execs in its real physical writer custody.
    """
    need(type(binding) is PublicProgramBinding and binding.role == 'tester-00' and
         core.rows[binding.trajectory_id]['arm'] in ('DYNTEAM', 'DYNTEAM_RACING'),
         'DYNTEAM_FORMAL_TESTER_EXACT_PUBLIC_BINDING')
    original = NativePublicDockerExec.__init__
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    prior = copy.deepcopy(tree)
    changes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1:
            if isinstance(node.ops[0], ast.Eq) and isinstance(node.comparators[0], ast.Constant) and node.comparators[0].value == 'DYNTEAM_RACING':
                changes.append((node, copy.deepcopy(node)))
                node.ops[0] = ast.In()
                node.comparators[0] = ast.Tuple(elts=[ast.Constant('DYNTEAM'), ast.Constant('DYNTEAM_RACING')], ctx=ast.Load())
            elif (isinstance(node.ops[0], ast.In) and isinstance(node.left, ast.Attribute) and
                  isinstance(node.left.value, ast.Name) and node.left.value.id == 'binding' and node.left.attr == 'role' and
                  isinstance(node.comparators[0], ast.Set) and
                  {getattr(value, 'value', None) for value in node.comparators[0].elts} ==
                  {'tester-00', 'racing-background-00'}):
                changes.append((node, copy.deepcopy(node)))
                node.ops[0] = ast.Eq()
                node.comparators[0] = ast.Constant('tester-00')
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Attribute) and node.targets[0].attr == 'home':
            changes.append((node, copy.deepcopy(node)))
            node.value = ast.parse("Path(core.rows[binding.trajectory_id]['root'])/'tester-public-exec-private'/str(binding.task_slot)", mode='eval').body
    need(len(changes) == 3, 'DYNTEAM_FORMAL_TESTER_THREE_CONSTRUCTOR_SCOPE_SITES')
    restored = copy.deepcopy(tree)
    for target, old in changes:
        matches = [node for node in ast.walk(restored) if type(node) is type(target) and
                   ast.dump(node, include_attributes=False) == ast.dump(target, include_attributes=False)]
        need(len(matches) == 1, 'DYNTEAM_FORMAL_TESTER_CONSTRUCTOR_SCOPE_RESTORE_UNIQUE')
        matches[0].__dict__.update(copy.deepcopy(old.__dict__))
    need(ast.dump(restored, include_attributes=False) == ast.dump(prior, include_attributes=False),
         'DYNTEAM_FORMAL_TESTER_NO_EXEC_CUSTODY_RESULT_OR_MODEL_DELTA')
    home = Path(core.rows[binding.trajectory_id]['root']) / 'tester-public-exec-private'
    if not home.exists():
        home.mkdir(mode=0o700)
    need(home.resolve() == home and not home.is_symlink() and home.is_dir(),
         'DYNTEAM_FORMAL_TESTER_ONLY_NEW_CUSTODY_PARENT')
    namespace = dict(original.__globals__)
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':private-native-constructor', 'exec'), namespace)
    # Reuse the ORIGINAL runtime's actual execution methods. This private
    # instance cannot loosen its frozen Docker mount/birth/cgroup checks.
    instance = NativePublicDockerExec.__new__(NativePublicDockerExec)
    MethodType(namespace['__init__'], instance)(core, binding=binding, scope=scope,
        existing_cases=existing_cases, active_now=active_now)
    need(NativePublicDockerExec.__init__ is original,
         'DYNTEAM_FORMAL_TESTER_ORIGINAL_PUBLIC_CLASS_UNCHANGED')
    return instance


class TesterPublicExecution:
    """Native per-slot public cases, not ProgramBench/private-reference scores.

    A genuinely absent program binding stays PUBLIC_EXECUTION_PORT_PENDING;
    no fabricated pass, empty suite success or official count14 verdict. Tests
    and generation still run via their charged native tester sessions.
    """
    def __init__(self, *, ports, active_now):
        need(type(ports) is dict and all(type(slot) is int and 1 <= slot <= 14 and
             type(port) is NativePublicProbePort for slot, port in ports.items()) and callable(active_now),
             'DYNTEAM_FORMAL_TESTER_TYPED_NATIVE_PUBLIC_PORTS')
        self.ports = dict(ports)
        self.active_now = active_now
        self.judges = {slot: Count14PublicRacingJudge(port, active_now=active_now)
                       for slot, port in ports.items()}
        self.attempted = set()
        self.partial = False
        self.lock = threading.Lock()
        self.busy = False

    def register_slot(self, slot, port):
        """Native runtime may bind a newly built PUBLIC program between cycles.

        Registration does not redispatch any old case/release. Missing slots
        are not an excuse to create fake programs or reference executables.
        The parent registers only the real owner/slot/container-bound port.
        """
        need(type(slot) is int and 1 <= slot <= 14 and type(port) is NativePublicProbePort,
             'DYNTEAM_FORMAL_TESTER_REGISTER_TYPED_PUBLIC_SLOT')
        port.scope.checked()
        with self.lock:
            need(not self.busy and slot not in self.ports,
                 'DYNTEAM_FORMAL_TESTER_PUBLIC_SLOT_BETWEEN_CYCLES_ONCE')
            self.ports[slot] = port
            self.judges[slot] = Count14PublicRacingJudge(port, active_now=self.active_now)

    def evaluate(self, number, cases):
        need(type(number) is int and number > 0 and number not in self.attempted and
             type(cases) is tuple and len({(slot, name) for slot, name, _ in cases}) == len(cases),
             'DYNTEAM_FORMAL_TESTER_PUBLIC_RELEASE_ONCE')
        with self.lock:
            need(not self.busy and number not in self.attempted,
                 'DYNTEAM_FORMAL_TESTER_PUBLIC_RELEASE_SERIAL_ONCE')
            self.attempted.add(number)
            self.busy = True
            judges = dict(self.judges)
        output = []
        try:
            for slot, name, directory in cases:
                need(type(slot) is int and 1 <= slot <= 14 and type(name) is str and Path(directory).is_dir(),
                     'DYNTEAM_FORMAL_TESTER_PUBLIC_CASE_EXACT_SLOT')
                judge = judges.get(slot)
                if judge is None:
                    output.append(dict(slot=slot, case_id=name, valid=False, fail=False,
                        code='PUBLIC_EXECUTION_PORT_PENDING', official_verdict=False))
                    continue
                result = judge.judge(directory, budget_s=120)
                output.append(dict(slot=slot, case_id=name, valid=result['valid'], fail=result['fail'],
                    signature=result['signature'], code=result.get('error', 'PUBLIC_EXECUTION_OBSERVED'),
                    pending=result.get('pending', False), official_verdict=False))
        finally:
            with self.lock:
                self.busy = False
        self.partial = any(row.get('pending') is True for row in output)
        return dict(schema='count14-native-tester-public-observations-v1', release=number,
            observations=output, total=len(output), valid=sum(r['valid'] for r in output),
            reproduced_public_failures=sum(r['valid'] and r['fail'] for r in output),
            official_verdict=False, private_reference_used=False,
            empty_suite_not_success=not output, model_calls_by_host=0)

    def physical_clear(self):
        with self.lock:
            if self.busy:
                return False
            judges = tuple(self.judges.values())
        return all(judge.physical_clear() for judge in judges)
