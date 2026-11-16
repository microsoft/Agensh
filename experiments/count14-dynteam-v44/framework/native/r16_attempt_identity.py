"""One explicitly user-authorized fresh attempt; not a new scientific arm.

Canonical manifest, model, source, seed and FINAL pins remain unchanged. Trusted
host registers a NEW account/process/root; no old request/RNG prefix is reused.
"""
from pathlib import Path
from common import need
from manifest import compile_manifest

OLD_SUFFIX='/Agensh-1/block-1/seed-4287909351'
ATTEMPT_ID='r16-team1-b1-2'
ATTEMPT_SUFFIX='/attempt-'+ATTEMPT_ID
EXPERIMENT='agensh-comparison-20261027-scientific6-r16'

def resolve_row(manifest, trajectory):
    rows={r['trajectory_id']:r for r in compile_manifest(manifest)['trajectories']}
    if trajectory in rows:return rows[trajectory]
    old=EXPERIMENT+OLD_SUFFIX
    need(manifest['experiment_id']==EXPERIMENT and old in rows
         and trajectory==old+ATTEMPT_SUFFIX,'R16_EXPLICIT_AUTHORIZED_ATTEMPT_ONLY')
    row=dict(rows[old]);row.update(trajectory_id=trajectory,canonical_trajectory_id=old,
        attempt_id=ATTEMPT_ID,root=str(Path(row['root'])/'attempts'/'a2'))
    # Exact Linux pathname AF_UNIX bound; no symlink/guard relaxation.
    from native_delivery import FILES
    paths=[Path(row['root'])/'transport-exports'/role/name
           for role in row['roles'] for name in FILES if name.endswith('.sock')]
    need(all(len(str(p).encode('utf-8'))<=107 for p in paths),
         'R16_ATTEMPT_SOCKET_PATH_TOO_LONG')
    return row
