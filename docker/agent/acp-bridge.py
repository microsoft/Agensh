#!/usr/bin/env python3
"""
acp-bridge — replaces `socat ... EXEC:python -m acp_adapter.entry`.

Why custom bridge instead of socat:
  socat EXEC binds child stdin/stdout to a single bidirectional unix socket.
  ACP JSON-RPC over a single socket fd has subtle SDK-side issues
  (newSession response gets lost between the initialize-response and the
  trailing session/update notification).

  This bridge accepts a single client connection over a unix socket, but
  internally spawns the child with separate stdin/stdout pipes, then
  forwards bytes:
    client→socket  →  child stdin
    child stdout   →  client→socket
  Child stderr → bridge stderr (visible in docker logs).

  This is exactly what `docker exec -i` provides (stdin/stdout/stderr as
  three independent pipes), avoiding the single-fd pitfall while
  preserving the unix-socket-per-agent isolation.

Usage:
  acp-bridge.py <socket-path> <socket-uid> <socket-gid> -- <child-cmd...>
"""
import os, sys, socket, subprocess, threading, signal, time

def usage():
    sys.stderr.write("usage: acp-bridge.py <sock-path> <uid> <gid> -- <child-cmd...>\n")
    sys.exit(2)

if "--" not in sys.argv:
    usage()
sep = sys.argv.index("--")
if sep != 4:
    usage()
sock_path = sys.argv[1]
sock_uid = int(sys.argv[2])
sock_gid = int(sys.argv[3])
child_cmd = sys.argv[sep+1:]
if not child_cmd:
    usage()

# Cleanup stale socket
try: os.unlink(sock_path)
except FileNotFoundError: pass

server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(sock_path)
os.chmod(sock_path, 0o660)
try:
    os.chown(sock_path, sock_uid, sock_gid)
except PermissionError:
    pass
server.listen(8)
sys.stderr.write(f"[acp-bridge] listening at {sock_path} (mode 0660 {sock_uid}:{sock_gid})\n")
sys.stderr.flush()

# --- Optional child privilege drop (pbench bin anti-reverse; opt-in only) --------
# ProgramBench requires the agent to be able to *run* the reference binary
# but not *read* its bytes. That is enforced by mounting the bin root:root
# mode 0111 and running the agent (the spawned ACP child) as a non-root
# user, which the kernel then denies read access to.
#
# This is GATED behind ACP_CHILD_UID / ACP_CHILD_GID env vars. When unset
# (dev / prod — the default), the child inherits the current uid (root,
# current behavior) — ZERO change. Only the pbench compose injects these,
# so dev/prod are untouched.
#
# Implementation note: Popen(user=, group=) does NOT clear the root
# supplementary group (child ends up groups=<gid>,0). That is harmless for the 0111 read-protection (mode 0111
# has no read bit for owner/group/other), so we do not need extra_groups=[].
# We keep the current uid's groups to avoid surprising the agent's normal
# tooling.
_child_uid_env = os.environ.get("ACP_CHILD_UID", "").strip()
_child_gid_env = os.environ.get("ACP_CHILD_GID", "").strip()
_child_popen_kwargs = {}
if _child_uid_env:
    _drop_uid = int(_child_uid_env)
    # Default the gid to the uid when only ACP_CHILD_UID is given.
    _drop_gid = int(_child_gid_env) if _child_gid_env else _drop_uid
    _child_popen_kwargs["user"] = _drop_uid
    _child_popen_kwargs["group"] = _drop_gid
    sys.stderr.write(
        f"[acp-bridge] child privilege drop ENABLED: spawning children as "
        f"uid={_drop_uid} gid={_drop_gid}\n"
    )
    sys.stderr.flush()

def _child_env():
    # When dropping privileges, point HOME at the drop-user's writable state
    # dir so claude-agent-acp's ~/.claude/* lands somewhere it can write.
    # entrypoint.sh already exports HOME=$AGENT_HOME/home (chowned to the
    # drop user), so inheriting the current env's HOME is correct; we copy
    # it explicitly to make the intent clear and to allow None (no override
    # in the default root path).
    if not _child_popen_kwargs:
        return None
    env = os.environ.copy()
    return env

def serve(client_sock, peer_id):
    sys.stderr.write(f"[acp-bridge] conn {peer_id} accepted, spawning {child_cmd}\n")
    sys.stderr.flush()
    # The spawn CAN fail, and an unhandled failure loses the whole agent silently.
    #
    # When pbench.slice reaches its TasksMax, Popen raises BlockingIOError
    # [Errno 11], and an uncaught exception kills this thread -- leaving
    # client_sock ACCEPTED with no child behind it. The router has already
    # logged "socket established" and sent initialize; it waits on that dead
    # socket for the rest of the run, and the agent never recovers, because a
    # per-connection bridge never notices, PID 1 stays alive, and docker's
    # restart policy never fires.
    #
    # Closing the socket is what makes it self-healing: the router's reconnect
    # loop already retries, it just needs the chance. Retry briefly first --
    # EAGAIN under a task ceiling is usually transient once a peer exits.
    proc = None
    for attempt in range(1, 4):
        try:
            proc = subprocess.Popen(
                child_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,  # inherit, goes to docker logs
                bufsize=0,
                close_fds=True,
                env=_child_env(),
                **_child_popen_kwargs,
            )
            break
        except (BlockingIOError, OSError) as e:
            sys.stderr.write(
                f"[acp-bridge] conn {peer_id} SPAWN FAILED (attempt {attempt}/3): "
                f"{e.__class__.__name__}: {e}\n")
            sys.stderr.flush()
            if attempt < 3:
                time.sleep(2 * attempt)
    if proc is None:
        # Give the client a closed socket rather than a silent black hole.
        sys.stderr.write(
            f"[acp-bridge] conn {peer_id} ABANDONED after 3 spawn failures; "
            f"closing socket so the client reconnects\n")
        sys.stderr.flush()
        try: client_sock.shutdown(socket.SHUT_RDWR)
        except Exception: pass
        try: client_sock.close()
        except Exception: pass
        return

    def sock_to_child():
        try:
            while True:
                b = client_sock.recv(65536)
                if not b: break
                proc.stdin.write(b)
                proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        finally:
            try: proc.stdin.close()
            except Exception: pass

    def child_to_sock():
        try:
            while True:
                b = proc.stdout.read(65536)
                if not b: break
                client_sock.sendall(b)
        except (BrokenPipeError, OSError):
            pass
        finally:
            try: client_sock.shutdown(socket.SHUT_WR)
            except Exception: pass

    t1 = threading.Thread(target=sock_to_child, daemon=True)
    t2 = threading.Thread(target=child_to_sock, daemon=True)
    t1.start(); t2.start()
    proc.wait()
    t1.join(timeout=2); t2.join(timeout=2)
    try: client_sock.close()
    except Exception: pass
    sys.stderr.write(f"[acp-bridge] conn {peer_id} child exited rc={proc.returncode}\n")
    sys.stderr.flush()

def shutdown(*_):
    try: server.close()
    except Exception: pass
    try: os.unlink(sock_path)
    except Exception: pass
    sys.exit(0)
signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

peer_counter = 0
while True:
    cs, _ = server.accept()
    peer_counter += 1
    threading.Thread(target=serve, args=(cs, peer_counter), daemon=True).start()
