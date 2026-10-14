#!/usr/bin/env bash
# Opt-in private TCP relay. Does not alter the existing proxy or its credentials.
# up STATE_DIR --context CONTEXT --namespace NS --profile PROFILE --node NODE
#              --image IMAGE --name NAME --target HOST:PORT [--max-attempts N]
# serve STATE_DIR  (foreground; suitable for explicit Bash backgrounding)
# status STATE_DIR | stop STATE_DIR
# The profile must point PBENCH_LLM_UPSTREAM at NAME:18080 before rendering.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 - "$ROOT" "$@" <<'PY'
import argparse
import base64
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import select
import signal
import socket
import stat
import subprocess
import sys
import time
import uuid

ROOT = Path(sys.argv[1])
PREFIX = 'omcgitea-gateway-relay-'
KINDS = {
    'Pod': ('/api/v1', 'pods'),
    'Service': ('/api/v1', 'services'),
    'Secret': ('/api/v1', 'secrets'),
    'ConfigMap': ('/api/v1', 'configmaps'),
    'NetworkPolicy': ('/apis/networking.k8s.io/v1', 'networkpolicies'),
}
CREATE_RECONCILE_GRACE_S = 60
BOOT_ID = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
os.umask(0o077)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('mode', choices=['up', 'serve', 'status', 'stop'])
parser.add_argument('state_dir', help='fresh absolute directory below this repository out/')
parser.add_argument('--context')
parser.add_argument('--namespace')
parser.add_argument('--profile')
parser.add_argument('--node')
parser.add_argument('--image')
parser.add_argument('--name')
parser.add_argument('--target')
parser.add_argument('--max-attempts', type=int, default=20)
args = parser.parse_args(sys.argv[2:])
D = Path(args.state_dir)
if not D.is_absolute() or D.resolve() != D or ROOT / 'out' not in D.parents:
    parser.error('state directory must be an absolute, non-symlink path below repository out/')
for parent in (D, *D.parents):
    if parent.is_symlink():
        parser.error('state path must not contain symlinks')

option_names = ('context', 'namespace', 'profile', 'node', 'image', 'name', 'target')
if args.mode == 'up':
    missing = [name for name in option_names if not getattr(args, name)]
    if missing:
        parser.error('up requires --' + ', --'.join(missing))
    CTX, NS, PROFILE = args.context, args.namespace, args.profile
    NODE, IMAGE, NAME = args.node, args.image, args.name
    NS_UID = None
else:
    if any(getattr(args, name) is not None for name in option_names) or args.max_attempts != 20:
        parser.error('configuration options are valid only with up')
    try:
        initial = json.loads((D / 'state.json').read_text())
        CTX, NS, PROFILE = initial['context'], initial['namespace'], initial['profile']
        NODE, IMAGE, NAME = initial['node'], initial['image'], initial['name']
        NS_UID = initial['namespace_uid']
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        parser.error('cannot read relay state: ' + str(exc))

if not re.fullmatch(r'[a-z0-9](?:[-a-z0-9]*[a-z0-9])?', NS or '') or len(NS) > 63:
    parser.error('namespace must be a Kubernetes DNS label')
if (not re.fullmatch(r'omcgitea-gateway-relay-[a-z0-9](?:[-a-z0-9]*[a-z0-9])?', NAME or '')
        or len(NAME) > 63):
    parser.error('name must be an omcgitea-gateway-relay-* Kubernetes DNS label')
if (not re.fullmatch(r'[A-Za-z0-9](?:[-A-Za-z0-9_.]*[A-Za-z0-9])?', PROFILE or '')
        or len(PROFILE) > 63):
    parser.error('profile must be a Kubernetes label value')
if not CTX or any(character.isspace() for character in CTX + NODE + IMAGE):
    parser.error('context, node, and image must be non-empty single tokens')


def write(name, value):
    destination = D / name
    temporary = D / (name + '.tmp-' + str(os.getpid()))
    with temporary.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, destination)


def run(argv, *, data=None, check=True, timeout=40):
    process = subprocess.run(argv, input=data, capture_output=True, text=True, timeout=timeout)
    if check and process.returncode:
        # Never print stdin: Secret creation can carry a host private key.
        raise RuntimeError(f'{argv[0]} failed ({process.returncode}): {process.stderr[-1500:]}')
    return process


