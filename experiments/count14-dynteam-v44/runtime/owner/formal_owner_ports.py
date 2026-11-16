"""Private cold constructor/control selectors for the registered formal cohort.

No original class/global/active source is changed. All original startup locks,
source/checkpoint/typed identity/action guards and the same CLAIM launcher are
retained. SDK epochs remain normal fresh-SDK epochs, NOT cold SDK restoration.
"""
from types import MethodType
import ast
import copy
import inspect
import textwrap

from common import need
from native_cold_bootstrap import NativeColdBootstrap
from smoke_bootstrap_task_launch import NativeSameCoreSmokeLaunch


def _compiled(function, edits, namespace=None):
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    prior = copy.deepcopy(tree)
    changes = edits(tree)
    restored = copy.deepcopy(tree)
    for target, old in changes:
        matches = [node for node in ast.walk(restored) if type(node) is type(target) and
            ast.dump(node, include_attributes=False) == ast.dump(target, include_attributes=False)]
        need(len(matches) == 1, 'FORMAL_OWNER_UNIQUE_PRIVATE_INVERSE_SELECTOR')
        matches[0].__dict__.update(copy.deepcopy(old.__dict__))
    need(ast.dump(restored, include_attributes=False) == ast.dump(prior, include_attributes=False),
         'FORMAL_OWNER_ORIGINAL_SCIENTIFIC_ACTION_BODY_UNCHANGED')
    scope = dict(function.__globals__, **(namespace or {}))
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':formal-cold-selector', 'exec'), scope)
    return scope[function.__name__]


def formal_launcher_initializer():
    """Compile only, no owner/asset/launcher action; inverse proof runs now."""
    def edits(tree):
        changes = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1 and
                isinstance(node.ops[0], ast.Eq) and isinstance(node.comparators[0], ast.Constant)):
                if node.comparators[0].value == 'smoke':
                    changes.append((node, copy.deepcopy(node)))
                    node.comparators[0].value = 'production'
                elif node.comparators[0].value == 'DYNTEAM':
                    changes.append((node, copy.deepcopy(node)))
                    node.ops[0] = ast.In()
                    node.comparators[0] = ast.Tuple(elts=[ast.Constant('DYNTEAM'), ast.Constant('DYNTEAM_RACING')],
                                                  ctx=ast.Load())
        need(len(changes) == 2, 'FORMAL_LAUNCHER_EXACT_MODE_AND_ARM_SELECTOR_ONLY')
        return changes
    return _compiled(NativeSameCoreSmokeLaunch.__init__, edits)


def formal_launcher(core, trajectory, source_ports, *, pbench_source):
    result = NativeSameCoreSmokeLaunch.__new__(NativeSameCoreSmokeLaunch)
    formal_launcher_initializer()(result, core, trajectory, source_ports, pbench_source=pbench_source)
    return result


def install_formal_initial_port(owner, cohort):
    bootstrap = owner.bootstrap
    need(type(bootstrap) is NativeColdBootstrap and bootstrap.core is cohort.core and
         owner.scientific_smoke is cohort and not bootstrap.records and
         not hasattr(bootstrap, '_formal_initial_owner'),
         'FORMAL_INITIAL_ONLY_COLD_SAME_ORIGINAL_BOOTSTRAP')
    original = bootstrap.start_initial

    def getter(bound, trajectory):
        need(bound is bootstrap and owner.scientific_smoke is cohort and trajectory in cohort.tracks,
             'FORMAL_INITIAL_SAME_OWNER_REGISTERED_TRAJECTORY')
        return cohort.tracks[trajectory]['tester']

    def edits(tree):
        changes = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1 and
                isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'tester'):
                changes.append((node, copy.deepcopy(node)))
                node.value = ast.parse('_formal_actual_tester(self,t)', mode='eval').body
            elif (isinstance(node, ast.ImportFrom) and node.module == 'smoke_bootstrap_task_tester' and
                  [(alias.name, alias.asname) for alias in node.names] == [('NativeTesterInitialRelease', None)]):
                changes.append((node, copy.deepcopy(node)))
                node.module = 'formal_count14_tester'
                node.names = [ast.alias(name='FormalCount14Tester', asname='NativeTesterInitialRelease')]
            elif isinstance(node, ast.Constant) and node.value == 'ORIGINAL_TESTER_CYCLE0_PUBLISHED_MODELS_HELD':
                changes.append((node, copy.deepcopy(node)))
                node.value = 'TASK_AWARE_NATIVE_CYCLE0_READY_MODELS_HELD'
            elif isinstance(node, ast.Constant) and node.value == 'smoke_checkpoint_ports':
                changes.append((node, copy.deepcopy(node)))
                node.value = 'formal_checkpoint_ports'
        need(len(changes) == 4, 'FORMAL_INITIAL_EXACT_TESTER_THREE_AND_CHECKPOINT_REGISTRY_SELECTOR')
        return changes
    formal = _compiled(NativeColdBootstrap.start_initial, edits, {'_formal_actual_tester': getter})
    def start(bound, trajectory):
        if trajectory not in cohort.tracks:
            return original(trajectory)
        return formal(bound, trajectory)
    bootstrap.start_initial = MethodType(start, bootstrap)
    bootstrap._formal_initial_owner = cohort


def formal_activate_method(original):
    def edits(tree):
        rows = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and
                node.module == 'native_baseline_smoke' and
                [(alias.name, alias.asname) for alias in node.names] == [('NativeBaselineSmoke', None)]]
        need(len(rows) == 1, 'FORMAL_ACTIVATE_ONE_ORIGINAL_EXACT_COHORT_TYPE_SELECTOR')
        node = rows[0]
        old = copy.deepcopy(node)
        node.module = 'native_formal_cohort'
        node.names = [ast.alias(name='NativeFormalCohort', asname='NativeBaselineSmoke')]
        return [(node, old)]
    return _compiled(original, edits)
