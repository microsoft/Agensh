#!/usr/bin/env python3
# software-project evaluate hook: run the final acceptance commands ([acceptance] final,
# else main) on the delivered main inside the worker image and record each command's
# outcome in acceptance.json. [acceptance] private_dir (held-out data the team never
# saw) is mounted read-only at /private for these commands only. With the pack's model
# route, the commands run on the team network so AGENSH_MODEL_BASE reaches the proxy.
# A failing check is a result, not a hook failure; only an unusable setup exits 1.

import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

from common import ROOT, context, log, read_json, write_json

sys.path.insert(0, str(ROOT))
from agensh import quality  # noqa: E402

OUTPUT_TAIL = 4000
# The checkout belongs to the host user, not the container's root, so git would refuse it
# as dubious ownership; trust it as the worker's own git config does, then run the check.
TRUSTED_RUN = 'git config --global --add safe.directory "*" && eval "$1"'


def main():
    task_out, values, project, pack = context()
    checkout = task_out / '_deliver'
    if not checkout.is_dir():
        raise RuntimeError(f'{checkout} is missing; the export hook did not complete')
    prepare = read_json(task_out / 'prepare.json', {})
    image = values['AGENT_IMAGE']
    docker = shlex.split(os.environ.get('DOCKER', 'sudo -n docker'))
    network = ['--network', 'none'] if prepare.get('network') == 'offline' else []
    profile = os.environ.get('AGENSH_PROFILE') or values.get('PROFILE', '')
    if pack.model_route and not profile:
        log('WARN: no profile name; the final commands cannot reach the model route')
    elif pack.model_route:
        team_network = f'omcgitea-{profile}_default'
        if subprocess.run([*docker, 'network', 'inspect', team_network], capture_output=True).returncode == 0:
            network = ['--network', team_network, '-e', f'AGENSH_MODEL_BASE={quality.FINAL_MODEL_ROUTE}']
        else:
            log(f'WARN: {team_network} is gone; the final commands cannot reach the model route')
    private = ['-v', f'{project.private_dir}:/private:ro', '-e', 'AGENSH_PRIVATE_DIR=/private'] if project.private_dir else []
    results = []
    for command in project.final_commands:
        started = time.monotonic()
        run = subprocess.run([*docker, 'run', '--rm', *network, '--entrypoint', 'bash', '-v', f'{checkout}:/work',
                              *private, '-w', '/work', image, '-lc', TRUSTED_RUN, 'bash', command],
                             capture_output=True, text=True)
        output = (run.stdout + run.stderr)[-OUTPUT_TAIL:]
        results.append({'command': command, 'exit_status': run.returncode,
                        'seconds': round(time.monotonic() - started, 1), 'output_tail': output})
        log(f'{"PASS" if run.returncode == 0 else "FAIL"} ({run.returncode}) {command}')
    write_json(task_out / 'acceptance.json', {
        'head': read_json(task_out / 'delivery.json', {}).get('head'), 'image': image,
        'all_passed': all(r['exit_status'] == 0 for r in results), 'results': results,
    })


if __name__ == '__main__':
    try:
        main()
    except Exception as error:  # Report any failure as the hook's exit status.
        log(f'FATAL: {error}')
        sys.exit(1)