def k(*argv, **kwargs):
    return run(['kubectl', '--context', CTX, '--request-timeout=20s', '-n', NS, *argv], **kwargs)


def scope():
    obj = json.loads(k('get', 'namespace', NS, '-o', 'json').stdout)
    metadata = obj['metadata']
    if metadata['uid'] != NS_UID or metadata.get('labels', {}).get('pbench-profile') != PROFILE:
        raise RuntimeError('namespace UID/profile changed; refusing cluster mutation')


def private_directory():
    info = D.stat()
    if not D.is_dir() or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError('state must be an owned private directory (0700)')


def open_lock(name):
    private_directory()
    descriptor = os.open(D / name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    info = os.fstat(descriptor)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600):
        os.close(descriptor)
        raise RuntimeError('unsafe lifecycle lock')
    return os.fdopen(descriptor, 'a')


@contextmanager
def lifecycle(cancel=None):
    with open_lock('lifecycle.lock') as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if cancel and cancel():
                    raise InterruptedError('supervisor stopped while waiting for lifecycle lock')
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def private_state():
    private_directory()
    for path in D.iterdir():
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600):
            raise RuntimeError('state contains an unsafe file: ' + path.name)


def load():
    private_state()
    state = json.loads((D / 'state.json').read_text())
    actual = (
        state.get('context'),
        state.get('namespace'),
        state.get('namespace_uid'),
        state.get('profile'),
        state.get('node'),
        state.get('image'),
        state.get('name'),
    )
    expected = (CTX, NS, NS_UID, PROFILE, NODE, IMAGE, NAME)
    if actual != expected:
        raise RuntimeError('state scope mismatch')
    if (not re.fullmatch(r'omcgitea-gateway-relay-[a-z0-9](?:[-a-z0-9]*[a-z0-9])?', state['name'])
            or len(state['name']) > 63):
        raise RuntimeError('invalid resource name in state')
    if not re.fullmatch(r'[0-9a-f]{32}', state['run']):
        raise RuntimeError('invalid owner in state')
    for record in state['resources'] + state.get('creation_intents', []):
        if record['kind'] not in KINDS or record['name'] != state['name']:
            raise RuntimeError('invalid resource record')
    return state


def selected(selector, labels):
    if any(labels.get(key) != value for key, value in selector.get('matchLabels', {}).items()):
        return False
    for expression in selector.get('matchExpressions', []):
        key = expression['key']
        operator = expression['operator']
        values = expression.get('values', [])
        if operator == 'In' and labels.get(key) not in values:
            return False
        if operator == 'NotIn' and key in labels and labels[key] in values:
            return False
        if operator == 'Exists' and key not in labels:
            return False
        if operator == 'DoesNotExist' and key in labels:
            return False
    return True


def check_ingress(state):
    # NetworkPolicy allows are additive. Reject any preexisting ingress allow
    # selecting the relay rather than pretending this relay's policy overrides it.
    policies = json.loads(k('get', 'networkpolicy', '-o', 'json').stdout)['items']
    for policy in policies:
        if policy['metadata']['name'] == state['name']:
            continue
        spec = policy['spec']
        if selected(spec['podSelector'], state['labels']) and spec.get('ingress'):
            raise RuntimeError('another ingress policy selects relay: ' + policy['metadata']['name'])


def owned(state, record):
    result = k('get', record['kind'], record['name'], '--ignore-not-found', '-o', 'json')
    if not result.stdout.strip():
        return None
    obj = json.loads(result.stdout)
    metadata = obj['metadata']
    if (metadata['uid'] != record['uid']
            or metadata.get('labels', {}).get('pbench-relay-run') != state['run']):
        raise RuntimeError('resource ownership changed; refusing '
                           + record['kind'] + '/' + record['name'])
    return obj


