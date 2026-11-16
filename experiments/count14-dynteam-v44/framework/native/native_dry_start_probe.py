#!/usr/bin/env python3
"""OPS-run, no-model native worker pre-CLI probe. No release writes or RPCs.

Run under the actual worker UID in its existing mount/net namespace. A host
collector must separately prove container identity, namespace fence, native
backend priming and resource admission. This probe alone is NOT gate4 PASS.
Only public pinned files are hashed. Private export values never leave process.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import http.client
import json
import os
import re
import socket
import sqlite3
import stat
import subprocess
import sys
import time
import urllib.parse
import uuid

SCHEMA = 'agensh-native-worker-no-model-preflight-v1'
PLAN_SCHEMA = 'agensh-native-worker-no-model-plan-v1'
PUBLIC8 = ('common.py', 'bridge.py', 'native_git_http.py', 'git_http_uds_front.py',
           'native_mcp_policy.py', 'native_mcp_bridge.py', 'mcp_uds_client.py', 'worker_hold.sh')
ENTRY = '/opt/omcgitea/entrypoint.sh'
CUT = '/opt/omcgitea/acp-bridge.py "$ACP_SOCK" 10000 10000 -- \\\n'
SOURCE_PATHS = {
    'agent/entrypoint.sh': ENTRY,
    'agent/acp-bridge.py': '/opt/omcgitea/acp-bridge.py',
    'agent/archive.py': '/opt/omcgitea/archive.py',
    'prompts/agents.txt': '/opt/omcgitea/prompts/agents.md',
    'prompts/pbench-brief.txt': '/opt/omcgitea/prompts/pbench-brief.md',
}
# This list cannot be shortened by a probe plan. CLI binaries are NEVER run.
EXECUTABLES = ('/bin/bash', '/usr/bin/python3', '/usr/bin/git', '/usr/bin/jq',
               '/usr/bin/envsubst', ENTRY, '/opt/omcgitea/acp-bridge.py',
               '/usr/local/bin/copilot-wrapped', '/opt/agentrt/bin/node',
               '/opt/copilot-cli/node_modules/@github/copilot-linux-x64/copilot')
PRIVATE_FILES = ('mcp.json.tmpl', 'copilot-deny-tools.json', 'placeholder.token', 'git.capability')
SOCKETS = ('gitea', 'mattermost', 'board', 'git')
WRITABLE = ('/work', '/opt/data', '/var/run/acp')
CLI_WRAPPER_PATH = '/usr/local/bin/copilot-wrapped'
CLI_DIST = '/opt/copilot-cli/node_modules/@github/copilot-linux-x64'
CLI_RECEIPT_PATH = '/opt/count14/native_cli_tool_receipt.mjs'
READONLY = (CLI_WRAPPER_PATH, CLI_DIST+'/app.js', '/opt/count14', ENTRY, '/opt/omcgitea/config',
            '/run/count14/transport', '/run/count14/release')
ENV_KEYS = ('PATH', 'LANG', 'AGENT_KIND', 'AGENT_NAME', 'GITEA_HOST', 'GITEA_TOKEN_FILE',
            'ANTHROPIC_BASE_URL', 'ANTHROPIC_MODEL', 'ANTHROPIC_API_KEY', 'AGENT_NODE',
            'AGENT_HOME', 'ACP_CHILD_UID', 'ACP_CHILD_GID', 'COPILOT_BIN', 'MATTERMOST_HOST', 'BOARD_SERVICE_URL', 'BOARD_IDS',
            'ORG_NAME', 'COUNT14_REPOSITORY', 'COUNT14_GIT_FRONT_PORT', 'COUNT14_LATE_DELIVERY',
            'COPILOT_PROVIDER_TYPE', 'COPILOT_PROVIDER_WIRE_API', 'COPILOT_AGENT_REASONING_EFFORT',
            'COPILOT_PROVIDER_MAX_PROMPT_TOKENS', 'COPILOT_CLI_DIST_DIR', 'COPILOT_AUTO_UPDATE')

class ProbeFailure(Exception):
    pass

def require(ok, code):
    if not ok:
        raise ProbeFailure(code)

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def strict(raw):
    def pairs(items):
        result = {}
        for key, val in items:
            require(key not in result, 'DUPLICATE_JSON_KEY')
            result[key] = val
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: require(False, 'NONFINITE_JSON'))

class Checks:
    def __init__(self):
        self.rows = []
    def check(self, name, action):
        try:
            action()
        except Exception as error:
            # Never include messages, tracebacks, subprocess output or env values.
            code = str(error) if type(error) is ProbeFailure else 'CHECK_EXCEPTION'
            if not re.fullmatch('[A-Z0-9_]{1,100}', code):
                code = 'CHECK_EXCEPTION'
            self.rows.append({'check': name, 'ok': False, 'code': code,
                              'exception_type': type(error).__name__ if type(error).__module__ == 'builtins' else 'ProbeFailure'})
            return False
        self.rows.append({'check': name, 'ok': True})
        return True
    def result(self, actor, phase, plan_sha):
        failures = [r['check'] for r in self.rows if not r['ok']]
        return {'schema': SCHEMA, 'actor': actor, 'phase': phase, 'plan_sha256': plan_sha,
                'uid': os.getuid(), 'gid': os.getgid(), 'pid': os.getpid(),
                'started_cli_or_acp': False, 'published_release': False,
                'model_requests': 0, 'tool_business_rpc': 0,
                'status': 'WORKER_CHECKS_PASS_NOT_HOST_OR_GATE4_PASS' if not failures else 'FAIL',
                'failed_checks': failures, 'checks': self.rows}

class WorkerFS:
    """Root mapping is for OWN tests only; CLI always uses actual worker '/'."""
    def __init__(self, root=Path('/')):
        self.root = Path(root)
    def path(self, name):
        require(type(name) is str and name.startswith('/') and '..' not in name.split('/'), 'FIXED_ABSOLUTE_PATH')
        return self.root / name.lstrip('/')
    def readonly(self, name):
        return bool(os.statvfs(self.path(name)).f_flag & os.ST_RDONLY)
    def writable(self, name, uid):
        p = self.path(name)
        st = p.lstat()
        require(stat.S_ISDIR(st.st_mode) and st.st_uid == uid, 'WRITABLE_MOUNT_DIRECTORY_UID')
        probe = p / ('.count14-dry-' + uuid.uuid4().hex)
        fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, b'count14-no-model-own-probe\n')
            os.fsync(fd)
        finally:
            os.close(fd)
            probe.unlink()
    def public(self, name, pin, *, exact_mode=None):
        p = self.path(name)
        st = p.lstat()
        require(stat.S_ISREG(st.st_mode) and not st.st_mode & 0o022, 'PUBLIC_REGULAR_NOT_GROUP_WORLD_WRITABLE')
        if exact_mode is not None:
            require(stat.S_IMODE(st.st_mode) == exact_mode, 'PUBLIC_EXACT_MODE')
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            h, count = hashlib.sha256(), 0
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
                count += len(chunk)
            stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode)
            require(stamp(before) == stamp(os.fstat(fd)) == stamp(p.lstat()), 'PUBLIC_CHANGED_DURING_READ')
            require({'bytes': count, 'sha256': h.hexdigest()} == pin, 'PUBLIC_PIN_MISMATCH')
        finally:
            os.close(fd)
    def executable(self, name):
        p = self.path(name)
        st = p.stat()  # Original image executable symlinks are permitted here.
        require(stat.S_ISREG(st.st_mode) and not st.st_mode & 0o022, 'EXECUTABLE_REGULAR_NOT_WRITABLE')
        require(os.access(p, os.R_OK | os.X_OK), 'EXECUTABLE_UID_READ_EXECUTE')
        require(not os.statvfs(p).f_flag & os.ST_NOEXEC, 'EXECUTABLE_MOUNT_NOEXEC')
    def private_read(self, name, uid):
        p = self.path(name)
        s = p.lstat()
        require(stat.S_ISREG(s.st_mode) and s.st_uid in (0, uid) and not s.st_mode & 0o022,
                'PRIVATE_EXPORT_OWNER_MODE')
        with p.open('rb') as f:
            require(bool(f.read(1)), 'PRIVATE_EXPORT_EMPTY')
    def release(self, actor, phase):
        p = self.path('/run/count14/release')
        s = p.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid != os.getuid() and stat.S_IMODE(s.st_mode) == 0o711,
                'RELEASE_HOST_OWNED_0711')
        require(not os.access(p, os.W_OK), 'RELEASE_WORKER_NOT_WRITABLE')
        require(not os.path.lexists(p / 'ALLOW_CLI'), 'ALLOW_CLI_MUST_REMAIN_ABSENT')
        flag = p / 'PORTS_READY'
        if phase == 'held':
            require(not os.path.lexists(flag), 'HELD_PORTS_READY_MUST_BE_ABSENT')
        else:
            st = flag.lstat()
            require(stat.S_ISREG(st.st_mode) and st.st_uid == s.st_uid and stat.S_IMODE(st.st_mode) == 0o444,
                    'PORTS_READY_HOST_EXACT0444')
            require(flag.read_bytes() == (actor + '\n').encode(), 'PORTS_READY_EXACT_ACTOR')
    def socket_access(self, purpose):
        p = self.path('/run/count14/transport/' + purpose + '.sock')
        require(stat.S_ISSOCK(p.lstat().st_mode) and os.access(p, os.R_OK | os.W_OK), 'ROLE_SOCKET_ACCESS')
        # Do NOT connect: an empty unauthenticated connection could fault owner.
    def unix_bind(self):
        p = self.path('/var/run/acp') / ('.dry-' + uuid.uuid4().hex[:12])
        s = socket.socket(socket.AF_UNIX)
        try:
            s.bind(str(p))
        finally:
            s.close()
            if p.exists():
                p.unlink()
    def sqlite(self):
        p = self.path('/opt/data') / ('.dry-sqlite-' + uuid.uuid4().hex)
        first = second = None
        try:
            first = sqlite3.connect(p, timeout=0)
            first.execute('create table own_probe(n integer)')
            first.commit()
            first.execute('begin immediate')
            second = sqlite3.connect(p, timeout=0)
            try:
                second.execute('begin immediate')
            except sqlite3.OperationalError as error:
                require(getattr(error, 'sqlite_errorcode', None) == sqlite3.SQLITE_BUSY, 'SQLITE_EXPECTED_BUSY')
            else:
                raise ProbeFailure('SQLITE_LOCK_NOT_EXCLUSIVE')
        finally:
            if second is not None:
                second.close()
            if first is not None:
                first.close()
            for suffix in ('', '-wal', '-shm', '-journal'):
                try:
                    Path(str(p) + suffix).unlink()
                except FileNotFoundError:
                    pass

def validate_plan(p):
    require(type(p) is dict and set(p) == {'schema', 'actor', 'uid', 'gid', 'phase',
            'git_front_port', 'relay_health_url', 'public_pins', 'deny_rules'}, 'PLAN_FIELDS')
    require(p['schema'] == PLAN_SCHEMA and p['uid'] == p['gid'] == 10000, 'PLAN_SCHEMA_UID')
    require(type(p['actor']) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.+-]{0,127}', p['actor']), 'PLAN_ACTOR')
    require(p['phase'] in ('held', 'ports'), 'PLAN_PHASE')
    require(type(p['git_front_port']) is int and 1 <= p['git_front_port'] <= 65535, 'PLAN_FRONT_PORT')
    health_target(p['relay_health_url'])
    pins = p['public_pins']
    required = set(SOURCE_PATHS.values()) | {'/opt/count14/' + n for n in PUBLIC8} | {CLI_WRAPPER_PATH, CLI_RECEIPT_PATH}
    require(type(pins) is dict and required <= set(pins), 'PLAN_FIXED_PUBLIC_CLOSURE')
    cli = []
    for path, pin in pins.items():
        if path not in required:
            require(path.startswith('/opt/copilot-cli/node_modules/@github/') and '..' not in path.split('/')
                    and str(PurePosixPath(path)) == path, 'PLAN_PUBLIC_PATH_ONLY')
            cli.append(path)
        require(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and type(pin['bytes']) is int
                and pin['bytes'] >= 0 and type(pin['sha256']) is str
                and re.fullmatch('[0-9a-f]{64}', pin['sha256']), 'PLAN_PUBLIC_PIN')
    require(len(cli) == 191, 'PLAN_ORIGINAL_CLI191_REQUIRED')
    require(type(p['deny_rules']) is list and p['deny_rules'] and all(type(n) is str for n in p['deny_rules']), 'PLAN_ORIGINAL_DENY_RULES')
    return p

def health_target(url):
    require(type(url) is str, 'HEALTH_URL')
    u = urllib.parse.urlsplit(url)
    require(u.scheme == 'http' and u.hostname and u.port and u.path == '/healthz'
            and not u.username and not u.password and not u.query and not u.fragment, 'HEALTH_GET_ONLY_FIXED_PATH')
    return u.hostname, u.port

def safe_get(host, port, path, expected):
    # No proxy support, redirects, authentication, body, retry, model route or RPC.
    c = http.client.HTTPConnection(host, port, timeout=3)
    try:
        c.request('GET', path, headers={'Connection': 'close'})
        r = c.getresponse()
        require(r.status == expected, 'HEALTH_HTTP_STATUS')
        # Deliberately do not read/log response body.
    finally:
        c.close()

def safe_environment(env):
    return {key: env[key] for key in ENV_KEYS if key in env}

def shell_syntax(path, env):
    r = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-n', str(path)],
                       env=safe_environment(env), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    require(r.returncode == 0, 'SHELL_SYNTAX_EXIT_NONZERO')

def node_dependencies(env):
    # Resolve without loading npm-loader (which immediately spawns native CLI).
    # No package module is executed and no model/network library is imported.
    program = "const fs=require('node:fs');const {createRequire}=require('node:module');const r=createRequire('/opt/copilot-cli/node_modules/@github/copilot/npm-loader.js');for(const n of ['detect-libc','@github/copilot-linux-x64']){const p=r.resolve(n);fs.accessSync(p,fs.constants.R_OK)}"
    r = subprocess.run(['/opt/agentrt/bin/node', '-e', program],
                       env=safe_environment(env), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    require(r.returncode == 0, 'NATIVE_NODE_LOADER_DEPENDENCY_NONZERO')


def pre_cli_source(raw, expected_sha):
    require(sha(raw) == expected_sha, 'PRECLI_ORIGINAL_ENTRYPOINT_SHA')
    text = raw.decode('utf-8')
    require(text.count(CUT) == 1, 'PRECLI_UNIQUE_ORIGINAL_CUT')
    return (text[:text.index(CUT)] + '\n# No ACP/CLI/router or model is started by this dry probe.\nexit 0\n').encode()

def run_pre_cli(raw, expected_sha, env):
    script = pre_cli_source(raw, expected_sha)
    r = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-s'], input=script,
                       env=safe_environment(env), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    require(r.returncode == 0, 'ORIGINAL_PRECLI_EXIT_NONZERO')

def check_environment(env, p):
    expected = {'AGENT_NAME': p['actor'], 'COUNT14_LATE_DELIVERY': '1',
                'COUNT14_GIT_FRONT_PORT': str(p['git_front_port']),
                'GITEA_HOST': 'http://127.0.0.1:' + str(p['git_front_port']),
                'GITEA_TOKEN_FILE': '/run/count14/transport/placeholder.token',
                'MATTERMOST_HOST': '', 'BOARD_SERVICE_URL': 'count14-fixed-uds',
                'COPILOT_CLI_DIST_DIR': CLI_DIST, 'COPILOT_AUTO_UPDATE': 'false'}
    for key, value in expected.items():
        require(env.get(key) == value, 'WORKER_ENV_BINDING')
    require(env.get('AGENT_HOME', '/opt/data') == '/opt/data', 'WORKER_FIXED_HOME')
    require(env.get('COPILOT_BIN') == '/usr/local/bin/copilot-wrapped', 'WORKER_ORIGINAL_CLI_WRAPPER')
    require(env.get('COPILOT_PROVIDER_TYPE', 'openai') == 'openai' and bool(env.get('ANTHROPIC_API_KEY')), 'WORKER_PROVIDER_CREDENTIAL_PRESENT')
    base = urllib.parse.urlsplit(env.get('ANTHROPIC_BASE_URL', ''))
    host, port = health_target(p['relay_health_url'])
    require(base.scheme == 'http' and base.hostname == host and base.port == port
            and not base.username and not base.password and not base.query and not base.fragment,
            'WORKER_PROVIDER_EXACT_RELAY')
    require(not any(env.get(k) for k in ('GITEA_ACCESS_TOKEN', 'MATTERMOST_TOKEN', 'MATTERMOST_TOKEN_FILE',
                'DOCKER_HOST', 'DOCKER_CERT_PATH', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
                'http_proxy', 'https_proxy', 'all_proxy', 'BASH_ENV', 'NODE_OPTIONS', 'NODE_PATH',
                'COPILOT_GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN', 'GITHUB_COPILOT_API_TOKEN')), 'NO_BACKEND_OR_PROXY_CREDENTIALS')

def check_mcp(fs, plan):
    # Only structure/guard results escape; capability/placeholder values do not.
    template = fs.path('/opt/omcgitea/config/mcp.json.tmpl').read_bytes()
    require(template == fs.path('/run/count14/transport/mcp.json.tmpl').read_bytes(), 'CONFIG_ROLE_EXPORT_SAME_BYTES')
    cfg = strict(template)
    require(set(cfg) == {'mcpServers'} and set(cfg['mcpServers']) == set(SOCKETS) - {'git'}, 'CONFIG_NATIVE_SERVER_SET')
    for purpose, server in cfg['mcpServers'].items():
        require(set(server) == {'type', 'timeout', 'command', 'args', 'env'}
                and server['type'] == 'stdio' and server['timeout'] in ('180000', 180000)
                and server['command'] == '/usr/bin/python3'
                and server['args'] == ['-B', '/opt/count14/mcp_uds_client.py'], 'CONFIG_FIXED_STDIO_COMMAND')
        env = server['env']
        require(set(env) == {'AGENSH_MCP_SOCKET', 'AGENSH_MCP_CAPABILITY'}
                and env['AGENSH_MCP_SOCKET'] == '/run/count14/transport/' + purpose + '.sock'
                and type(env['AGENSH_MCP_CAPABILITY']) is str and len(env['AGENSH_MCP_CAPABILITY']) >= 48,
                'CONFIG_FIXED_ROLE_SOCKET_CAPABILITY')
    deny = strict(fs.path('/opt/omcgitea/config/copilot-deny-tools.json').read_bytes())
    require(deny == plan['deny_rules'] == strict(fs.path('/run/count14/transport/copilot-deny-tools.json').read_bytes()), 'ORIGINAL_DENIALS_UNCHANGED')
    require(fs.path('/run/count14/transport/placeholder.token').read_bytes() == b'count14-no-backend-authority\n', 'PLACEHOLDER_NOT_BACKEND_AUTHORITY')

def run_worker(plan, *, fs=None, env=None, network=safe_get, prelude=run_pre_cli):
    c = Checks()
    if not c.check('plan.valid', lambda: validate_plan(plan)):
        return c.result('invalid-plan', 'unknown', sha(canonical(plan)))
    fs, env = fs or WorkerFS(), os.environ if env is None else env
    actor, phase, uid = plan['actor'], plan['phase'], plan['uid']
    c.check('identity.actual_uid_gid', lambda: require(os.getuid() == uid and os.getgid() == plan['gid'], 'ACTUAL_WORKER_UID_GID'))
    def umask_check():
        # Read metadata without transiently changing a process-wide umask.
        line = next(l for l in Path('/proc/self/status').read_text().splitlines() if l.startswith('Umask:'))
        require(int(line.split()[1], 8) == 0o077, 'PROBE_MUST_INHERIT_UMASK077')
    c.check('identity.actual_umask', umask_check)
    c.check('identity.no_extra_groups', lambda: require(set(os.getgroups()) <= {uid}, 'NO_EXTRA_WORKER_GROUPS'))
    for key in ('ACP_CHILD_UID', 'ACP_CHILD_GID'):
        c.check('environment.' + key, lambda key=key: require(env.get(key) == '10000', 'ACP_CHILD_NONROOT_UID_GID'))
    c.check('environment.native_onlyrelay', lambda: check_environment(env, plan))
    c.check('release.before', lambda: fs.release(actor, phase))
    for path in READONLY:
        c.check('mount.readonly:' + path, lambda path=path: require(fs.readonly(path), 'MOUNT_NOT_READONLY'))
    for path in WRITABLE:
        c.check('mount.write_uid_fsync:' + path, lambda path=path: fs.writable(path, uid))
    c.check('runtime.acp_unix_bind', fs.unix_bind)
    c.check('runtime.sqlite_exclusive_lock', fs.sqlite)
    for path, pin in sorted(plan['public_pins'].items()):
        c.check('public.read_sha:' + path, lambda path=path, pin=pin: fs.public(path, pin, exact_mode=0o555 if path==CLI_WRAPPER_PATH else (0o444 if path.startswith('/opt/count14/') else None)))
    for path in EXECUTABLES:
        c.check('runtime.read_execute:' + path, lambda path=path: fs.executable(path))
    c.check('runtime.agent_node_read_execute', lambda: fs.executable(env.get('AGENT_NODE', '/usr/local/bin/node')))
    for name in ('worker_hold.sh',):
        c.check('syntax:' + name, lambda name=name: shell_syntax(fs.path('/opt/count14/' + name), env))
    c.check('syntax:original_entrypoint', lambda: shell_syntax(fs.path(ENTRY), env))
    c.check('runtime.native_node_loader_dependencies', lambda: node_dependencies(env))
    for path in ('/opt/omcgitea/acp-bridge.py', '/opt/omcgitea/archive.py') + tuple('/opt/count14/' + n for n in PUBLIC8 if n.endswith('.py')):
        c.check('syntax.python:' + path, lambda path=path: compile(fs.path(path).read_bytes(), path, 'exec'))
    host, port = health_target(plan['relay_health_url'])
    c.check('network.relay_health_get_only', lambda: network(host, port, '/healthz', 200))
    if phase == 'ports':
        for name in PRIVATE_FILES:
            c.check('export.uid_read:' + name, lambda name=name: fs.private_read('/run/count14/transport/' + name, uid))
        for purpose in SOCKETS:
            c.check('export.socket_stat_access:' + purpose, lambda purpose=purpose: fs.socket_access(purpose))
        config_ok = c.check('export.original_mcp_guards', lambda: check_mcp(fs, plan))
        c.check('network.loopback_git_nonbusiness_403', lambda: network('127.0.0.1', plan['git_front_port'], '/__count14_no_model_preflight__', 403))
        # Running the exact reviewed prefix exercises original envsubst/jq/HOME/
        # Git credentials/SQLite prep. A bad config must never reach that prefix.
        if config_ok and all(row['ok'] for row in c.rows):
            c.check('runtime.original_entrypoint_precli', lambda: prelude(fs.path(ENTRY).read_bytes(), plan['public_pins'][ENTRY]['sha256'], env))
        else:
            c.check('runtime.original_entrypoint_precli', lambda: require(False, 'PRECLI_SKIPPED_UNSAFE_OR_FAILED_ADMISSION'))
    c.check('release.after', lambda: fs.release(actor, phase))
    return c.result(actor, phase, sha(canonical(plan)))

def make_plan(base, *, actor, phase, port, relay_health_url):
    """Trusted local public inputs only. Does not inspect worker/task/service state."""
    base = Path(base)
    pins = {}
    origin = strict((base / 'NATIVE_PUBLIC105_CONSUMED.json').read_bytes())
    source = base.parent / 'operations-agensh-comparison-20261026/native-public-text105-transfer-v1/source'
    by_name = {row['path']: row for row in origin['sources']}
    for name, target in SOURCE_PATHS.items():
        raw = (source / name).read_bytes()
        require(sha(raw) == by_name[name]['sha256'], 'ORIGINAL_PUBLIC_INPUT_CHANGED')
        pins[target] = {'bytes': len(raw), 'sha256': sha(raw)}
    from native_worker_launch import HOLD_SCRIPT
    for name in PUBLIC8:
        raw = HOLD_SCRIPT.encode() if name == 'worker_hold.sh' else (base / name).read_bytes()
        pins['/opt/count14/' + name] = {'bytes': len(raw), 'sha256': sha(raw)}
    index_path = base.parent / 'operations-agensh-comparison-20261026/public-installed-copilot-static-export-v1/PUBLIC_INSTALLED_CLI_CLOSURE_INDEX_V1.json'
    index_raw = index_path.read_bytes()
    require(sha(index_raw) == '3c7719c87126f0dae6c19b43bbcfe60bb6bd507f844d7e4afde40603dced8a8d', 'ORIGINAL_CLI_INDEX_PIN')
    index = strict(index_raw)
    for row in index['files']:
        pins['/opt/copilot-cli/node_modules/' + row['path']] = {k: row[k] for k in ('bytes', 'sha256')}
    from native_cli_tool_overlay import build_app, CLI_WRAPPER
    app = index_path.parent/'source/@github/copilot-linux-x64/app.js'
    patched = build_app(app.read_bytes())
    pins[CLI_DIST+'/app.js'] = {'bytes':len(patched),'sha256':sha(patched)}
    client = (base/'native-cli-tool-receipt-v1/native_cli_tool_receipt.mjs').read_bytes()
    pins[CLI_RECEIPT_PATH] = {'bytes':len(client),'sha256':sha(client)}
    pins[CLI_WRAPPER_PATH] = {'bytes':len(CLI_WRAPPER.encode()),'sha256':sha(CLI_WRAPPER.encode())}
    deny = (source / 'agent/config/copilot-deny-tools.json').read_bytes()
    require(sha(deny) == by_name['agent/config/copilot-deny-tools.json']['sha256'], 'ORIGINAL_DENY_INPUT_CHANGED')
    plan = {'schema': PLAN_SCHEMA, 'actor': actor, 'uid': 10000, 'gid': 10000,
            'phase': phase, 'git_front_port': port, 'relay_health_url': relay_health_url,
            'public_pins': pins, 'deny_rules': strict(deny)}
    return validate_plan(plan)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    args = parser.parse_args()
    try:
        raw = Path(args.plan).read_bytes()
        require(len(raw) <= 256 * 1024, 'PUBLIC_PLAN_BOUND')
        plan = strict(raw)
        result = run_worker(plan)
    except Exception:
        # Invalid input can include secrets: no argument/raw/exception echo.
        result = {'schema': SCHEMA, 'status': 'FAIL', 'failed_checks': ['plan.input'],
                  'model_requests': 0, 'published_release': False, 'started_cli_or_acp': False}
    print(canonical(result).decode())
    return 0 if result['status'] == 'WORKER_CHECKS_PASS_NOT_HOST_OR_GATE4_PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
