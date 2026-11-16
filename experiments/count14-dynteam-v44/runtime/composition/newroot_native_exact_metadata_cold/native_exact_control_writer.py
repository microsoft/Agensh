"""Msg210 / plan748: exact native-control roots, FULL original physical backup.

New cold namespace only. No active module/class changes, backup root exclusion,
caller path allowlist, extra mount, IPC name scan, model or financial action.
"""
from pathlib import Path
from types import FunctionType, MethodType
import ast
import copy
import hashlib
import inspect
import os
import stat
import textwrap

PLAN = '748ed49a3a96665a47044ddf793bb33502a87df715fb7ce3884676776859bd0f'
WRITER = '9f7941d794e8ba46106642bbd03052fb919621e67a80cb59ad4774762a2bf0c1'
CONTROL = '54ee9dd7eb09268ca86ac6f7ca43153ddc0d1fd5e22572a830801515de166fe2'
CHECKPOINT = 'c67217c67f14da903597afa73924a13d6ff32340297721ef7e94259467e8a504'
DESTINATION = '/run/count14-dynteam'
CLOCK = '/run/count14-budget-clock'
MATTERMOST_COMPONENT = 'a611121c5cc4300cb64c79acd849c1c47b83995a8895129efe9ba728b522bc57'


def need(ok):
    if not ok:
        raise ValueError('EXACT_CONTROL_WRITER_ONLY_FROZEN_SAME_CORE_COMPLETE_BACKUP')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_selector(whitelist, control_module, *, mattermost_module, scope_guard):
    need(sha(control_module.__file__) == CONTROL and type(whitelist) is control_module.FrozenControls and
         sha(mattermost_module.__file__) == MATTERMOST_COMPONENT and callable(scope_guard))

    def allowed(writer, launch, snapshot, mount, source, infrastructure):
        need(writer.core is whitelist.core and writer.core.native_containers is whitelist.registry)
        need(source.is_absolute() and source.resolve() == source and not source.is_symlink())
        # Tighten, never broaden, the original clock/agent read-only contract.
        need(mount.get('Destination') != CLOCK and source not in whitelist.clocks)
        if not infrastructure:
            need(launch is not None)
            whitelist.readonly_clocks(launch, snapshot)
        if source.is_relative_to(Path(writer.row['root'])):
            return True
        if infrastructure and snapshot['labels'].get('role') == 'infra-mattermost':
            return mattermost_module.registry_for(writer.core,scope_guard).exact(writer,launch,snapshot,mount,source)
        need(not infrastructure and launch.component == 'router')
        return whitelist.exact(whitelist.registry, launch, snapshot, mount, source, running=True) is True

    return allowed