def validate_provisioned(state):
    if state.get('creation_intents'):
        raise RuntimeError('relay still has unresolved create intents')
    if (len(state['resources']) != len(KINDS)
            or {record['kind'] for record in state['resources']} != set(KINDS)):
        raise RuntimeError('relay resource inventory is incomplete or duplicated')
    scope()
    objects = {}
    for record in state['resources']:
        obj = owned(state, record)
        if obj is None:
            raise RuntimeError('recorded relay resource disappeared: ' + record['kind'])
        objects[record['kind']] = obj

    service = objects['Service']['spec']
    if (service.get('type') != 'ClusterIP' or service.get('clusterIP') == 'None'
            or service.get('externalIPs')
            or service.get('selector') != {'pbench-relay-run': state['run']}
            or service.get('ports') != [{
                'name': 'gateway',
                'port': 18080,
                'protocol': 'TCP',
                'targetPort': 18080,
            }]):
        raise RuntimeError('relay Service is no longer the private recorded route')

    policy = objects['NetworkPolicy']['spec']
    expected_ingress = [{
        'from': [{'podSelector': {'matchLabels': {'app': 'egress-proxy'}}}],
        'ports': [{'port': 18080, 'protocol': 'TCP'}],
    }]
    if (policy.get('podSelector') != {'matchLabels': {'pbench-relay-run': state['run']}}
            or policy.get('policyTypes') != ['Ingress']
            or policy.get('ingress') != expected_ingress):
        raise RuntimeError('relay ingress policy was removed or widened')

    pod = objects['Pod']['spec']
    containers = pod.get('containers') or []
    if (pod.get('nodeName') != NODE
            or pod.get('automountServiceAccountToken') is not False
            or pod.get('hostNetwork') is True
            or any('hostPath' in volume for volume in pod.get('volumes', []))
            or len(containers) != 1
            or containers[0].get('name') != 'sshd'
            or containers[0].get('image') != IMAGE):
        raise RuntimeError('relay Pod escaped its recorded placement or isolation')
    check_ingress(state)
    return objects


def reconcile_creates(state):
    for intent in list(state.get('creation_intents', [])):
        while True:
            scope()
            result = k('get', intent['kind'], intent['name'], '--ignore-not-found', '-o', 'json')
            if result.stdout.strip():
                metadata = json.loads(result.stdout)['metadata']
                if (metadata['name'] != state['name'] or metadata['namespace'] != NS
                        or metadata.get('labels', {}).get('pbench-relay-run') != state['run']
                        or metadata.get('labels', {}).get('pbench-profile') != PROFILE):
                    raise RuntimeError('create intent ownership changed; refusing adoption')
                previous = next((record for record in state['resources']
                                 if record['kind'] == intent['kind']), None)
                if previous and previous['uid'] != metadata['uid']:
                    raise RuntimeError('create intent UID changed; refusing adoption')
                if previous is None:
                    state['resources'].append({
                        key: value for key, value in intent.items() if key != 'created_at'
                    } | {'uid': metadata['uid']})
                state['creation_intents'].remove(intent)
                write('state.json', state)
                break

            # A missing read immediately after a timed-out create is not proof the
            # apiserver will never commit it. Poll beyond both request timeouts.
            created_at = intent.get('created_at')
            if isinstance(created_at, (int, float)):
                remaining = created_at + CREATE_RECONCILE_GRACE_S - time.time()
                if remaining <= 0:
                    state['creation_intents'].remove(intent)
                    write('state.json', state)
                    break
                time.sleep(min(1.0, remaining))
                continue
            raise RuntimeError('unresolved create intent lacks reconciliation time: ' + intent['kind'])


def create(state, kind, body):
    scope()
    if k('get', kind, state['name'], '--ignore-not-found', '-o', 'name').stdout.strip():
        raise RuntimeError('refusing preexisting resource: ' + kind + '/' + state['name'])
    obj = {
        'apiVersion': 'networking.k8s.io/v1' if kind == 'NetworkPolicy' else 'v1',
        'kind': kind,
        'metadata': {
            'name': state['name'],
            'namespace': NS,
            'labels': state['labels'],
        },
        **body,
    }
    intent = {'kind': kind, 'name': state['name'], 'created_at': time.time()}
    state.setdefault('creation_intents', []).append(intent)
    write('state.json', state)
    # Create, never apply. The persisted intent covers a killed client or a
    # timeout after API acceptance; cleanup resolves only this fresh name/owner.
    result = k('create', '-f', '-', '-o', 'json', data=json.dumps(obj), check=False)
    if result.returncode:
        invalid = f'The {kind} "{state["name"]}" is invalid:'
        rejected = any(
            line.startswith(invalid)
            or re.match(r'^Error from server \((?:Invalid|BadRequest|Forbidden|Unauthorized)\):', line)
            for line in result.stderr.splitlines()
        )
        if rejected:
            state['creation_intents'].remove(intent)
            write('state.json', state)
        raise RuntimeError(f'kubectl create failed ({result.returncode}): {result.stderr[-1500:]}')
    got = json.loads(result.stdout)
    state['resources'].append({
        'kind': kind,
        'name': state['name'],
        'uid': got['metadata']['uid'],
    })
    state['creation_intents'].remove(intent)
    write('state.json', state)


