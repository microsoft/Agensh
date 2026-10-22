#!/usr/bin/env python3
# Bridge one Unix-socket ACP connection at a time to a non-root Copilot process.
# Disconnects cancel active prompts; shutdown saves the worker's HOME and /work.

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time

from archive import begin, save

if len(sys.argv) < 6 or sys.argv[4] != '--':
    sys.exit('usage: acp-bridge.py <socket> <uid> <gid> -- <child-command...>')
sock_path = sys.argv[1]
sock_uid, sock_gid = int(sys.argv[2]), int(sys.argv[3])
child_cmd = sys.argv[5:]
child_uid, child_gid = int(os.environ['ACP_CHILD_UID']), int(os.environ['ACP_CHILD_GID'])
if child_uid == 0:
    sys.exit('ACP child must run as a non-root user')
state_root = Path(os.environ.get('AGENT_HOME', '/opt/data')).absolute()
archive = begin(state_root)
stopping = threading.Event()
connections = set()
connection_lock = threading.Lock()

try:
    os.unlink(sock_path)
except FileNotFoundError:
    pass
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(sock_path)
os.chmod(sock_path, 0o660)
os.chown(sock_path, sock_uid, sock_gid)
server.listen(8)
print(f'[acp-bridge] listening at {sock_path}', file=sys.stderr, flush=True)


def stop_processes(proc):
    # Reap the child's process group, or any remaining worker-UID processes at exit.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if proc is not None:
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                pass
        else:
            for path in Path('/proc').glob('[0-9]*/status'):
                try:
                    uid = next(line.split()[1] for line in path.read_text().splitlines() if line.startswith('Uid:'))
                    if int(uid) == child_uid:
                        os.kill(int(path.parent.name), sig)
                except (FileNotFoundError, ProcessLookupError):
                    pass
        if sig == signal.SIGTERM and proc is not None:
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        elif sig == signal.SIGTERM:
            time.sleep(0.25)
    if proc is not None:
        proc.wait(timeout=5)


def serve(client, peer):
    proc = None
    try:
        for attempt in range(1, 4):
            if stopping.is_set():
                return
            try:
                proc = subprocess.Popen(child_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=sys.stderr, bufsize=0, close_fds=True, user=child_uid, group=child_gid,
                    start_new_session=True)
                break
            except OSError as error:
                print(f'[acp-bridge] conn {peer} spawn attempt {attempt}/3: {type(error).__name__}', file=sys.stderr, flush=True)
                if attempt < 3:
                    stopping.wait(2 * attempt)
        if proc is None:
            return
        pending = {}
        condition = threading.Condition()
        writer = threading.Lock()
        disconnected = threading.Event()

        def sock_to_child():
            try:
                with client.makefile('rb') as stream:
                    for line in stream:
                        try:
                            message = json.loads(line)
                            if message.get('method') == 'session/prompt':
                                with condition:
                                    pending[message['id']] = message['params']['sessionId']
                        except (ValueError, KeyError, TypeError):
                            pass
                        with writer:
                            proc.stdin.write(line)
                            proc.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            finally:
                disconnected.set()

        def child_to_sock():
            forwarding = True
            try:
                for line in iter(proc.stdout.readline, b''):
                    try:
                        message = json.loads(line)
                        if 'id' in message and 'method' not in message:
                            with condition:
                                pending.pop(message['id'], None)
                                condition.notify_all()
                    except (ValueError, KeyError, TypeError):
                        pass
                    if forwarding:
                        try:
                            client.sendall(line)
                        except OSError:
                            forwarding = False
                            disconnected.set()
            except (BrokenPipeError, OSError):
                pass
            finally:
                disconnected.set()

        to_child = threading.Thread(target=sock_to_child, daemon=True)
        to_client = threading.Thread(target=child_to_sock, daemon=True)
        to_child.start()
        to_client.start()
        while proc.poll() is None and not stopping.is_set() and not disconnected.wait(0.1):
            pass
        if proc.poll() is None:
            with condition:
                sessions = set(pending.values())
            if sessions:
                # Let Copilot settle native cancellation before terminating its tools.
                try:
                    with writer:
                        for session in sessions:
                            proc.stdin.write((json.dumps({'jsonrpc':'2.0', 'method':'session/cancel',
                                'params':{'sessionId':session}}) + '\n').encode())
                        proc.stdin.flush()
                    with condition:
                        settled = condition.wait_for(lambda: not pending, timeout=8)
                    print(f'[acp-bridge] conn {peer} native cancellation settled={settled}', file=sys.stderr, flush=True)
                except (BrokenPipeError, OSError):
                    pass
            with writer:
                proc.stdin.close()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        stop_processes(proc)
        try:
            client.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        to_child.join(timeout=2)
        to_client.join(timeout=2)
        print(f'[acp-bridge] conn {peer} child exited rc={proc.returncode}', file=sys.stderr, flush=True)
    finally:
        if proc is not None and proc.poll() is None:
            stop_processes(proc)
        client.close()
        with connection_lock:
            connections.discard(threading.current_thread())


def shutdown(*_):
    stopping.set()


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)
server.settimeout(0.5)
peer = 0
try:
    while not stopping.is_set():
        try:
            client, _ = server.accept()
        except socket.timeout:
            continue
        peer += 1
        thread = threading.Thread(target=serve, args=(client, peer), daemon=True)
        with connection_lock:
            connections.add(thread)
        thread.start()
        # A replacement connection must wait for the previous child's cleanup.
        while thread.is_alive() and not stopping.is_set():
            thread.join(timeout=0.1)
finally:
    stopping.set()
    server.close()
    # Limit connection joins to nine minutes, leaving time for the shutdown archive.
    deadline = time.monotonic() + 540
    with connection_lock:
        threads = list(connections)
    for thread in threads:
        thread.join(timeout=max(0, deadline - time.monotonic()))
    try:
        if any(thread.is_alive() for thread in threads):
            raise RuntimeError('ACP shutdown did not finish before the archive deadline')
        stop_processes(None)
        save(archive, state_root / 'home', Path('/work'))
        print('[acp-bridge] final HOME/workspace archive complete', file=sys.stderr, flush=True)
    finally:
        try:
            os.unlink(sock_path)
        except FileNotFoundError:
            pass
