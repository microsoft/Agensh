"""Exact identity registry for OWN native metadata peers; no stacks/argv.

Only /proc identity, credentials and namespace control metadata. The owner
registers original launcher/Docker births, NEVER identities claimed by senders.
No global process/GC scan, private file, stack, command line or signal action.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading

from common import need


@dataclass(frozen=True)
class ProcessBirth:
    pid: int
    start_ticks: int
    boot_id: str
    uid: int
    gid: int
    pid_namespace: int
    network_namespace: int
    mount_namespace: int


def process_birth(pid):
    need(type(pid) is int and pid > 0, "DYNTEAM_EXACT_NATIVE_PEER_PID")
    p = Path("/proc") / str(pid)
    # comm is opaque: find the final delimiter rather than exposing/parsing it.
    raw = (p / "stat").read_bytes()
    fields = raw[raw.rfind(b")") + 2:].split()
    start = int(fields[19])
    status = {}
    for line in (p / "status").read_bytes().splitlines():
        key, sep, values = line.partition(b":")
        if sep and key in (b"Uid", b"Gid"):
            status[key] = tuple(map(int, values.split()))
    need(len(set(status[b"Uid"])) == 1 and len(set(status[b"Gid"])) == 1,
         "DYNTEAM_NATIVE_PEER_NO_MIXED_CREDENTIALS")
    result = ProcessBirth(pid, start, Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                          status[b"Uid"][0], status[b"Gid"][0], (p / "ns/pid").stat().st_ino,
                          (p / "ns/net").stat().st_ino, (p / "ns/mnt").stat().st_ino)
    again = (p / "stat").read_bytes()
    need(int(again[again.rfind(b")") + 2:].split()[19]) == start,
         "DYNTEAM_NATIVE_PEER_PID_REUSE_RACE")
    return result


class NativePeerRegistry:
    def __init__(self, *, source_commit, allowed_bindings):
        need(type(source_commit) is str and len(source_commit) == 40 and
             all(c in "0123456789abcdef" for c in source_commit), "DYNTEAM_NATIVE_PEER_SOURCE_PIN")
        self.source_commit = source_commit
        self.allowed = frozenset(allowed_bindings)
        self._lock = threading.Lock()
        self._peers = {}
        self._retired = set()
        self._retired_bindings = set()

    def register_from_launcher(self, trajectory, role, birth, *, expected_birth, purpose="router"):
        need(type(birth) is ProcessBirth and type(expected_birth) is ProcessBirth and
             birth == expected_birth and (trajectory, role) in self.allowed and purpose in ("router", "bridge", "launcher") and
             (purpose!='launcher' or role=='worker-00'),
             "DYNTEAM_TRUSTED_LAUNCHER_EXACT_NATIVE_PEER")
        # /proc I/O is outside every registry/ledger/science lock.
        need(process_birth(birth.pid) == birth, "DYNTEAM_FRESH_NATIVE_PEER_BIRTH")
        with self._lock:
            key = (trajectory, role, purpose)
            if self._peers.get(key) == birth:
                return False
            need(key not in self._peers and birth not in self._retired and
                 all(p.pid != birth.pid for p in self._peers.values()),
                 "DYNTEAM_NATIVE_PEER_ALREADY_REGISTERED_OR_NOT_RETIRED")
            self._peers[key] = birth
            return True

    def validate(self, envelope, peercred):
        if type(peercred) is not tuple or len(peercred) != 3:
            return False
        purpose = ('launcher' if envelope.get('schema')=='count14-native-spawn-control-v2' else
                   "bridge" if envelope.get("schema") == "count14-native-bridge-lifecycle-v1" else "router")
        key = (envelope.get("trajectory_id"), envelope.get("role_slot"), purpose)
        with self._lock:
            birth = self._peers.get(key)
        if birth is None or envelope.get("source_commit") != self.source_commit:
            return False
        if purpose=='launcher':
            try:
                client=process_birth(peercred[0])
                raw=Path('/proc',str(client.pid),'stat').read_bytes()
                parent=int(raw[raw.rfind(b')')+2:].split()[1])
                if (peercred!=(client.pid,birth.uid,birth.gid) or parent!=birth.pid or
                    (client.pid_namespace,client.mount_namespace,client.network_namespace)!=
                    (birth.pid_namespace,birth.mount_namespace,birth.network_namespace)):
                    return False
            except (OSError,ValueError,IndexError,KeyError):return False
        elif peercred != (birth.pid,birth.uid,birth.gid):return False
        try:
            current = process_birth(birth.pid)
        except (OSError, ValueError, IndexError, KeyError):
            return False
        with self._lock:
            return current == birth and self._peers.get(key) == birth

    def retire_after_exit(self, trajectory, role, birth, *, original_physical_clear, purpose="router"):
        need(original_physical_clear is True, "DYNTEAM_NATIVE_PEER_RETAIN_UNTIL_PHYSICAL_CLEAR")
        try:
            current = process_birth(birth.pid)
        except FileNotFoundError:
            current = None
        need(current != birth, "DYNTEAM_NATIVE_PEER_STILL_SAME_BIRTH_LIVE")
        with self._lock:
            key = (trajectory, role, purpose)
            if key not in self._peers and (key,birth) in self._retired_bindings:
                return False # same exact already-retired birth, never a live/different peer
            need(self._peers.get(key) == birth, "DYNTEAM_RETIRE_EXACT_NATIVE_PEER")
            del self._peers[key]
            self._retired.add(birth)
            self._retired_bindings.add((key,birth))
            return True
