"""Cold-only per-root host alias; no daemon mutation or container action.

This compiles an ADDITIONAL private Compose layer.  The old generated base,
private environment, original overlay and all scientific sources stay intact.
Only the existing host.docker.internal hostname is concretized to the exact
NativeNetworkBinding gateway already used by the same trajectory's relay.
Writing this layer is not permission to remove, start or activate containers.
"""
from pathlib import Path
import json
import os
import stat


def need(condition, code):
    if not condition:
        raise ValueError(code)


def compile_overlay(*, contract, row, network, relay_address, qualification_only):
    from native_network_binding import NativeNetworkBinding
    from native_beta_layout import native_aliases

    need(type(network) is NativeNetworkBinding,
         'DYNTEAM_HOST_ALIAS_ORIGINAL_TYPED_NETWORK_REQUIRED')
    need(type(contract) is dict and type(row) is dict and
         any(value is row for value in contract['trajectories']),
         'DYNTEAM_HOST_ALIAS_SAME_CONTRACT_ROW_REQUIRED')
    network.checked(contract=contract, row=row, qualification_only=qualification_only)
    need(type(relay_address) is tuple and len(relay_address) == 2 and
         type(relay_address[0]) is str and relay_address[0] == network.gateway and
         type(relay_address[1]) is int and 0 < relay_address[1] < 65536,
         'DYNTEAM_HOST_ALIAS_EXACT_EXISTING_RELAY_GATEWAY_REQUIRED')
    aliases = native_aliases(row['arm'])
    need(set(aliases) == set(row['roles']),
         'DYNTEAM_HOST_ALIAS_EXACT_REGISTERED_ROLE_CATALOGUE_REQUIRED')
    services = {}
    for role, alias in aliases.items():
        for component in ('agent', 'router'):
            name = alias[component + '_service']
            need(name not in services,
                 'DYNTEAM_HOST_ALIAS_NO_DUPLICATE_OR_INFRA_SERVICE')
            services[name] = {'extra_hosts': {'host.docker.internal': network.gateway}}
    need(len(services) == 2 * len(aliases),
         'DYNTEAM_HOST_ALIAS_ALL_REGISTERED_ROLE_PAIRS_ONLY')
    return {'services': services}


def write_new_overlay(path, *, contract, row, network, relay_address,
                      qualification_only, owner_uid):
    """One new private file, never rewrite an existing control/source layer."""
    value = compile_overlay(contract=contract, row=row, network=network,
                            relay_address=relay_address,
                            qualification_only=qualification_only)
    path = Path(path)
    root = Path(row['root'])
    need(type(owner_uid) is int and owner_uid == os.geteuid() and
         (qualification_only or owner_uid == 0) and path.is_absolute() and
         path.parent.resolve() == path.parent and root.resolve() == root and
         path.is_relative_to(root) and
         path.name == 'compose.explicit-host-gateway.private.yaml',
         'DYNTEAM_HOST_ALIAS_NEW_PRIVATE_LEAF_ONLY_OWN_ROOT')
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        before = os.fstat(parent)
        need(before.st_uid == owner_uid and not stat.S_IMODE(before.st_mode) & 0o022,
             'DYNTEAM_HOST_ALIAS_EXACT_PRIVATE_PARENT_OWNER_MODE')
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o400, dir_fd=parent)
        # Compose's plain list/map merge retains the unresolved old sentinel.
        # The explicit per-attribute tag replaces ONLY this single host list.
        # If unsupported, normal config verification must refuse before rm.
        lines = ['services:']
        for service, config in sorted(value['services'].items()):
            address = config['extra_hosts']['host.docker.internal']
            lines += ['  ' + json.dumps(service) + ':',
                      '    extra_hosts: !override',
                      '      - ' + json.dumps('host.docker.internal=' + address)]
        with os.fdopen(fd, 'wb') as stream:
            stream.write(('\n'.join(lines) + '\n').encode())
            stream.flush()
            os.fchmod(stream.fileno(), 0o400)
            os.fsync(stream.fileno())
        after = os.fstat(parent)
        need((before.st_dev, before.st_ino, before.st_uid, before.st_mode) ==
             (after.st_dev, after.st_ino, after.st_uid, after.st_mode),
             'DYNTEAM_HOST_ALIAS_PARENT_IDENTITY_CHANGED')
        os.fsync(parent)
    finally:
        os.close(parent)
    return path


def append_layer(compose, *, path, network):
    """Only a new command tuple; old command/source/file bytes are unchanged."""
    from native_network_binding import NativeNetworkBinding
    need(type(network) is NativeNetworkBinding and type(compose) is tuple and
         all(type(value) is str for value in compose) and
         compose.count('compose') == 1 and compose.count('--project-name') == 1,
         'DYNTEAM_HOST_ALIAS_ORIGINAL_FINITE_COMPOSE_COMMAND')
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and
         path.is_relative_to(Path(network.experiment_root)) and
         path.name == 'compose.explicit-host-gateway.private.yaml',
         'DYNTEAM_HOST_ALIAS_ONLY_THIS_NEW_PRIVATE_FILE')
    s = path.lstat()
    need(stat.S_ISREG(s.st_mode) and not path.is_symlink() and s.st_nlink == 1 and
         s.st_uid == os.geteuid() and stat.S_IMODE(s.st_mode) == 0o400,
         'DYNTEAM_HOST_ALIAS_EXACT_NEW_PRIVATE_FILE_METADATA')
    need(str(path) not in compose,
         'DYNTEAM_HOST_ALIAS_LAYER_ALREADY_SELECTED_NO_DUPLICATION')
    at = compose.index('--project-name')
    need(at > compose.index('compose') and at + 1 < len(compose),
         'DYNTEAM_HOST_ALIAS_INSERT_ONLY_BEFORE_ORIGINAL_PROJECT_NAME')
    return compose[:at] + ('-f', str(path)) + compose[at:]
