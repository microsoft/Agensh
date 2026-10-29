#!/usr/bin/env python3
"""Check that an image contains exactly the requested harness and its runtime."""

import json
import os
from pathlib import Path
import subprocess
import sys
from dataclasses import asdict

from harness_config import DEFAULT_VERSIONS, PROFILE, load_config, prepare_native, reported_version


def check(kind, expected_version=None):
    config = load_config(overrides={'harness': kind, 'version': expected_version})
    kind = config.harness
    runtime = Path('/opt/omcgitea')
    required = ('config.sh',) if kind == 'copilot' else ('acp.py', 'config.py')
    if any(not (runtime / kind / name).is_file() for name in required):
        raise RuntimeError(f'Rebuild {kind} with the current harness directory layout')
    if any((runtime / other).exists() for other in DEFAULT_VERSIONS if other != kind):
        raise RuntimeError(f'The {kind} image must contain only its own harness directory')
    binary = Path('/usr/local/bin') / (kind + '-wrapped')
    if not os.access(binary, os.X_OK):
        raise RuntimeError(f'This image has no {kind}; rebuild with --build-arg AGENT_HARNESS={kind}')
    for other in DEFAULT_VERSIONS:
        if other != kind and ((Path('/opt') / (other + '-cli')).exists() or
                              (binary.parent / (other + '-wrapped')).exists()):
            raise RuntimeError(f'The {kind} image must not contain {other}')
    version = subprocess.check_output([str(binary), '--version'], text=True).strip().splitlines()[0]
    cli_version = reported_version(version)
    if cli_version != config.version:
        raise RuntimeError(f'Expected {kind} {config.version}, found {cli_version}; rebuild the selected image')
    if kind == 'codex' and not os.access('/opt/codex-cli/bin/codex-code-mode-host', os.X_OK):
        raise RuntimeError('Codex requires its native Code Mode host for this model profile')
    prepare_native(config)
    if kind == 'pi':
        package = Path('/opt/pi-cli/node_modules/@earendil-works/pi-coding-agent')
        manifest = json.loads((package / 'agensh-limits.json').read_text())
        if (manifest.get('profile') != PROFILE or manifest.get('pi_version') != cli_version
                or manifest.get('tool_output_bytes') != config.tool_output_bytes
                or manifest.get('mcp_output_bytes') != config.tool_output_bytes
                or manifest.get('entrypoint') != 'dist/rpc-entry.js'
                or 'dist/rpc-entry.js' not in binary.read_text()):
            raise RuntimeError('Rebuild Pi with the reviewed Copilot resource policy')
    elif kind == 'codex':
        catalog = json.loads(Path('/opt/omcgitea/codex/models.json').read_text())
        if not catalog.get('models') or any(model.get('truncation_policy') !=
                {'mode': 'bytes', 'limit': config.tool_output_bytes} for model in catalog['models']):
            raise RuntimeError('Rebuild Codex with the reviewed native model catalog')
    node_version = subprocess.check_output(['/opt/agentrt/bin/node', '--version'], text=True).strip()
    return {'agent_harness': kind, 'version': version, 'cli_version': cli_version, 'node_version': node_version,
            'limits_profile': PROFILE, 'tool_output_bytes': config.tool_output_bytes,
            'settings': asdict(config)}


if __name__ == '__main__':
    print(json.dumps(check(sys.argv[1] if len(sys.argv) > 1 else os.environ.get('AGENT_HARNESS', 'copilot'),
                           sys.argv[2] if len(sys.argv) > 2 else None)))
