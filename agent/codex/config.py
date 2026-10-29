#!/usr/bin/env python3
"""Configure Codex with shared model settings and MCP tools."""

import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_config import INFERENCE_MAX_RETRIES, REQUEST_TIMEOUT_MS, load_config, write_private


def codex_home():
    return Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))


def toml(value, prefix=()):
    lines = []
    if prefix:
        lines.append('[' + '.'.join(json.dumps(key) for key in prefix) + ']')
    for key, item in value.items():
        if not isinstance(item, dict):
            lines.append(json.dumps(key) + ' = ' + json.dumps(item, ensure_ascii=False))
    for key, item in value.items():
        if isinstance(item, dict):
            lines.extend(['', *toml(item, prefix + (key,))])
    return lines


def configure(mcp_config=None, deny_tools=None):
    settings = load_config()
    base_url = (os.environ.get('CODEX_PROVIDER_BASE_URL') or os.environ['ANTHROPIC_BASE_URL']).rstrip('/')
    if not base_url.endswith('/v1'):
        base_url += '/v1'
    if os.environ.get('CODEX_PROVIDER_WIRE_API', 'responses') != 'responses':
        raise ValueError('Codex experiments require CODEX_PROVIDER_WIRE_API=responses')
    config = {
        'model': settings.model,
        'model_provider': 'agensh', 'model_reasoning_effort': settings.reasoning_effort,
        'model_verbosity': 'low',
        'model_context_window': settings.prompt_tokens, 'approval_policy': 'never',
        'model_catalog_json': '/opt/omcgitea/codex/models.json',
        # Retain native history management; the Codex proxy enforces the exact
        # byte ceiling. A token override would replace this catalog policy.
        'project_doc_max_bytes': 1048576,
        'background_terminal_max_timeout': REQUEST_TIMEOUT_MS,
        # Docker, the worker UID and reference file permissions provide isolation.
        'sandbox_mode': 'danger-full-access', 'web_search': 'disabled',
        'check_for_update_on_startup': False,
        'analytics': {'enabled': False}, 'feedback': {'enabled': False},
        'agents': {'enabled': False},
        'features': {'multi_agent': False, 'goals': False, 'apps': False, 'tool_suggest': False,
                     'api_key_model_discovery': False, 'enable_request_compression': False,
                     'daemon_auto_start': False},
        'model_providers': {'agensh': {
            'name': 'Agensh', 'base_url': base_url, 'wire_api': 'responses',
            'env_key': 'CODEX_PROVIDER_API_KEY', 'requires_openai_auth': False,
            'supports_websockets': False,
            'request_max_retries': INFERENCE_MAX_RETRIES,
            'stream_max_retries': INFERENCE_MAX_RETRIES,
            'stream_idle_timeout_ms': REQUEST_TIMEOUT_MS,
        }},
    }
    if settings.compact_tokens is not None:
        config['model_auto_compact_token_limit'] = settings.compact_tokens
        config['model_auto_compact_token_limit_scope'] = 'total'
    servers = {}
    if mcp_config is not None:
        for name, server in json.loads(Path(mcp_config).read_text())['mcpServers'].items():
            timeout = float(server.get('timeout', 180000)) / 1000
            servers[name] = {key: server[key] for key in ('command', 'args', 'env', 'cwd') if key in server}
            servers[name].update(startup_timeout_sec=timeout, tool_timeout_sec=timeout, required=True)
        if deny_tools is not None:
            rules = json.loads(Path(deny_tools).read_text())
            if not rules:
                raise ValueError('No MCP tool exclusions configured')
            for rule in rules:
                match = re.fullmatch(r'([^()]+)\(([^()]+)\)', rule)
                if match is None:
                    raise ValueError('Invalid MCP exclusion: ' + rule)
                server, tool = match.groups()
                if server in servers:
                    servers[server].setdefault('disabled_tools', []).append(tool)
    if servers:
        config['mcp_servers'] = servers
    write_private(codex_home() / 'config.toml', '\n'.join(toml(config)) + '\n')
    return config


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mcp-config', type=Path)
    parser.add_argument('--deny-tools', type=Path)
    args = parser.parse_args()
    configure(args.mcp_config, args.deny_tools)
