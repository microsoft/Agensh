#!/usr/bin/env python3
"""Configure the native Claude Code runtime and shared MCP servers."""

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_config import REQUEST_TIMEOUT_MS, load_config, write_private_json as write_private

# Keep Agensh in charge of peers and scheduling. Skills and local coding tools stay enabled.
TOOLS = ('Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep', 'NotebookEdit', 'Skill',
         'TodoWrite', 'TaskCreate', 'TaskGet', 'TaskList', 'TaskUpdate')


def config_dir():
    return Path(os.environ.get('CLAUDE_CONFIG_DIR', str(Path.home() / '.claude')))


def native_environment(settings):
    if os.environ.get('CLAUDE_PROVIDER_WIRE_API', 'messages') != 'messages':
        raise ValueError('Claude Code requires the native Messages API')
    base = os.environ['ANTHROPIC_BASE_URL'].rstrip('/')
    if base.endswith('/v1'):
        base = base[:-3]
    values = {
        'ANTHROPIC_BASE_URL': base, 'ANTHROPIC_API_KEY': os.environ.get('ANTHROPIC_API_KEY', 'local-proxy-no-auth'),
        'ANTHROPIC_MODEL': settings.model, 'ANTHROPIC_DEFAULT_HAIKU_MODEL': settings.model,
        'ANTHROPIC_DEFAULT_SONNET_MODEL': settings.model, 'ANTHROPIC_DEFAULT_OPUS_MODEL': settings.model,
        'ANTHROPIC_SMALL_FAST_MODEL': settings.model,
        'CLAUDE_CONFIG_DIR': str(config_dir()), 'DISABLE_AUTOUPDATER': '1',
        'DISABLE_TELEMETRY': '1', 'DISABLE_ERROR_REPORTING': '1',
        'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1', 'ENABLE_CLAUDEAI_MCP_SERVERS': 'false',
        # Forked skills need native base-agent definitions. The CLI tool
        # allowlist still leaves peer-agent delegation under Agensh's control.
        'ENABLE_TOOL_SEARCH': 'false', 'CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS': '0',
        'CLAUDE_CODE_MAX_CONTEXT_TOKENS': str(settings.prompt_tokens),
        'MAX_MCP_OUTPUT_TOKENS': str(settings.tool_output_bytes),
        'BASH_MAX_OUTPUT_LENGTH': str(min(settings.tool_output_bytes, 150000)),
        'API_TIMEOUT_MS': str(REQUEST_TIMEOUT_MS), 'MCP_TIMEOUT': '180000', 'MCP_TOOL_TIMEOUT': '180000',
    }
    if settings.output_tokens is not None:
        values['CLAUDE_CODE_MAX_OUTPUT_TOKENS'] = str(settings.output_tokens)
    if settings.compact_fraction is not None:
        values['CLAUDE_CODE_AUTO_COMPACT_WINDOW'] = str(settings.prompt_tokens)
        values['CLAUDE_AUTOCOMPACT_PCT_OVERRIDE'] = format(settings.compact_fraction * 100, '.12g')
    return values


def configure(mcp_config=None):
    settings = load_config()
    env = native_environment(settings)
    directory = config_dir()
    write_private(directory / 'settings.json', {'model': settings.model,
        'effortLevel': settings.reasoning_effort, 'autoMemoryEnabled': False,
        'bashOutputMaxChars': min(settings.tool_output_bytes, 150000), 'env': env})
    servers = {}
    if mcp_config is not None:
        for name, source in json.loads(Path(mcp_config).read_text())['mcpServers'].items():
            servers[name] = {key: source[key] for key in ('type', 'command', 'args', 'env', 'cwd') if key in source}
    write_private(directory / 'mcp.json', {'mcpServers': servers})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mcp-config', type=Path)
    args = parser.parse_args()
    configure(args.mcp_config)