def cleanup_resources(state):
    # Preflight every identity before deleting even one resource.
    scope()
    reconcile_creates(state)
    for record in state['resources']:
        owned(state, record)
    for record in reversed(state['resources']):
        scope()
        if owned(state, record) is None:
            continue
        api, plural = KINDS[record['kind']]
        write('delete.json', {
            'apiVersion': 'v1',
            'kind': 'DeleteOptions',
            'preconditions': {'uid': record['uid']},
            'gracePeriodSeconds': 0,
        })
        k('delete', '--raw', f'{api}/namespaces/{NS}/{plural}/{record["name"]}',
          '-f', str(D / 'delete.json'))
    state['stopped'] = True
    write('state.json', state)


def process(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        if fields[0] == 'Z':
            return None
        return {'pid': pid, 'start': fields[19], 'boot_id': BOOT_ID}
    except (FileNotFoundError, ProcessLookupError):
        return None


def alive(record):
    return bool(record) and process(record['pid']) == record


def kill_record(record):
    if not alive(record):
        return
    # Pin the kernel process before rechecking its recorded start time. A PID
    # exiting/reusing between inspection and signalling must never hit a peer.
    try:
        descriptor = os.pidfd_open(record['pid'])
    except ProcessLookupError:
        return
    try:
        if not alive(record):
            return
        poller = select.poll()
        poller.register(descriptor, select.POLLIN)
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                signal.pidfd_send_signal(descriptor, sig)
            except ProcessLookupError:
                return
            if poller.poll(5000):
                return
        raise RuntimeError('owned process did not stop; retaining its identity')
    finally:
        os.close(descriptor)


def runtime():
    try:
        return json.loads((D / 'runtime.json').read_text())
    except FileNotFoundError:
        return {}


def up():
    global NS_UID
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*:[0-9]{1,5}', args.target):
        raise RuntimeError('target must be a fixed HOST:PORT, not a URL or forwarding expression')
    host, port = args.target.rsplit(':', 1)
    if not 1 <= int(port) <= 65535 or not 1 <= args.max_attempts <= 100:
        raise RuntimeError('invalid port or retry budget (1..100)')
    namespace = json.loads(k('get', 'namespace', NS, '-o', 'json').stdout)
    if namespace['metadata'].get('labels', {}).get('pbench-profile') != PROFILE:
        raise RuntimeError('namespace profile label does not match the requested profile')
    NS_UID = namespace['metadata']['uid']
    scope()
    # The parent must exist. Even an empty preexisting state directory is refused.
    D.mkdir(mode=0o700)
    with lifecycle():
        provision(host, int(port))


def provision(host, port):
    run_id = uuid.uuid4().hex
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        local_port = sock.getsockname()[1]
    state = {
        'version': 1,
        'context': CTX,
        'namespace': NS,
        'namespace_uid': NS_UID,
        'profile': PROFILE,
        'node': NODE,
        'image': IMAGE,
        'name': NAME,
        'run': run_id,
        'local_port': local_port,
        'target_host': host,
        'target_port': port,
        'max_attempts': args.max_attempts,
        'endpoint': f'http://{NAME}.{NS}.svc.cluster.local:18080',
        'resources': [],
        'labels': {
            'app': 'pbench-gateway-relay',
            'pbench-relay-run': run_id,
            'pbench-profile': PROFILE,
        },
    }
    write('state.json', state)
    try:
        check_ingress(state)
        for key in ('client', 'host'):
            run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(D / key)])
            (D / (key + '.pub')).chmod(0o600)
        host_key = ' '.join((D / 'host.pub').read_text().split()[:2])
        (D / 'known_hosts').write_text(NAME + ' ' + host_key + '\n')

        config = '''Port 2222
ListenAddress 127.0.0.1
HostKey /host-key/key
PidFile /run/sshd.pid
AuthorizedKeysFile /run/relay/authorized_keys
StrictModes yes
PubkeyAuthentication yes
AuthenticationMethods publickey
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
PermitRootLogin no
AllowUsers relay
AllowTcpForwarding remote
PermitListen 0.0.0.0:18080
GatewayPorts clientspecified
MaxSessions 0
PermitTTY no
AllowAgentForwarding no
X11Forwarding no
AllowStreamLocalForwarding no
PermitTunnel no
ClientAliveInterval 5
ClientAliveCountMax 2
LogLevel VERBOSE
'''
        startup = '''adduser -D -H -h /run/relay -s /bin/sh relay
mkdir -p /run/relay
chmod 0755 /run/relay
cp /relay-config/authorized_keys /run/relay/authorized_keys
chmod 0644 /run/relay/authorized_keys
# Unlock only this new account with a random unavailable password. sshd forbids
# password/interactive login; a locked shadow account would also reject its key.
password="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \\n')"
printf 'relay:%s\\n' "$password" | chpasswd
unset password
mkdir -p /run/sshd
exec /usr/sbin/sshd -D -e -f /relay-config/sshd_config
'''
        create(state, 'Secret', {
            'type': 'Opaque',
            'data': {'key': base64.b64encode((D / 'host').read_bytes()).decode()},
        })
        create(state, 'ConfigMap', {
            'data': {
                'sshd_config': config,
                'authorized_keys': (
                    'restrict,port-forwarding,permitlisten="0.0.0.0:18080" '
                    + (D / 'client.pub').read_text()
                ),
            },
        })
        create(state, 'NetworkPolicy', {
            'spec': {
                'podSelector': {'matchLabels': {'pbench-relay-run': run_id}},
                'policyTypes': ['Ingress'],
                'ingress': [{
                    'from': [{'podSelector': {'matchLabels': {'app': 'egress-proxy'}}}],
                    'ports': [{'protocol': 'TCP', 'port': 18080}],
                }],
            },
        })
        create(state, 'Service', {
            'spec': {
                'type': 'ClusterIP',
                'selector': {'pbench-relay-run': run_id},
                'ports': [{'name': 'gateway', 'port': 18080, 'targetPort': 18080}],
            },
        })
        create(state, 'Pod', {
            'spec': {
                'nodeName': NODE,
                'automountServiceAccountToken': False,
                'restartPolicy': 'Always',
                'terminationGracePeriodSeconds': 3,
                'containers': [{
                    'name': 'sshd',
                    'image': IMAGE,
                    'imagePullPolicy': 'IfNotPresent',
                    'command': ['/bin/sh', '-ec', startup],
                    'resources': {
                        'requests': {'cpu': '10m', 'memory': '32Mi'},
                        'limits': {'cpu': '250m', 'memory': '128Mi'},
                    },
                    'securityContext': {
                        'runAsUser': 0,
                        'runAsGroup': 0,
                        'allowPrivilegeEscalation': False,
                        'capabilities': {
                            'drop': ['ALL'],
                            'add': [
                                'CHOWN', 'DAC_OVERRIDE', 'SETUID', 'SETGID',
                                'SYS_CHROOT', 'KILL',
                            ],
                        },
                    },
                    'volumeMounts': [
                        {'name': 'host-key', 'mountPath': '/host-key', 'readOnly': True},
                        {'name': 'config', 'mountPath': '/relay-config', 'readOnly': True},
                    ],
                }],
                'volumes': [
                    {'name': 'host-key', 'secret': {'secretName': NAME, 'defaultMode': 0o400}},
                    {'name': 'config', 'configMap': {'name': NAME, 'defaultMode': 0o444}},
                ],
            },
        })
        k('wait', '--for=condition=Ready', 'pod/' + NAME, '--timeout=90s', timeout=115)
        # Pod Ready alone is not transport readiness; serve performs HTTP validation.
        print(json.dumps({
            'state_dir': str(D),
            'endpoint': state['endpoint'],
            'status': 'provisioned-not-connected',
        }))
    except BaseException:
        cleanup_resources(state)
        raise


