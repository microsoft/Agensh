#!/usr/bin/env python3
"""Resolve shared harness settings and prepare native runtime output limits."""

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
import urllib.request
from functools import lru_cache

DEFAULT_CONFIG = Path(__file__).resolve().parent / 'config/harness.json'
DEFAULT_VERSIONS = {'copilot': '1.0.70', 'pi': '1.4.0', 'codex': '0.164.0', 'claude': 'latest'}
PACKAGES = {'copilot': '@github/copilot', 'pi': '@earendil-works/pi-coding-agent',
            'codex': '@openai/codex', 'claude': '@anthropic-ai/claude-code'}
PROFILE = 'agensh-config-v4'
CRITICAL_FRACTION = 0.95
REQUEST_TIMEOUT_MS = 600000
INFERENCE_MAX_RETRIES = 5
RETRY_BASE_DELAY_MS = 500
RETRY_MAX_DELAY_MS = 60000
VERSION = re.compile(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?'
                     r'(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?')
ENV_FIELDS = {
    'harness': ('AGENT_HARNESS',), 'version': ('HARNESS_VERSION',),
    'model': ('LLM_MODEL', 'ANTHROPIC_MODEL'),
    'reasoning_effort': ('REASONING_EFFORT', 'AGENT_REASONING_EFFORT'),
    'prompt_tokens': ('PROMPT_TOKENS', 'AGENT_MAX_PROMPT_TOKENS'),
    'output_tokens': ('OUTPUT_TOKENS',), 'tool_output_bytes': ('TOOL_OUTPUT_BYTES',),
    'compact_fraction': ('COMPACT_FRACTION',),
}


def exact_version(value):
    if not isinstance(value, str) or VERSION.fullmatch(value) is None:
        raise ValueError('Harness version must be an exact release, such as 1.0.70')
    return value


def selected_version(kind, value=None):
    if kind not in DEFAULT_VERSIONS:
        raise ValueError('Harness must be copilot, pi, codex or claude')
    specification = value or DEFAULT_VERSIONS[kind]
    if specification == 'latest':
        installed = Path('/opt/omcgitea') / kind / 'release.json'
        if installed.is_file():
            return exact_version(json.loads(installed.read_text())['version'])
        return latest_version(kind)
    return exact_version(specification)


def version_argument(value):
    return value if value == 'latest' else exact_version(value)


@lru_cache(maxsize=8)
def latest_version(kind):
    package = PACKAGES[kind].replace('/', '%2f')
    with urllib.request.urlopen('https://registry.npmjs.org/' + package + '/latest', timeout=30) as response:
        return exact_version(json.load(response)['version'])


def reported_version(output):
    match = re.search(r'(?<![\w.])(' + VERSION.pattern + r')(?![\w+-])', output)
    if match is None:
        raise ValueError('Cannot read installed harness version: ' + output)
    return match.group(1)


