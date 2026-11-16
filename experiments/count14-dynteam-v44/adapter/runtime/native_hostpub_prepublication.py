"""Read-only hard prerequisite BEFORE the first source/Gitea side effect.

OPS remains the sole installer of each approved, exact NAT/sysctl pattern.
Missing rules/route readiness HOLD the original pump, without a ledger event,
fault, Gitea allocation, private publication directory, or HTTP request. Once
ready, this SAME owner checks the two original unauthenticated infrastructure
GET headers, never their bodies, and retains an exclusive public receipt.

There is no installer, model probe, SQL, live-owner injection, clock reset,
retry of Gitea, or exception-to-green path in this module.
"""
from dataclasses import asdict
from pathlib import Path
import hashlib
import http.client
import ipaddress
import json
import os
import re
import shlex
import stat
import subprocess
import time

from common import need, digest
from native_host_environment import infra_labels
from native_peer_registry import process_birth

WAITING = 'WAITING_EXACT_HOST_PUBLISH_READY'
READY = 'EXACT_HOST_PUBLISH_HEADERS200_BEFORE_GITEA'
PROJECTION = ('{"id":{{json .Id}},"networks":{{json .NetworkSettings.Networks}},'
              '"ports":{{json .NetworkSettings.Ports}}}')
NETWORK = ('{"id":{{json .Id}},"name":{{json .Name}},"driver":{{json .Driver}},'
           '"scope":{{json .Scope}},"labels":{{json .Labels}},'
           '"ipam":{{json .IPAM.Config}},"options":{{json .Options}}}')


def _read(path):
    return Path(path).read_text(encoding='ascii').strip()


def _run(argv):
    # All callers below supply fixed read-only executables/verbs, never a shell.
    child = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, timeout=3,
        env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'}, cwd='/')
    need(child.returncode == 0 and len(child.stdout) <= 4 * 1024**2,
         'HOSTPUB_FIXED_READONLY_CONTROL_COMMAND_FAILED')
    return child.stdout


def _ports(host):
    # This original private env is runtime-only; only these two PUBLIC port
    # scalars escape. Never return/log/hash its credential values or file.
    path = Path(host['envfile']); s = path.lstat()
    need(path.is_absolute() and path.resolve() == path and stat.S_ISREG(s.st_mode)
         and s.st_uid == os.geteuid() and s.st_nlink == 1
         and stat.S_IMODE(s.st_mode) == 0o400 and s.st_size <= 65536,
         'HOSTPUB_ORIGINAL_NATIVE_ENV_IDENTITY')
    selected = {}
    for line in path.read_text().splitlines():
        key, sep, value = line.partition('=')
        if key in ('EDGE_HTTP_PORT', 'EDGE_MM_PORT'):
            need(sep and key not in selected and value.isascii() and value.isdigit()
                 and 0 < int(value) < 65536, 'HOSTPUB_TWO_ORIGINAL_PUBLIC_PORTS')
            selected[key] = int(value)
    need(set(selected) == {'EDGE_HTTP_PORT', 'EDGE_MM_PORT'} and
         len(set(selected.values())) == 2, 'HOSTPUB_TWO_DISTINCT_REGISTERED_PORTS')
    return [selected['EDGE_HTTP_PORT'], selected['EDGE_MM_PORT']]