def serve():
    serve_lock = open_lock('serve.lock')
    try:
        fcntl.flock(serve_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('relay already has a supervisor')
    active = []
    stopping = False
    with lifecycle():
        state = load()
        if state.get('stopped') or state.get('stop_requested'):
            raise RuntimeError('relay was stopped; create a fresh state instead')
        validate_provisioned(state)
        previous = runtime()
        if alive(previous.get('supervisor')):
            raise RuntimeError('recorded supervisor is still alive; refusing ownership replacement')
        for role in ('ssh', 'pf'):
            kill_record(previous.get(role))
        generation = uuid.uuid4().hex
        rt = {
            'supervisor': process(os.getpid()),
            'generation': generation,
            'ready': False,
            'attempt': 0,
            'pf': None,
            'ssh': None,
        }
        write('runtime.json', rt)

    def stop_signal(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop_signal)
    signal.signal(signal.SIGINT, stop_signal)

    def publish():
        write('runtime.json', rt)

    def reap():
        # Kill and wait only exact Popen children of this supervisor.
        for child in reversed(active):
            if child.poll() is None:
                child.terminate()
        for child in reversed(active):
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        active.clear()
        rt.update(ready=False, pf=None, ssh=None)
        publish()

    def connect(attempt):
        # Stop and child creation cannot overlap. Healthy forwarding does not hold
        # this lifecycle transition lock.
        with lifecycle(cancel=lambda: stopping):
            current = load()
            if stopping or current.get('stop_requested') or current.get('stopped'):
                raise InterruptedError('stop fence prevents tunnel creation')
            validate_provisioned(current)
            rt.update(attempt=attempt, ready=False, error=None)
            publish()
            with (D / 'supervisor.log').open('a') as audit:
                audit.write(
                    f'{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} '
                    f'generation {generation} attempt {attempt}\n'
                )

            # Never stop a listener occupying the old local port. Re-select and
            # persist; a later bind race becomes a bounded reconnect attempt.
            with socket.socket() as sock:
                try:
                    sock.bind(('127.0.0.1', current['local_port']))
                except OSError:
                    sock.bind(('127.0.0.1', 0))
                state['local_port'] = current['local_port'] = sock.getsockname()[1]
            write('state.json', current)

            port_forward_log = D / f'port-forward-{generation}-{attempt}.log'
            with port_forward_log.open('x') as output:
                port_forward = subprocess.Popen([
                    'kubectl', '--context', CTX, '--request-timeout=20s', '-n', NS,
                    'port-forward', '--address=127.0.0.1', 'pod/' + state['name'],
                    f'{state["local_port"]}:2222',
                ], stdout=output, stderr=output)
            active.append(port_forward)
            rt.update(pf=process(port_forward.pid), pf_log=str(port_forward_log))
            publish()
            deadline = time.monotonic() + 20
            while not stopping and time.monotonic() < deadline:
                if port_forward.poll() is not None:
                    raise RuntimeError(f'port-forward exited {port_forward.returncode}')
                if (f'Forwarding from 127.0.0.1:{state["local_port"]} -> 2222'
                        in port_forward_log.read_text()):
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError('port-forward readiness timeout or stop')

            ssh_log = D / f'ssh-{generation}-{attempt}.log'
            ssh_log.touch(mode=0o600, exist_ok=False)
            ssh = subprocess.Popen([
                'ssh', '-F', '/dev/null', '-v', '-E', str(ssh_log), '-N', '-T',
                '-o', 'BatchMode=yes',
                '-o', 'IdentitiesOnly=yes',
                '-o', 'IdentityAgent=none',
                '-o', 'ControlMaster=no',
                '-o', 'StrictHostKeyChecking=yes',
                '-o', 'UserKnownHostsFile=' + str(D / 'known_hosts'),
                '-o', 'GlobalKnownHostsFile=/dev/null',
                '-o', 'HostKeyAlias=' + state['name'],
                '-o', 'ConnectTimeout=5',
                '-o', 'ExitOnForwardFailure=yes',
                '-o', 'ServerAliveInterval=5',
                '-o', 'ServerAliveCountMax=2',
                '-i', str(D / 'client'),
                '-p', str(state['local_port']),
                '-R', f'0.0.0.0:18080:{state["target_host"]}:{state["target_port"]}',
                'relay@127.0.0.1',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            active.append(ssh)
            rt.update(ssh=process(ssh.pid), ssh_log=str(ssh_log))
            publish()
            deadline = time.monotonic() + 20
            while not stopping and time.monotonic() < deadline:
                if ssh.poll() is not None or port_forward.poll() is not None:
                    raise RuntimeError(
                        f'tunnel child exited pf={port_forward.poll()} ssh={ssh.poll()}'
                    )
                if 'remote forward success for:' in ssh_log.read_text():
                    # Listener allocation alone never connects to the local target.
                    # Require one body-discarding HTTP response through the reverse path.
                    probe = k(
                        'exec', state['name'], '--',
                        'curl', '--silent', '--show-error', '--output', '/dev/null',
                        '--write-out', '%{http_code}', '--max-time', '15',
                        'http://127.0.0.1:18080/v1/responses',
                        check=False,
                        timeout=25,
                    )
                    if (probe.returncode
                            or not re.fullmatch(r'[1-5][0-9][0-9]', probe.stdout.strip())):
                        raise RuntimeError('reverse listener cannot reach its configured HTTP target')
                    rt['ready'] = True
                    publish()
                    return port_forward, ssh
                time.sleep(0.2)
            raise RuntimeError('SSH remote listener readiness timeout or stop')

    try:
        for attempt in range(1, state['max_attempts'] + 1):
            if stopping:
                return 0
            try:
                port_forward, ssh = connect(attempt)
                while (not stopping and port_forward.poll() is None
                       and ssh.poll() is None):
                    time.sleep(0.2)
                if not stopping:
                    raise RuntimeError(
                        f'tunnel lost pf={port_forward.poll()} ssh={ssh.poll()}'
                    )
            except Exception as exc:
                rt['error'] = str(exc)
                with (D / 'supervisor.log').open('a') as audit:
                    audit.write(str(exc) + '\n')
            finally:
                reap()
            if stopping:
                return 0
            for _ in range(20):
                if stopping:
                    return 0
                time.sleep(0.1)
        rt['error'] = 'retry budget exhausted; failed closed'
        publish()
        return 1
    finally:
        reap()
        serve_lock.close()


def stop(state):
    # The caller holds lifecycle.lock: preflight, stop fencing, process shutdown,
    # and exact resource cleanup form one transition.
    scope()
    reconcile_creates(state)
    for record in state['resources']:
        owned(state, record)
    state['stop_requested'] = True
    write('state.json', state)
    rt = runtime()
    kill_record(rt.get('supervisor'))
    # If the supervisor died abruptly, its exact recorded children remain ours.
    for role in ('ssh', 'pf'):
        kill_record(rt.get(role))
    cleanup_resources(state)
    print(json.dumps({
        'status': 'stopped',
        'state_dir': str(D),
        'endpoint': state['endpoint'],
    }))


try:
    if args.mode == 'up':
        up()
    elif args.mode == 'serve':
        sys.exit(serve())
    elif args.mode == 'stop':
        with lifecycle():
            stop(load())
    else:
        with lifecycle():
            state = load()
            if not state.get('stopped') and not state.get('stop_requested'):
                reconcile_creates(state)
                validate_provisioned(state)
            rt = runtime()
            ready = (
                not state.get('stopped')
                and not state.get('stop_requested')
                and rt.get('ready', False)
                and all(alive(rt.get(role)) for role in ('supervisor', 'pf', 'ssh'))
            )
            print(json.dumps({
                'ready': bool(ready),
                'endpoint': state['endpoint'],
                'state_dir': str(D),
                'attempt': rt.get('attempt', 0),
                'error': rt.get('error'),
            }))
            sys.exit(0 if ready else 1)
except Exception as exc:
    print('gateway relay: ' + str(exc), file=sys.stderr)
    sys.exit(1)
PY
