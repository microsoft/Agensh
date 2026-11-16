"""Pure proposed native management-bridge USER layer, never an installer.

No approval is created or consumed here. The exact current-three proposal is
pending; full-roster compilation is design/test coverage, NOT authority to
apply it to dynamic roles, another root, or either formal arm. Original model
CLI UID/GID, image defaults, commands, capabilities and science stay intact.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_HOSTNAME = _count14_os.environ.get('COUNT14_HOSTNAME', 'count14-host')
from pathlib import Path
import os
import stat

PLAN_SHA = 'eebbfcb8c1a750d13b41ad630d9c7138e705083223f376f7d89e2e60e6f7b177'
INITIAL_THREE = ('tester-00', 'checker-00', 'worker-00')


def need(ok, code):
    if not ok:
        raise ValueError(code)


def proposed_layer(*, contract, row, roles):
    from native_beta_layout import native_aliases
    need(type(contract) is dict and type(row) is dict and
         any(r is row for r in contract.get('trajectories', ())) and
         row.get('arm') in ('DYNTEAM', 'DYNTEAM_RACING'),
         'PROPOSED_BRIDGE_USER_ONE_ORIGINAL_SAME_CONTRACT_ROW')
    aliases = native_aliases(row['arm'])
    need(set(row['roles']) == set(aliases) and len(row['roles']) == len(aliases) and
         type(roles) is tuple and roles and all(type(r) is str for r in roles) and
         len(set(roles)) == len(roles) and set(roles) <= set(aliases),
         'PROPOSED_BRIDGE_USER_FROZEN_NATIVE_DIRECTORY_EXACT_SELECTED_ROLES')
    # Metadata-only result. The original source still supplies the root bridge
    # and explicitly unprivileged CLI; neither command nor ACP_CHILD_UID moves.
    return {'services': {aliases[r]['agent_service']: {'user': '0:0'} for r in roles}}


def write_OWN_layer(path, *, contract, row, roles):
    """Only a local OWN metadata fixture; cannot write a the production host runtime layer."""
    import json
    path = Path(path)
    need(os.uname().nodename != (_C14_HOSTNAME) and path.is_absolute() and
         any(p.startswith('OWN-') for p in path.parts) and path.parent.resolve() == path.parent and
         not path.exists() and not path.is_symlink(), 'PROPOSED_BRIDGE_USER_OWN_ONLY_NO_PRODUCTION_WRITER')
    raw = (json.dumps(proposed_layer(contract=contract, row=row, roles=roles), sort_keys=True) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    need(stat.S_IMODE(path.stat().st_mode) == 0o400, 'PROPOSED_BRIDGE_USER_OWN_PRIVATE_LAYER_MODE')
    return path