def _topology(core, t):
    row = core.rows[t]; net = core.native_networks[t]
    need(row in core.contract['trajectories'] and row['trajectory_id'] == t,
         'HOSTPUB_EXACT_CONTRACT_ROW')
    net.checked(contract=core.contract, row=row, qualification_only=core.qualification_only)
    docker = core.native_containers.docker
    need(docker.route.qualification_only is core.qualification_only,
         'HOSTPUB_SAME_ORIGINAL_PRIVATE_DAEMON')
    docker.verify_daemon()
    expected = infra_labels(core, t, 'nginx-edge')
    ids = docker.list_scope_ids(expected)
    need(len(ids) == 1, 'HOSTPUB_UNIQUE_EXACT_NGINX_CID')
    state = docker.inspect(ids[0])
    labels = {k: expected[v] for k, v in {
        'root': 'count14.root', 'trajectory': 'count14.trajectory-sha256',
        'contract': 'count14.contract-sha256', 'role': 'count14.role',
        'component': 'count14.component'}.items()}
    host = core.native_host_environment['trajectories'][t]
    need(state['labels'] == labels and state['id'] == ids[0]
         and state['image'] == host['image_ids']['nginx-edge']
         and state['running'] is True and state['pid'] > 0
         and not any(state[k] for k in ('paused', 'restarting', 'dead')),
         'HOSTPUB_ACTUAL_RUNNING_PINNED_NGINX')
    birth = process_birth(state['pid'])
    registered = core.cold_bootstrap.infra_birth_records.get((t, 'nginx-edge'))
    need(registered == dict(cid=state['id'], image_id=state['image'], init_birth=birth),
         'HOSTPUB_ORIGINAL_INFRA_INIT_FULLBIRTH_REQUIRED')
    live = docker._project('inspect', '--type', 'container', '--format', PROJECTION, state['id'])
    need(set(live) == {'id', 'networks', 'ports'} and live['id'] == state['id']
         and set(live['networks']) == {net.network_name}, 'HOSTPUB_ONLY_REGISTERED_NETWORK')
    attached = live['networks'][net.network_name]
    ip = attached['IPAddress']; address = ipaddress.IPv4Address(ip)
    subnet = ipaddress.IPv4Network(net.subnet)
    need(attached['NetworkID'] == net.network_id and attached['Gateway'] == net.gateway
         and address in subnet and address not in
         (subnet.network_address, subnet.broadcast_address, ipaddress.IPv4Address(net.gateway)),
         'HOSTPUB_EXACT_NGINX_IP_GATEWAY_SUBNET')
    ports = _ports(host)
    need(live['ports'] == {str(target) + '/tcp': [{'HostIp': '0.0.0.0', 'HostPort': str(port)}]
         for target, port in zip((80, 81), ports)}, 'HOSTPUB_ONLY_TWO_ORIGINAL_HOST_PUBLISH_PORTS')
    n = docker._project('network', 'inspect', '--format', NETWORK, net.network_id)
    need(set(n) == {'id', 'name', 'driver', 'scope', 'labels', 'ipam', 'options'}
         and n['id'] == net.network_id and n['name'] == net.network_name
         and n['driver'] == 'bridge' and n['scope'] == 'local'
         and n['labels'] == {k: expected[k] for k in
             ('count14.root', 'count14.trajectory-sha256', 'count14.contract-sha256')}
         and n['ipam'] == [{'Gateway': net.gateway, 'Subnet': net.subnet}],
         'HOSTPUB_LIVE_NETWORK_SCOPE_AND_IPAM')
    bridge = (n['options'] or {}).get('com.docker.network.bridge.name', 'br-' + net.network_id[:12])
    need(type(bridge) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,15}', bridge),
         'HOSTPUB_EXACT_KERNEL_BRIDGE_NAME')
    index = int(_read('/sys/class/net/' + bridge + '/ifindex'))
    need(index > 0, 'HOSTPUB_REAL_BRIDGE_IFINDEX')
    route = json.loads(_run(['/usr/sbin/ip', '-j', 'route', 'get', ip]))
    addr = json.loads(_run(['/usr/sbin/ip', '-j', '-4', 'address', 'show', 'dev', bridge]))
    need(len(route) == len(addr) == 1 and route[0]['dev'] == bridge
         and addr[0]['ifindex'] == index and any(a.get('local') == net.gateway
             for a in addr[0]['addr_info']), 'HOSTPUB_KERNEL_ROUTE_AND_GATEWAY_ADDRESS')
    return dict(root=row['root'], trajectory=t, contract_sha256=digest(core.contract),
        cid=state['id'], image=state['image'], init_birth=asdict(birth),
        daemon_id=docker.route.daemon_id, daemon_data_root=str(docker.route.data_root),
        network_id=net.network_id, bridge=bridge, ifindex=index, ip=ip,
        gateway=net.gateway, ports=ports)


def _rule_vectors(binding):
    b = binding
    return [('POSTROUTING', ['-s', '127.0.0.1/32', '-d', b['ip'] + '/32', '-o', b['bridge'],
        '-p', 'tcp', '-m', 'tcp', '--dport', str(target), '-j', 'SNAT', '--to-source', b['gateway']])
        for target in (80, 81)] + [('OUTPUT', ['-d', '127.0.0.1/32', '-p', 'tcp', '-m', 'tcp',
        '--dport', str(port), '-j', 'DNAT', '--to-destination', b['ip'] + ':' + str(target)])
        for port, target in zip(b['ports'], (80, 81))]


def _rules(binding, raw):
    chains = {'POSTROUTING': [], 'OUTPUT': []}
    all_comments = []
    for line in raw.decode('ascii').splitlines():
        if not line.startswith('-A '):
            continue
        tokens = shlex.split(line)
        comments = [tokens[i + 1] for i, x in enumerate(tokens[:-1]) if x == '--comment']
        all_comments.extend(comments)
        if tokens[1] in chains:
            clean = list(tokens[2:]); comment = None
            if '--comment' in clean:
                i = clean.index('--comment')
                need(len(comments) == 1 and i >= 2 and clean[i-2:i] == ['-m', 'comment'],
                     'HOSTPUB_EXACT_SINGLE_COMMENT_MATCH')
                comment = clean[i+1]; del clean[i-2:i+2]
            chains[tokens[1]].append((clean, comment, tokens))
    selected = []
    for chain, vector in _rule_vectors(binding):
        matches = [(i, comment, tokens) for i, (clean, comment, tokens) in enumerate(chains[chain])
                   if clean == vector]
        need(len(matches) <= 1, 'HOSTPUB_DUPLICATE_EXACT_NAT_RULE')
        if not matches:
            return None
        i, comment, tokens = matches[0]
        need(type(comment) is str and re.fullmatch(r'ct14-[A-Za-z0-9_-]{1,200}', comment)
             and all_comments.count(comment) == 1, 'HOSTPUB_UNIQUE_REGISTERED_RULE_COMMENT')
        # Installer's approved -I ... 1 pattern places both exact rules first;
        # no preceding broad DNAT/SNAT may intercept the loopback flow.
        need(i < 2, 'HOSTPUB_EXACT_NAT_BEFORE_POSSIBLY_INTERCEPTING_RULES')
        selected.append(tokens)
    need(len({tokens[tokens.index('--comment') + 1] for tokens in selected}) == 4,
         'HOSTPUB_FOUR_DISTINCT_COMMENT_RECEIPTS')
    return selected