def compile_writer(original, *, whitelist, control_module, mattermost_module, scope_guard):
    """Complete original native writer: exact control + per-track MM snapshot.

    Original native launch-binding expression executes as the final argument,
    before the hook can register metadata. No adopted/historical branch exists.
    """
    need(sha(original.__file__) == WRITER and inspect.getsourcefile(original.DynamicCutWriter) == original.__file__)
    need(sha(mattermost_module.__file__) == MATTERMOST_COMPONENT and callable(scope_guard) and scope_guard(whitelist.core) is True)
    raw = Path(original.__file__).read_text(); tree = ast.parse(raw); before = copy.deepcopy(tree)
    predicate = ast.parse("source.is_relative_to(Path(self.row['root'])) and source.resolve()==source", mode='eval').body
    selected = ast.parse('_exact_writer_source(self,launch,row,mount,source,infrastructure)', mode='eval').body
    native = ast.parse("{'kind':'ORIGINAL_ZERO_MODEL_INFRA_BOOTSTRAP','control_births':copy.deepcopy(core.cold_bootstrap.records[self.t]['control_births'])}", mode='eval').body
    picked = ast.Call(func=ast.Name(id='_mm_native_launch_binding',ctx=ast.Load()),
        args=[ast.Name(id=n,ctx=ast.Load()) for n in ('self','original_name','launch','row')]+[copy.deepcopy(native)],keywords=[])
    enumeration=ast.parse("enumerate(row['mounts'])",mode='eval').body
    ordered=ast.parse("enumerate(_canonical_native_mounts(row['mounts']))",mode='eval').body
    counts=[0,0,0]
    class Select(ast.NodeTransformer):
        def visit(self,node):
            for i,(a,b) in enumerate(((predicate,selected),(native,picked),(enumeration,ordered))):
                if ast.dump(node,include_attributes=False)==ast.dump(a,include_attributes=False):
                    counts[i]+=1;return copy.deepcopy(b)
            return super().visit(node)
    class Reverse(ast.NodeTransformer):
        def visit(self,node):
            for a,b in ((selected,predicate),(picked,native),(ordered,enumeration)):
                if ast.dump(node,include_attributes=False)==ast.dump(a,include_attributes=False):return copy.deepcopy(b)
            return super().visit(node)
    tree=Select().visit(tree)
    need(counts==[1,1,1] and ast.dump(Reverse().visit(copy.deepcopy(tree)),include_attributes=False)==ast.dump(before,include_attributes=False))
    namespace=dict(original.__dict__,_canonical_native_mounts=mattermost_module.canonical_mounts)
    namespace['_exact_writer_source']=source_selector(whitelist,control_module,mattermost_module=mattermost_module,scope_guard=scope_guard)
    namespace['_mm_native_launch_binding']=mattermost_module.launch_selector(whitelist.core,scope_guard=scope_guard)
    exec(compile(ast.fix_missing_locations(tree),original.__file__+':fresh-native-MM-exact-control','exec'),namespace)
    selected_class=namespace['DynamicCutWriter']
    need(selected_class is not original.DynamicCutWriter and namespace['_no_legacy_sdk'].__globals__ is namespace and namespace['DynamicCutWriter'] is selected_class)
    return selected_class,dict(schema='count14-newroot-native-MM-full-original-writer-selection-v1',
        approved_plan_sha256=PLAN,original_writer_sha256=WRITER,selection_sites=counts,inverse_full_module_AST=True,
        original_native_launch_binding_expression_evaluated_first=True,nonempty_original_native_control_births_required=True,
        adopted_or_current_history_fallbacks=0,exact_per_track_snapshot_guard_before_RW_loop=True,
        original_root_identity_and_all_RW_mount_index_insertions_unchanged=True,
        sole_original_enumerate_input_full_JSON_canonical_order=True,full_mount_fields_and_duplicate_multiplicity_preserved=True,
        original_inventory_census_scope_launch_process_cgroup_and_refresh_guards_unchanged=True,
        no_global_module_class_or_current_graph_mutated=True,physical_backup_roots_removed=0,
        fresh_helper_sha256=MATTERMOST_COMPONENT,whole_package_or_target_qualification=False)


def _socket_identity(path):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink())
    value = path.lstat()
    need(stat.S_ISSOCK(value.st_mode))
    return value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid, value.st_mtime_ns


def register_exact_control_IPC(port, registration, original_sockets, *, whitelist):
    """Add only mounted control roots' actual same-listener socket hardlinks.

    Every regular file stays in original roots and is captured by original CAS.
    Unknown IPC/special files still reach and fail the original CAS traversal.
    """
    writer = port.writer
    need(registration is writer.whole_team and writer.core is whitelist.core)
    registration.frozen(writer.writer_fence)
    listener = _socket_identity(writer.core.control.path)
    result = dict(original_sockets)
    for role in writer.roles:
        name = 'backend-router-' + role
        inventory = writer.containers.get(name)
        if inventory is None:
            continue
        key = writer.t, role, 'router'
        entry = whitelist.retained.get((*key, inventory['cid'])) or whitelist.entries.get(key)
        need(entry is not None)
        # Only a root that was accepted and remains in the physical backup
        # services table is eligible. No directory/filename traversal occurs.
        roots = inventory['roots']
        if not any(Path(binding['path']) == entry.source for binding in roots.values()):
            continue
        need(control_identity(entry.source) == entry.directory_identity)
        need(registration.services[name]['roots'] == roots)
        path = entry.source / 'native-control.sock'
        actual = _socket_identity(path)
        need(actual == listener and (str(path) not in result or tuple(result[str(path)]) == actual))
        result[str(path)] = actual
    registration.frozen(writer.writer_fence)
    need(_socket_identity(writer.core.control.path) == listener)
    return result


