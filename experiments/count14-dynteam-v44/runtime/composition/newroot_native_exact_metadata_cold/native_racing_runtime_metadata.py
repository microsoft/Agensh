"""Exact original RACING phase IPC metadata for the complete physical capture.

No scientific messages, turn targets, credentials or file bodies are read.
Only the two original listener paths in each frozen router export qualify;
socket identities remain pinned per genuine container birth across captures.
"""
from pathlib import Path
import os
import stat

from common import need


def socket_identity(path):
    path = Path(path)
    value = path.lstat()
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink()
         and stat.S_ISSOCK(value.st_mode) and value.st_nlink == 1
         and value.st_uid == value.st_gid == 10000,
         'RACING_PHYSICAL_ONLY_EXACT_ORIGINAL_ROUTER_PHASE_SOCKET')
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid,
            value.st_gid, value.st_mtime_ns)


class FrozenPhaseMetadata:
    """Cold export declaration first; real listener registration only frozen."""
    def __init__(self, whitelist):
        core = whitelist.core
        need(not core.closed and not core.scientific_activation_qualified
             and set(core.gate.startup_held) == set(core.rows),
             'RACING_PHASE_METADATA_ONLY_NEW_HELD_COLD_CORE')
        self.whitelist = whitelist
        self.declared = {}
        self.pins = {}
        for trajectory, row in core.rows.items():
            exports = core.cold_native_exports['trajectories'][trajectory]
            phases = exports['phase_routes']
            if not phases:
                continue
            expected = {'racing-background-00', *(f'racing-player-{i:02d}' for i in range(7))}
            need(row['arm'] == 'DYNTEAM_RACING' and set(phases) == expected,
                 'RACING_PHASE_METADATA_EXACT_ORIGINAL_EIGHT_ROLE_CATALOGUE')
            for role in sorted(expected):
                entry = whitelist.entries[trajectory, role, 'router']
                root = Path(exports['role_exports'][role]['router_control_directory'])
                need(root == entry.source and root.resolve() == root
                     and entry.directory_identity[2:] == (10000, 10000, 0o700)
                     and phases[role] == dict(socket=str(root / 'scientific.sock'),
                                             secret=str(root / 'phase.secret')),
                     'RACING_PHASE_METADATA_ORIGINAL_EXACT_FROZEN_EXPORT')
                alias = root / 'current-turn.json'
                value = alias.lstat()
                need(stat.S_ISLNK(value.st_mode) and value.st_nlink == 1
                     and (value.st_uid, value.st_gid) == (os.geteuid(), os.getegid())
                     and os.readlink(alias) == '/var/run/acp/current-turn.json',
                     'RACING_PHASE_METADATA_ONLY_ORIGINAL_OPAQUE_TURN_ALIAS')
                self.declared[trajectory, role] = (
                    root, entry.directory_identity,
                    (value.st_dev, value.st_ino, value.st_mode, value.st_uid,
                     value.st_gid, value.st_mtime_ns, value.st_ctime_ns))

    def extend(self, port, registration, original_sockets):
        from native_container_retirement import ContainerBinding
        from native_peer_registry import process_birth
        writer = port.writer
        core = self.whitelist.core
        need(writer.core is core and registration is writer.whole_team,
             'RACING_PHASE_METADATA_SAME_REAL_CAPTURE_CORE')
        registration.frozen(writer.writer_fence)
        result = dict(original_sockets)
        selected = [(role, value) for (trajectory, role), value in self.declared.items()
                    if trajectory == writer.t]
        need(not selected or len(selected) == 8,
             'RACING_PHASE_METADATA_NO_PARTIAL_HELPER_DECLARATION')
        for role, (root, directory_pin, alias_pin) in selected:
            inventory = writer.containers['backend-router-' + role]
            binding = core.native_containers.records[writer.t, role, 'router']
            need(type(binding) is ContainerBinding and binding.cid == inventory['cid']
                 and binding.image_id == inventory['image']
                 and process_birth(binding.init_birth.pid) == binding.init_birth
                 and (binding.init_birth.uid, binding.init_birth.gid) == (10000, 10000)
                 and process_birth(binding.peer_birth.pid) == binding.peer_birth,
                 'RACING_PHASE_METADATA_GENUINE_CURRENT_AUTHENTICATED_ROUTER_BIRTH')
            value = root.lstat()
            need(root.resolve() == root and stat.S_ISDIR(value.st_mode)
                 and (value.st_dev, value.st_ino, value.st_uid, value.st_gid,
                      stat.S_IMODE(value.st_mode)) == directory_pin
                 and any(Path(v['path']) == root for v in inventory['roots'].values())
                 and registration.services['backend-router-' + role]['roots'] == inventory['roots'],
                 'RACING_PHASE_METADATA_FULL_REGISTERED_RW_ROOT_STAYS_CAPTURED')
            alias = root / 'current-turn.json'
            value = alias.lstat()
            need(stat.S_ISLNK(value.st_mode) and
                 (value.st_dev, value.st_ino, value.st_mode, value.st_uid,
                  value.st_gid, value.st_mtime_ns, value.st_ctime_ns) == alias_pin
                 and os.readlink(alias) == '/var/run/acp/current-turn.json',
                 'RACING_PHASE_METADATA_ORIGINAL_ALIAS_NEVER_FOLLOWED_OR_REBOUND')
            key = (writer.t, role, binding.cid, binding.init_birth)
            actual = {str(root / name): socket_identity(root / name)
                      for name in ('proxy.sock', 'scientific.sock')}
            if key not in self.pins:
                self.pins[key] = dict(actual)
            need(actual == self.pins[key],
                 'RACING_PHASE_METADATA_LISTENER_INODE_CANNOT_CHANGE_WITHIN_BIRTH')
            for path, identity in actual.items():
                need(path not in result or tuple(result[path]) == identity,
                     'RACING_PHASE_METADATA_CANNOT_OVERWRITE_OTHER_RUNTIME_IDENTITY')
                result[path] = identity
        registration.frozen(writer.writer_fence)
        for role, (root, _, _) in selected:
            binding = core.native_containers.records[writer.t, role, 'router']
            key = (writer.t, role, binding.cid, binding.init_birth)
            need(all(socket_identity(Path(path)) == identity
                     for path, identity in self.pins[key].items()),
                 'RACING_PHASE_METADATA_POST_CAPTURE_REGISTRATION_IDENTITY_STABLE')
        return result