def _headers(binding):
    out = []
    for port, path in zip(binding['ports'], ('/api/v1/version', '/api/v4/system/ping')):
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        try:
            connection.request('GET', path, headers={
                'Connection': 'close', 'User-Agent': 'count14-registered-infra-header-only'})
            response = connection.getresponse()
            out.append(dict(port=port, path=path, status=response.status,
                response_body_not_read=True, at_mono_ns=time.monotonic_ns()))
        finally:
            connection.close()
    need(all(row['status'] == 200 for row in out), 'HOSTPUB_BOTH_ORIGINAL_HEADERS_MUST_BE200')
    return out


def _receipt(core, t, value):
    root = Path(core.rows[t]['root']); parent = root / 'metadata'
    s = parent.lstat()
    need(root.is_absolute() and root.resolve() == root and parent.resolve() == parent
         and stat.S_ISDIR(s.st_mode) and s.st_uid == os.geteuid()
         and not stat.S_IMODE(s.st_mode) & 0o022, 'HOSTPUB_ONLY_SAME_ROW_PUBLIC_METADATA')
    path = parent / ('HOST_PUBLISH_BEFORE_GITEA_' + digest(value['owner_birth']) + '_PUBLIC.json')
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw); out.flush(); os.fsync(out.fileno())
    fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())


def publication_hostpub_ready(core, t):
    need(t in core.rows and t in core.gate.startup_held
         and not core.scientific_activation_qualified, 'HOSTPUB_ONLY_UNRELEASED_ORIGINAL_SOURCE_PHASE')
    birth = asdict(process_birth(os.getpid())); now = time.monotonic_ns()
    if not hasattr(core, 'native_hostpub_prepublication'):
        core.native_hostpub_prepublication = {}
    table = core.native_hostpub_prepublication
    previous = table.get(t)
    if previous is not None:
        need(previous['owner_birth'] == birth, 'HOSTPUB_NO_OTHER_OWNER_PROOF_REUSE')
        if previous['state'] == READY:
            need(0 <= now - previous['verified_ns'] <= 15 * 10**9,
                 'HOSTPUB_ORIGINAL_HEADER_PROOF_EXPIRED_NO_RESTAMP')
            return True
        need(not previous.get('header_attempted'), 'HOSTPUB_HEADER_ATTEMPT_RETAINED_NO_AUTOMATIC_RETRY')
        if 0 <= now - previous['checked_ns'] < 2 * 10**9:
            return False
    state = dict(state=WAITING, owner_birth=birth, checked_ns=now, header_attempted=False)
    table[t] = state
    binding = _topology(core, t)
    if _read('/proc/sys/net/ipv4/conf/' + binding['bridge'] + '/route_localnet') != '1':
        state['reason'] = 'EXACT_BRIDGE_ROUTE_LOCALNET_NOT_READY'
        return False
    rules = _rules(binding, _run(['/usr/sbin/iptables-save', '-t', 'nat']))
    if rules is None:
        state['reason'] = 'EXACT_FOUR_COMMENTED_NAT_RULES_NOT_READY'
        return False
    state['header_attempted'] = True
    headers = _headers(binding)  # safe two headers, once, only after real rules
    # Full fresh identity/rules/route readback after I/O, no cached green.
    need(_topology(core, t) == binding
         and _read('/proc/sys/net/ipv4/conf/' + binding['bridge'] + '/route_localnet') == '1'
         and _rules(binding, _run(['/usr/sbin/iptables-save', '-t', 'nat'])) == rules,
         'HOSTPUB_METADATA_RULES_OR_ROUTE_CHANGED_DURING_HEADERS')
    at = time.monotonic_ns()
    need(0 <= at - now <= 15 * 10**9, 'HOSTPUB_BOUNDED_FRESH_PHYSICAL_VERIFICATION')
    value = dict(schema='count14-exact-hostpub-before-first-gitea-v1', owner_birth=birth,
        binding=binding, header_only_original_GETs=headers, exact_rules=rules,
        exact_rollback_argv=[['/usr/sbin/iptables', '--wait', '10', '-t', 'nat', '-D', *r[1:]]
            for r in reversed(rules)], observed_ns=at, no_system_or_scientific_model_probe=True,
        source_publication_has_not_started=True, NAT_or_sysctl_changes_by_this_module=0)
    ref = _receipt(core, t, value)
    state.update(state=READY, verified_ns=at, receipt=ref)
    return True