def control_identity(path):
    value = Path(path).stat()
    need(stat.S_ISDIR(value.st_mode))
    return value.st_dev, value.st_ino, value.st_uid, value.st_gid, stat.S_IMODE(value.st_mode)


def control_capture_selector(whitelist):
    """Original CAS captures ALL bytes; only stricter control-root special policy.

    The one original RACING SDK symlink is frozen as metadata before native
    actions. Unknown symlinks/hardlinks, sockets, FIFO and devices cannot become
    ad-hoc exclusions. Other scientific/physical roots keep their original CAS.
    """
    roots = {}
    known_links = {}
    for key, entry in (*whitelist.entries.items(), *whitelist.retained.items()):
        root = entry.source
        need(root not in roots or roots[root] == entry.directory_identity)
        roots[root] = entry.directory_identity
        phases = whitelist.core.cold_native_exports['trajectories'][key[0]]['phase_routes']
        if key[1] in phases:
            need(whitelist.core.rows[key[0]]['arm'] == 'DYNTEAM_RACING' and
                 root == Path(phases[key[1]]['socket']).parent)
            path = root / 'current-turn.json'
            value = path.lstat()
            need(stat.S_ISLNK(value.st_mode) and os.readlink(path) == '/var/run/acp/current-turn.json')
            known_links[path] = (value.st_dev, value.st_ino, value.st_uid, value.st_gid, value.st_mode,
                                 value.st_mtime_ns, value.st_ctime_ns)

    def metadata(source, sockets):
        need(source.is_absolute() and source.resolve() == source and control_identity(source) == roots[source])
        pending = [source]
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as scan:
                for entry in scan:
                    path = directory / entry.name
                    value = path.lstat()
                    if stat.S_ISDIR(value.st_mode):
                        need(path.resolve() == path)
                        pending.append(path)
                    elif stat.S_ISREG(value.st_mode):
                        need(value.st_nlink == 1)  # No unknown external hardlink.
                    elif stat.S_ISSOCK(value.st_mode):
                        need(str(path) in sockets and tuple(sockets[str(path)]) == _socket_identity(path))
                    elif stat.S_ISLNK(value.st_mode):
                        actual = (value.st_dev, value.st_ino, value.st_uid, value.st_gid, value.st_mode,
                                  value.st_mtime_ns, value.st_ctime_ns)
                        need(path in known_links and actual == known_links[path] and
                             os.readlink(path) == '/var/run/acp/current-turn.json')
                    else:
                        need(False)

    def capture(cas, source, *, runtime_sockets):
        source = Path(source)
        if source in roots:
            metadata(source, runtime_sockets)
        result = cas.capture_tree(source, runtime_sockets=runtime_sockets)
        if source in roots:
            metadata(source, runtime_sockets)
        return result

    return capture


def physical_backup_factory(original_class, *, whitelist):
    """Keep original port TYPE and full run, adding only control special checks."""
    function = original_class.run
    before = ast.parse(textwrap.dedent(inspect.getsource(function)))
    tree = copy.deepcopy(before)
    wanted = ast.parse("cut.cas.capture_tree(Path(binding['path']),runtime_sockets=sockets)", mode='eval').body
    selected = ast.parse("_approved_capture(cut.cas,Path(binding['path']),runtime_sockets=sockets)", mode='eval').body
    count = 0

    class Select(ast.NodeTransformer):
        def visit(self, node):
            nonlocal count
            if ast.dump(node, include_attributes=False) == ast.dump(wanted, include_attributes=False):
                count += 1
                return copy.deepcopy(selected)
            return super().visit(node)

    class Reverse(ast.NodeTransformer):
        def visit(self, node):
            if ast.dump(node, include_attributes=False) == ast.dump(selected, include_attributes=False):
                return copy.deepcopy(wanted)
            return super().visit(node)

    tree = Select().visit(tree)
    need(count == 1 and ast.dump(Reverse().visit(copy.deepcopy(tree)), include_attributes=False) ==
         ast.dump(before, include_attributes=False))
    namespace = dict(function.__globals__, _approved_capture=control_capture_selector(whitelist))
    exec(compile(ast.fix_missing_locations(tree), function.__code__.co_filename + ':msg210-control-specials', 'exec'), namespace)

    def factory(*args, **kwargs):
        return original_class(*args, **kwargs)

    # Original _begin_cut's existing _function selection sees this run and
    # still supplies its genuine same-cut runtime-sockets callback normally.
    factory.run = namespace['run']
    return factory