def positive_integer(name, value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(name + ' must be a positive integer')
    try:
        result = int(value)
    except ValueError:
        raise ValueError(name + ' must be a positive integer') from None
    if result <= 0:
        raise ValueError(name + ' must be a positive integer')
    return result


def write_private(path, text):
    """Publish a native config atomically and hand it to the worker user."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(text)
    temporary.chmod(0o600)
    temporary.replace(path)
    if os.getuid() == 0:
        uid = int(os.environ.get('ACP_CHILD_UID', '10000'))
        gid = int(os.environ.get('ACP_CHILD_GID', '10000'))
        os.chown(path.parent, uid, gid)
        os.chown(path, uid, gid)


def write_private_json(path, value):
    write_private(path, json.dumps(value, indent=2) + '\n')


@dataclass(frozen=True)
class HarnessConfig:
    harness: str
    version: str
    model: str
    reasoning_effort: str
    prompt_tokens: int
    output_tokens: int | None
    tool_output_bytes: int
    compact_fraction: float | None

    @property
    def effective_prompt_tokens(self):
        return int(self.prompt_tokens * CRITICAL_FRACTION)

    @property
    def compact_tokens(self):
        return None if self.compact_fraction is None else int(self.prompt_tokens * self.compact_fraction)

    def environment(self):
        values = asdict(self)
        return {names[0]: str(values[key]) if values[key] is not None else ''
                for key, names in ENV_FIELDS.items()}


def load_config(path=None, overrides=None, environ=None):
    env = os.environ if environ is None else environ
    defaults = json.loads(DEFAULT_CONFIG.read_text())
    selected = path or env.get('HARNESS_CONFIG')
    if selected:
        supplied = json.loads(Path(selected).expanduser().read_text())
        if not isinstance(supplied, dict):
            raise ValueError('Harness configuration must be a JSON object')
        unknown = set(supplied) - set(defaults)
        if unknown:
            raise ValueError('Unknown harness configuration fields: ' + ', '.join(sorted(unknown)))
        if supplied.get('harness', defaults['harness']) != defaults['harness'] and 'version' not in supplied:
            defaults['version'] = DEFAULT_VERSIONS.get(supplied['harness'], defaults['version'])
        defaults.update(supplied)
    configured_harness = defaults['harness']
    configured_version = version_argument(defaults['version'])
    version_override = None
    for key, names in ENV_FIELDS.items():
        for name in names:
            if name in env and (env[name] != '' or key in ('output_tokens', 'compact_fraction')):
                defaults[key] = env[name]
                if key == 'version':
                    version_override = env[name]
                break
    defaults.update({key: value for key, value in (overrides or {}).items()
                     if value is not None or key in ('output_tokens', 'compact_fraction')})
    version_override = (overrides or {}).get('version') or version_override
    harness = defaults['harness']
    if harness not in DEFAULT_VERSIONS:
        raise ValueError('AGENT_HARNESS must be copilot, pi, codex or claude')
    version = selected_version(harness, version_override or env.get(harness.upper() + '_CLI_VERSION') or
                               (configured_version if harness == configured_harness else None))
    model = defaults['model']
    if not isinstance(model, str) or not model.strip() or any(c in model for c in '\r\n\0'):
        raise ValueError('model must be a nonempty single-line string')
    effort = defaults['reasoning_effort']
    if effort == 'off':
        effort = 'none'
    if effort not in ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'):
        raise ValueError('reasoning_effort must be none, minimal, low, medium, high, xhigh or max')
    if harness == 'claude' and effort in ('none', 'minimal'):
        raise ValueError('Claude Code supports low, medium, high, xhigh or max effort')
    prompt = positive_integer('prompt_tokens', defaults['prompt_tokens'])
    if int(prompt * CRITICAL_FRACTION) <= 16384:
        raise ValueError('prompt_tokens must leave more than 16384 tokens inside the effective context window')
    output = defaults['output_tokens']
    if isinstance(output, bool):
        raise ValueError('output_tokens must be null or a positive integer')
    output = None if output in (None, '', 0, '0') else positive_integer('output_tokens', output)
    if output is not None and output >= int(prompt * CRITICAL_FRACTION):
        raise ValueError('output_tokens must be smaller than the effective prompt window')
    tool_bytes = positive_integer('tool_output_bytes', defaults['tool_output_bytes'])
    fraction = defaults['compact_fraction']
    if fraction in (None, '', 'null'):
        fraction = None
    else:
        if isinstance(fraction, bool):
            raise ValueError('compact_fraction must be null or a number between 0 and 0.95')
        fraction = float(fraction)
        if not math.isfinite(fraction) or not 0 < fraction < CRITICAL_FRACTION:
            raise ValueError('compact_fraction must be null or a number between 0 and 0.95')
    if harness == 'claude' and fraction is not None and not 100000 <= prompt <= 1000000:
        raise ValueError('Claude Code requires a 100000–1000000-token auto-compaction window')
    return HarnessConfig(harness, version, model.strip(), effort, prompt, output, tool_bytes, fraction)


def patch_pi(package, budget):
    """Adjust reviewed JS constants in the container's writable runtime layer."""
    package = Path(package)
    version = json.loads((package / 'package.json').read_text())['version']
    manifest_path = package / 'agensh-limits.json'
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if (previous.get('profile') == PROFILE and previous.get('pi_version') == version
            and previous.get('tool_output_bytes') == budget
            and all(hashlib.sha256((package / name).read_bytes()).hexdigest() == record['after_sha256']
                    for name, record in previous.get('files', {}).items()) and previous.get('files')):
        return
    dist = package / 'dist'
    edits = {}
    truncate = dist / 'core/tools/truncate.js'
    text = truncate.read_text()
    text, lines = re.subn(r'export const DEFAULT_MAX_LINES = (?:2000|Number\.MAX_SAFE_INTEGER);',
                         'export const DEFAULT_MAX_LINES = Number.MAX_SAFE_INTEGER;', text)
    text, bytes_count = re.subn(r'export const DEFAULT_MAX_BYTES = (?:50 \* 1024|\d+);[^\n]*',
                               f'export const DEFAULT_MAX_BYTES = {budget}; // Agensh resource policy', text)
    if lines != 1 or bytes_count != 1:
        raise ValueError('Pi tool modules changed; cannot apply configured output budget')
    edits[truncate] = text
    mcp = dist / 'extensions/mcp/tools.js'
    text, count = re.subn(r'export const MCP_OUTPUT_MAX_BYTES = (?:20 \* 1024|\d+);',
                         f'export const MCP_OUTPUT_MAX_BYTES = {budget};', mcp.read_text())
    if count != 1:
        raise ValueError('Pi MCP modules changed; cannot apply configured output budget')
    edits[mcp] = re.sub(r'Text over (?:20KB|1MB|\d+ bytes)', f'Text over {budget} bytes', text)
    description = re.compile(r'((?:[Oo]utput is truncated to (?:last )?))\$\{DEFAULT_MAX_LINES\} lines or '
                             r'(\$\{DEFAULT_MAX_BYTES\s*/\s*1024\}KB) \(whichever is hit first\)\.')
    for name in ('read.js', 'bash.js'):
        path = dist / 'core/tools' / name
        text, count = description.subn(r'\1\2.', path.read_text())
        if count:
            edits[path] = text
    manifest = {'profile': PROFILE, 'pi_version': version, 'tool_output_bytes': budget,
                'mcp_output_bytes': budget, 'entrypoint': 'dist/rpc-entry.js', 'files': {}}
    for path, text in edits.items():
        before = path.read_bytes()
        manifest['files'][str(path.relative_to(package))] = {
            'before_sha256': hashlib.sha256(before).hexdigest(),
            'after_sha256': hashlib.sha256(text.encode()).hexdigest()}
    for path, text in edits.items():
        if path.read_text() != text:
            path.write_text(text)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


def prepare_native(config):
    if config.harness == 'pi':
        patch_pi('/opt/pi-cli/node_modules/@earendil-works/pi-coding-agent', config.tool_output_bytes)
    elif config.harness == 'codex':
        path = Path('/opt/omcgitea/codex/models.json')
        catalog = json.loads(path.read_text())
        changed = False
        for model in catalog['models']:
            policy = {'mode': 'bytes', 'limit': config.tool_output_bytes}
            if model.get('truncation_policy') != policy or model.get('effective_context_window_percent') != 95:
                model['truncation_policy'] = policy
                model['effective_context_window_percent'] = 95
                changed = True
        if changed:
            path.write_text(json.dumps(catalog) + '\n')


def main():
    shell = len(sys.argv) > 1 and sys.argv[1] == 'shell'
    parser = argparse.ArgumentParser(description=__doc__, add_help=not shell)
    if shell:
        parser.add_argument('-h', '--help', action='store_true', help='Show this help and exit')
    parser.add_argument('--agent-harness', choices=DEFAULT_VERSIONS)
    parser.add_argument('--harness-version', type=version_argument, metavar='VERSION')
    parser.add_argument('--harness-config', type=Path, help='JSON settings file; default: agent/config/harness.json')
    parser.add_argument('--check-profile', type=Path, help='Validate a generated team profile against these settings')
    args = parser.parse_args(sys.argv[2:] if shell else None)
    if shell and args.help:
        print("printf '%s\\n' " + shlex.quote(parser.format_help()) + '\nexit 0')
        return
    try:
        config = load_config(args.harness_config, {'harness': args.agent_harness, 'version': args.harness_version})
        if args.check_profile:
            fields = dict(line.split('=', 1) for line in args.check_profile.read_text().splitlines()
                          if '=' in line and not line.startswith('#'))
            missing = set(config.environment()) - fields.keys()
            if missing:
                raise ValueError('Profile is missing settings; regenerate it: ' + ', '.join(sorted(missing)))
            fields.pop('HARNESS_CONFIG', None)
            actual = load_config(environ=fields)
            differences = [name for name, value in asdict(config).items() if getattr(actual, name) != value]
            if differences:
                raise ValueError('Profile differs from harness configuration; regenerate it: ' + ', '.join(differences))
            return
    except (ValueError, OSError, TypeError) as error:
        parser.error(str(error))
    if shell:
        selected_path = args.harness_config or os.environ.get('HARNESS_CONFIG') or DEFAULT_CONFIG
        values = config.environment() | {'HARNESS_CONFIG': str(Path(selected_path).expanduser().resolve())}
        print('\n'.join('export ' + name + '=' + shlex.quote(value) for name, value in values.items()))
    else:
        print(json.dumps(asdict(config), indent=2))


if __name__ == '__main__':
    main()
