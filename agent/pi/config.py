#!/usr/bin/env python3
"""Install shared model settings and MCP configuration for Pi."""

import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_config import (INFERENCE_MAX_RETRIES, REQUEST_TIMEOUT_MS,
                            RETRY_BASE_DELAY_MS, RETRY_MAX_DELAY_MS, load_config,
                            write_private_json as write_private)


def agent_dir():
    return Path(os.environ.get('PI_CODING_AGENT_DIR', str(Path.home() / '.pi/agent')))


def configure(mcp_config=None, deny_tools=None):
    config = load_config()
    directory = agent_dir()
    base_url = os.environ.get('PI_PROVIDER_BASE_URL') or os.environ['ANTHROPIC_BASE_URL']
    base_url = base_url.rstrip('/')
    if not base_url.endswith('/v1'):
        base_url += '/v1'
    wire_api = os.environ.get('PI_PROVIDER_WIRE_API', 'responses')
    if wire_api != 'responses':
        raise ValueError('Pi experiments require PI_PROVIDER_WIRE_API=responses')
    model = config.model
    effort = 'off' if config.reasoning_effort == 'none' else config.reasoning_effort
    effective_window = config.effective_prompt_tokens
    key = os.environ.get('PI_PROVIDER_API_KEY') or os.environ.get('ANTHROPIC_API_KEY', 'local-proxy-no-auth')
    write_private(directory / 'models.json', {'providers': {'agensh': {
        'api': 'openai-responses', 'baseUrl': base_url, 'apiKey': key, 'authHeader': True,
        'models': [{'id': model, 'name': model, 'reasoning': True, 'input': ['text'],
                    # Pi needs numeric planning metadata. The proxy applies
                    # output_tokens independently as the generation cap.
                    'contextWindow': effective_window, 'maxTokens': 16384,
                    'thinkingLevelMap': {'xhigh': 'xhigh', 'max': 'max'},
                    'compat': {'supportsMaxOutputTokens': False},
                    'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0}}],
    }}})
    settings = {
        'defaultProvider': 'agensh', 'defaultModel': model, 'defaultThinkingLevel': effort,
        'defaultProjectTrust': 'never', 'enableInstallTelemetry': False, 'cacheWarming': 'off',
        'httpIdleTimeoutMs': REQUEST_TIMEOUT_MS,
        'retry': {'enabled': True, 'maxRetries': INFERENCE_MAX_RETRIES,
                  'baseDelayMs': RETRY_BASE_DELAY_MS, 'maxAgentDelayMs': RETRY_MAX_DELAY_MS,
                  'provider': {'timeoutMs': REQUEST_TIMEOUT_MS, 'maxRetries': 0,
                               'maxRetryDelayMs': RETRY_MAX_DELAY_MS}},
    }
    if config.compact_tokens is not None:
        settings['compaction'] = {'enabled': True,
            'reserveTokens': effective_window - config.compact_tokens,
            'keepRecentTokens': min(20000, config.compact_tokens // 2)}
    write_private(directory / 'settings.json', settings)
    servers = {}
    if mcp_config is not None:
        servers = json.loads(Path(mcp_config).read_text())['mcpServers']
        for server in servers.values():
            # Copilot uses milliseconds; Pi's MCP timeout is in seconds.
            server['timeout'] = float(server.get('timeout', 180000)) / 1000
            server['exposure'] = 'direct'
        if deny_tools is not None:
            rules = json.loads(Path(deny_tools).read_text())
            if not rules:
                raise ValueError('No MCP tool exclusions configured')
            for rule in rules:
                match = re.fullmatch(r'([^()]+)\(([^()]+)\)', rule)
                if match is None:
                    raise ValueError('Invalid MCP exclusion: ' + rule)
                server_name, tool = match.groups()
                if server_name in servers:
                    servers[server_name].setdefault('toolExposure', {})[tool] = 'hidden'
    write_private(directory / 'mcp.json', {'mcpServers': servers})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mcp-config', type=Path)
    parser.add_argument('--deny-tools', type=Path)
    arguments = parser.parse_args()
    configure(arguments.mcp_config, arguments.deny_tools)