def compile_checkpoint(original, *, selected_writer, whitelist):
    """Keep the ORIGINAL checkpoint type and all strict retirement consumers.

    Bind only new-unused checkpoint instances in the new held cold graph.
    Both original methods retain their CodeType and select the same private
    writer through private globals; no original class/module mutation occurs.
    """
    need(sha(original.__file__) == CHECKPOINT)
    tree = ast.parse(Path(original.__file__).read_text())
    uses = [node for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id == 'DynamicCutWriter' and isinstance(node.ctx, ast.Load)]
    need(len(uses) == 3)  # preflight __new__(class), plus the real _begin_cut.
    original_class = original.DynamicCheckpointPorts
    retained = set()
    physical = physical_backup_factory(original.NativeWholeTeamPhysicalBackup, whitelist=whitelist)

    def selected_method(function):
        value = FunctionType(function.__code__, dict(function.__globals__, DynamicCutWriter=selected_writer,
                             NativeWholeTeamPhysicalBackup=physical),
                             function.__name__, function.__defaults__, function.__closure__)
        value.__kwdefaults__ = function.__kwdefaults__
        return value

    preflight = selected_method(original_class.preflight)
    begin_cut = selected_method(original_class._begin_cut)
    body = original_class._native_runtime_sockets
    import native_racing_runtime_metadata as phase_metadata
    need(sha(phase_metadata.__file__) == '64e8caf2c2b44f8a96646403418f8fe113b825b0a31143bfb82f404bb7df23db')
    phases = phase_metadata.FrozenPhaseMetadata(whitelist)

    def sockets(port, registration):
        original_result = body(port, registration)
        controls = register_exact_control_IPC(port, registration, original_result, whitelist=whitelist)
        return phases.extend(port, registration, controls)

    def bind_unused(port):
        need(type(port) is original_class and port.core is whitelist.core and
             port.writer is None and port.state == 'BOUND_MODELS_HELD' and id(port) not in retained and
             not port.core.scientific_activation_qualified and
             set(port.core.gate.startup_held) == set(port.core.rows) and
             all(name not in vars(port) for name in ('preflight', '_begin_cut', '_native_runtime_sockets')))
        retained.add(id(port))
        port.preflight = MethodType(preflight, port)
        port._begin_cut = MethodType(begin_cut, port)
        port._native_runtime_sockets = MethodType(sockets, port)
        need(type(port) is original_class and
             port.preflight.__func__.__code__ is original_class.preflight.__code__ and
             port._begin_cut.__func__.__code__ is original_class._begin_cut.__code__)
        return port

    def factory(*args, **kwargs):
        return bind_unused(original_class(*args, **kwargs))

    return factory, bind_unused, dict(schema='count14-exact-control-writer-original-checkpoint-consumer-selection-v2',
        approved_plan_sha256=PLAN, original_checkpoint_sha256=sha(original.__file__),
        original_checkpoint_type_and_strict_retirement_type_checks_preserved=True,
        original_preflight_and_begin_cut_CodeType_unchanged=True, selected_writer_load_sites=len(uses),
        exact_same_listener_IPC_metadata_only=True, original_CAS_cut_COMMITTED_collector_K3_bodies_unchanged=True,
        physical_backup_single_capture_call_inverse_AST=True,
        physical_port_type_and_all_root_capture_preserved_with_stricter_unknown_control_special_refusal=True,
        no_global_module_class_or_current_graph_mutated=True)
