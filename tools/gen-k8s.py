#!/usr/bin/env python3
"""gen-k8s.py — render the AKS manifests for a pbench profile.

WHY IT READS THE COMPOSE RENDER INSTEAD OF DECLARING ITS OWN ENV
The agent and router env is ~50 keys spread over gen-compose-prod.py's anchors
and three overlays, and it moves often. A hand-written manifest set would
drift from the docker path silently -- a profile key nothing reads, an overlay
that never carries the poller.
So the input here is `docker compose config --format json`: the SAME merged,
interpolated definition `make up` would deploy. Anything added to the compose
files reaches k8s with no change here.

WHAT IT CHANGES ON PURPOSE (everything else is passed through)
  1. 16 agent + 16 mini-router services collapse into ONE StatefulSet
     with 2 containers per pod. Scaling is `kubectl scale --replicas=N`.
  2. AGENT_NAME is derived from the pod ordinal at start, not baked per service.
  3. Bind mounts are classified, not copied (see classify_volume).

WHAT MUST NOT CHANGE, AND DOES NOT
  * In-cluster addresses. The prompts and env say http://gitea:3000,
    http://mattermost:8065, http://board-service:8660. A k8s Service of the same
    name in the same namespace resolves to exactly that, so agent-side config is
    byte-for-byte what it is under compose.
  * The reference binary stays run-not-read: an initContainer running as root
    stages /workspace/executable out of the agent image into an emptyDir at
    0111 root:root, and the agent container runs as ACP_CHILD_UID. It CANNOT go
    on the Azure Files volume -- SMB applies one file_mode to the whole share,
    so the 0111 would either not hold or would break every other file on it.
  * An agent sees only its own gitea/mattermost tokens. The full tokens dir is
    mounted into an initContainer only; that init copies the three files this
    ordinal owns into an emptyDir, which is what the agent and router mount.

Usage:
    PROFILE=pbench-multi-node-pandoc python3 tools/gen-k8s.py > /tmp/pbench.yaml
    kubectl apply -f /tmp/pbench.yaml
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = os.environ.get("PROFILE") or sys.exit("PROFILE=<profile> required")
# The profile is the namespace, so it must be a valid one.
if not re.fullmatch(r"pbench-[a-z0-9-]+", PROFILE) or len(PROFILE) > 63 or PROFILE.endswith("-"):
    sys.exit(f"FATAL: PROFILE={PROFILE} is not a usable namespace (pbench-[a-z0-9-]+, at most 63 chars)")
ENV_FILE = ROOT / f".env.{PROFILE}"

# Azure storage classes. Files (SMB, RWX) carries DATA_ROOT so the host-side
# runner can mount the same share for pbench_run.sh's idle watchdog and
# pbench_chain.sh's trajectory snapshot. Disk (RWO) carries
# gitea's sqlite and mysql's innodb, neither of which belongs on SMB.
FILES_PVC = "pbench-files"

# AKS nodes cannot see the build host's local docker images, so the four support
# images the compose files name as `omcgitea-*:local` get qualified with the
# registry, and so does a bare omcgitea-* AGENT_IMAGE from .env.<profile>.
REGISTRY = os.environ.get("PBENCH_REGISTRY", "")  # e.g. myacr.azurecr.io
# Attaching the ACR to the cluster needs an AcrPull role assignment, which is
# Owner-level; this deployer is Contributor. So pulls go through a
# docker-registry secret instead (created by scripts/pbench_k8s_up.sh).
PULL_SECRET = os.environ.get("PBENCH_PULL_SECRET", "acr-pull")

# PER-AGENT RESOURCE REQUEST. The request is what the SCHEDULER reserves, so it
# sets how many agents fit on a node and therefore how many nodes a fleet needs.
# 2 cores is right for a real agent (it compiles), and wrong by more than an
# order of magnitude for AGENT_KIND=sim, which issues one request a minute and
# is idle in between: at 2 cores a D32 holds 15 sim agents, so 1024 of them want
# ~68 nodes -- past the pool ceiling, i.e. the run simply never schedules. The
# limit is left generous either way; it is the request that decides packing.
def _profile_val(key: str, default: str) -> str:
    """Read a key from .env.<profile>, env var wins. Defined here rather than
    using env_val() below because these are module-level constants."""
    if os.environ.get(key):
        return os.environ[key]
    try:
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip() or default
    except OSError:
        pass
    return default


SC_FILES = _profile_val("PBENCH_SC_FILES", "azurefile-csi-premium")
SC_DISK = _profile_val("PBENCH_SC_DISK", "managed-csi-premium")
FILES_SIZE = _profile_val("PBENCH_FILES_SIZE", "100Gi")
MYSQL_SIZE = _profile_val("PBENCH_MYSQL_SIZE", "20Gi")
AGENT_CPU = _profile_val("PBENCH_AGENT_CPU", "2")
AGENT_MEM = _profile_val("PBENCH_AGENT_MEM", "4Gi")
AGENT_MEM_LIMIT = _profile_val("PBENCH_AGENT_MEM_LIMIT", "24Gi")

# OPTIONAL AGENT PLACEMENT, comma-separated node names.
#
# nodeSelector says which POOL and nothing about which NODES, so "2 agents here,
# 2 there" is not expressible -- and a run that wants an even split can get
# 4+0 while looking entirely normal. Empty (the default) emits nothing at all:
# pbench-scale is a live 1024-agent
# namespace and a stray placement rule there could strand pods on a node the
# autoscaler has since removed.
AGENT_NODES = [n.strip() for n in _profile_val("PBENCH_AGENT_NODES", "").split(",") if n.strip()]


def qualify(image: str) -> str:
    if REGISTRY and image.startswith("omcgitea-") and "/" not in image:
        return f"{REGISTRY}/{image}"
    return image


# PIN MUTABLE TAGS TO A DIGEST.
#
# imagePullPolicy: Always exists here because the support images are rebuilt and
# re-pushed under the same tag, and IfNotPresent then runs whatever a node
# cached. But Always makes EVERY pod hit the registry, and at 1024 pods that
# exceeds the kubelet's own registryPullQPS: pods go to ImagePullBackOff ("pull
# QPS exceeded") and the backoff is exponential, so they do not converge on
# their own.
#
# A digest gives both properties at once: the reference itself changes when the
# image changes, so IfNotPresent can never serve a stale layer, and a node that
# already has that digest does not go back to the registry. Resolve with
#   az acr manifest list-metadata -r <acr> -n <repo> --query "[?tags[0]=='pbench'].digest"
# (-r is the REGISTRY and -n the REPOSITORY; reversing them fails with the
# misleading "Registry names may contain only alpha numeric characters")
# and pass as PBENCH_IMAGE_DIGESTS=repo=sha256:...,repo2=sha256:...
_DIGESTS = {}
for _kv in (os.environ.get("PBENCH_IMAGE_DIGESTS", "") or "").split(","):
    if "=" in _kv:
        _r, _d = _kv.split("=", 1)
        _DIGESTS[_r.strip()] = _d.strip()


def pin_digest(image: str) -> str:
    """`registry/repo:tag` -> `registry/repo@sha256:...` when a digest is known."""
    base = image.split("@")[0]
    repo = base.rsplit("/", 1)[-1].split(":")[0]
    d = _DIGESTS.get(repo)
    return f"{base.split(':')[0] if '/' not in base.split(':')[0] else base.rsplit(':',1)[0]}@{d}" if d else image


def pull_policy(image: str) -> str:
    """`:local` is a MUTABLE tag -- the support images are rebuilt and re-pushed
    under it every time their source changes. With the k8s default of
    IfNotPresent a node that already cached the tag keeps running the old build
    forever, and the only symptom is a log line that reads like the previous
    version's. Pin it to Always; leave the agent image's tag and digests alone
    so the 6 GB agent image is not re-pulled on every pod start."""
    # A digest reference is immutable, so it never needs a forced re-pull.
    return "Always" if (image.endswith(":local") and "@" not in image) else "IfNotPresent"

# Services that get a ClusterIP Service. The NAME IS THE CONTRACT -- these are
# the hostnames baked into agent env and role prompts.
PORTS = {
    "gitea": 3000,
    "mattermost": 8065,
    "mysql": 3306,
    "secret-service": 8650,
    "board-service": 8660,
    "egress-proxy": 4180,
}
# nginx-edge is host-facing only (seed push / issue / submission export). It gets
# a Service so `kubectl port-forward` can reach it; agents never use it.
EDGE_PORTS = {"http": 80, "mm": 81}

# Per-service durable storage: compose bind target -> (kind, size).
DISK_MOUNTS = {
    "gitea": [("/data", "20Gi")],
    "mysql": [("/var/lib/mysql", MYSQL_SIZE)],
    "mattermost": [
        ("/mattermost/data", "10Gi"),
        ("/mattermost/config", "1Gi"),
        ("/mattermost/logs", "1Gi"),
        ("/mattermost/plugins", "1Gi"),
    ],
}
# act-runner is deliberately absent: PBENCH_CI_GATE=0 seeds no workflows, so it
# has nothing to run, and it needs a docker daemon AKS nodes do not expose.
# gitea-admin-init becomes an initContainer on gitea (same RWO disk, so it
# cannot be a separate pod).
SKIP = {"act-runner", "gitea-admin-init"}

DATA_RE = re.compile(r"/(tokens|agents|acp|gitea|mysql|mattermost|board-lifecycle)(/.*)?$")

# Resolved DATA_ROOT/<profile>. Set from bootstrap's /data mount in build(),
# because DATA_ROOT is relative to docker/ and therefore commonly INSIDE the
# repo -- which made every data path look like a repo file to classify() and
# turned the agent's home and token mounts into ConfigMap entries.
DATA_DIR = ""


def sh(cmd: list[str], **kw) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, **kw).stdout


def compose_render() -> dict:
    """The merged, interpolated compose definition -- the single source of env."""
    if not ENV_FILE.exists():
        sys.exit(f"FATAL: {ENV_FILE} missing")
    base = ROOT / f"docker/_gen-prod.{PROFILE}.yml"
    # Re-render every time, as every Makefile target does. A base left over from
    # an earlier PBENCH_WORKERS_PER_TEAM gives bootstrap the old AGENTS list
    # while the StatefulSet scales to the new count, and each extra pod's router
    # gets a 404 for its token.
    subprocess.run(["make", "-s", "render-pbench-base", f"PROFILE={PROFILE}"],
                   cwd=ROOT, check=True, capture_output=True)
    # Ask the Makefile which overlays this profile layers rather than
    # reimplementing its selection rules -- a second copy here would be one
    # more thing to drift. Same trick launch_single_node.sh uses.
    dry = sh(["make", "-n", "up", f"PROFILE={PROFILE}"])
    overlays = re.findall(r"-f (docker/docker-compose[^\s]*)", dry)
    # sudo deliberately strips the caller's environment. Preserve only the
    # non-secret compose interpolation knob that a scale launcher must override;
    # using sudo -E here would also propagate credentials and unrelated shell
    # state. Profiles still flow through --env-file and all absent values keep
    # the compose generator's historical fallback.
    compose_env = []
    for key in ("MYSQL_INNODB_BUFFER_POOL_SIZE",):
        if os.environ.get(key):
            compose_env.append(f"{key}={os.environ[key]}")
    cmd = ["sudo"]
    if compose_env:
        cmd += ["env", *compose_env]
    cmd += ["docker", "compose", "-f", str(base)]
    for o in dict.fromkeys(overlays):
        cmd += ["-f", o]
    cmd += ["--project-name", f"k8sgen-{PROFILE}", "--env-file", str(ENV_FILE),
            "--profile", PROFILE, "config", "--format", "json"]
    env = {k: v for k, v in os.environ.items()
           if k not in ("ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL", "ANTHROPIC_API_KEY",
                        "AGENT_KIND", "COPILOT_PROVIDER_TYPE", "GITEA_HOST", "GITEA_TOKEN")}
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, env=env)
    if r.returncode != 0:
        sys.exit(f"FATAL: compose config failed\n{r.stderr[:2000]}")
    return json.loads(r.stdout)


# The upstream model credential, supplied at RENDER time and never stored.
#
# .env.<profile> keeps PBENCH_LLM_UPSTREAM / UPSTREAM_AUTH_TOKEN at CHANGEME.
# The real values come from the process environment, or -- better -- from a
# settings file this reads directly, so the token exists only in memory here and
# in the k8s Secret it lands in. Nothing under the checkout ever holds it, which
# also means the generated manifest must not be committed or pasted around.
#
#   PBENCH_LLM_SETTINGS_FILE=~/.claude/settings.local.json  (reads the 3 keys)
#   ...or export UPSTREAM_AUTH_TOKEN / PBENCH_LLM_UPSTREAM / ANTHROPIC_MODEL
SETTINGS_MAP = {              # settings.json key -> service env key
    "ANTHROPIC_BASE_URL": "PBENCH_LLM_UPSTREAM",
    "ANTHROPIC_AUTH_TOKEN": "UPSTREAM_AUTH_TOKEN",
    "ANTHROPIC_MODEL": "ANTHROPIC_MODEL",
}
# One logical value can appear under more than one env NAME: compose renames
# PBENCH_LLM_UPSTREAM to UPSTREAM on the egress-proxy service, and
# strip_metadata_proxy.py reads UPSTREAM. Overriding only the profile-side
# name left the proxy on its CHANGEME default and every request died with
# `unknown url type: 'CHANGEME/v1/messages'`. Write every alias.
ALIASES = {
    "PBENCH_LLM_UPSTREAM": ("PBENCH_LLM_UPSTREAM", "UPSTREAM"),
    "UPSTREAM_AUTH_TOKEN": ("UPSTREAM_AUTH_TOKEN",),
    "ANTHROPIC_MODEL": ("ANTHROPIC_MODEL",),
}
_raw: dict[str, str] = {}
for _k in ALIASES:
    if os.environ.get(_k):
        _raw[_k] = os.environ[_k]
_sf = os.environ.get("PBENCH_LLM_SETTINGS_FILE")
if _sf:
    _cfg = json.loads(Path(_sf).expanduser().read_text()).get("env", {})
    for _src, _dst in SETTINGS_MAP.items():
        if _cfg.get(_src) and _dst not in _raw:
            # The proxy appends its own path; a trailing slash would double it.
            _raw[_dst] = str(_cfg[_src]).rstrip("/")
OVERRIDES: dict[str, str] = {
    name: val for key, val in _raw.items() for name in ALIASES[key]
}


def env_of(svc: dict) -> dict:
    """Compose leaves an unset pass-through key as None; k8s rejects a null value
    and the entrypoint only exports non-empty vars anyway, so null -> ''.

    Render-time overrides land here so they reach every service that names the
    key, whichever one that is -- UPSTREAM_AUTH_TOKEN is read by egress-proxy,
    ANTHROPIC_MODEL by all 16 agents.
    """
    out = {k: ("" if v is None else str(v)) for k, v in (svc.get("environment") or {}).items()}
    for k, v in OVERRIDES.items():
        if k in out:
            out[k] = v
    return out


def classify(src: str, tgt: str) -> tuple[str, str]:
    """(kind, detail) for one compose bind mount.

    files    -> the shared Azure Files PVC, subPath = detail
    disk     -> a per-service Azure Disk PVC
    acp      -> the in-pod emptyDir carrying the ACP unix socket (never SMB:
                SMB has no unix sockets, and the agent<->router channel IS one)
    pbenchbin-> the staged 0111 reference binary emptyDir
    repo     -> a repo file/dir, shipped as a ConfigMap; detail = repo-relative path
    skip     -> /dev/null placeholders and anything else
    """
    if tgt == "/opt/pbench/executable":
        return ("pbenchbin", "")
    if src.startswith("/dev/"):
        return ("skip", "")
    # DATA_ROOT is checked BEFORE the repo test on purpose: it is usually a path
    # inside the checkout, so the repo test would swallow it.
    if DATA_DIR and src.startswith(DATA_DIR):
        # The data root ITSELF, which is what bootstrap mounts at /data. Without
        # this case DATA_RE finds no trailing subdir and the mount is dropped:
        # bootstrap writes every token into its own ephemeral layer, they vanish
        # with the Job pod while secret-service and every agent wait on an empty
        # share, and nothing fails loudly -- the Job logs "Bootstrap done."
        if src.rstrip("/") == DATA_DIR:
            return ("files", "")
        m = DATA_RE.search(src)
        if not m:
            return ("skip", "")
        top, rest = m.group(1), (m.group(2) or "")
        if top == "acp":
            return ("acp", "")
        if top in ("gitea", "mysql", "mattermost"):
            return ("disk", top + rest)
        return ("files", top + rest)
    try:
        rel = str(Path(src).resolve().relative_to(ROOT))
        return ("repo", rel)
    except ValueError:
        return ("skip", "")


# --- ConfigMap for every repo file the compose mounts ------------------------
CM_NAME = "repo-files"
_cm_data: dict[str, str] = {}


def cm_key(rel: str) -> str:
    k = re.sub(r"[^-._a-zA-Z0-9]", "_", rel)
    return k


def add_repo_file(rel: str) -> list[tuple[str, str]]:
    """Register a repo file (or every file under a repo dir). Returns
    [(configmap key, path relative to the mount target)]."""
    p = ROOT / rel
    out = []
    if p.is_dir():
        for f in sorted(p.rglob("*")):
            if f.is_file():
                r = str(f.relative_to(ROOT))
                _cm_data[cm_key(r)] = f.read_text(errors="replace")
                out.append((cm_key(r), str(f.relative_to(p))))
    elif p.is_file():
        _cm_data[cm_key(rel)] = p.read_text(errors="replace")
        out.append((cm_key(rel), ""))
    return out


def env_checksum(env: dict) -> str:
    """A Secret change does NOT restart the pods that consume it. Without this,
    `apply` updates the Secret, reports everything configured, and every pod goes
    on running the old values -- which is how the egress-proxy kept serving
    CHANGEME as its upstream for 35 hours after the real credential was injected,
    while `kubectl get pods` showed it healthy. Stamping the digest into the pod
    template makes the template itself change, so the rollout happens."""
    blob = "\0".join(f"{k}={v}" for k, v in sorted(env.items()))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def meta(name: str, ns: str, **kw) -> dict:
    m = {"name": name, "namespace": ns}
    m.update(kw)
    return m


def build(cfg: dict) -> list[dict]:
    global DATA_DIR
    svcs = cfg["services"]
    # bootstrap mounts DATA_ROOT/<profile> at /data and nothing else does, so it
    # is the one unambiguous place to read the resolved data root from.
    for v in svcs.get("bootstrap", {}).get("volumes", []):
        if v.get("target") == "/data":
            DATA_DIR = v.get("source", "").rstrip("/")
    if not DATA_DIR:
        sys.exit("FATAL: could not resolve DATA_ROOT from the bootstrap /data mount")
    ns = PROFILE
    docs: list[dict] = [{"apiVersion": "v1", "kind": "Namespace",
                         "metadata": {"name": ns, "labels": {"pbench-profile": PROFILE}}}]

    # Shared RWX volume = DATA_ROOT. One per namespace, so two runs never share
    # state -- the same isolation the per-profile DATA_ROOT gives under compose.
    docs.append({
        "apiVersion": "v1", "kind": "PersistentVolumeClaim",
        "metadata": meta(FILES_PVC, ns),
        "spec": {"accessModes": ["ReadWriteMany"], "storageClassName": SC_FILES,
                 "resources": {"requests": {"storage": FILES_SIZE}}},
    })

    agent_tmpl = svcs.get("agent-worker1")
    router_tmpl = svcs.get("mini-router-worker1")
    if not agent_tmpl or not router_tmpl:
        sys.exit("FATAL: no agent-worker1 in the rendered compose base")
    replicas = int(os.environ.get("PBENCH_WORKERS_PER_TEAM")
                   or env_val("PBENCH_WORKERS_PER_TEAM") or 16)

    for name in sorted(svcs):
        if name in SKIP or name.startswith(("agent-worker", "mini-router-worker")):
            continue
        docs += infra_workload(name, svcs[name], ns, svcs)

    docs += agent_statefulset(agent_tmpl, router_tmpl, ns, replicas)
    docs += network_policies(ns)

    # ConfigMap last: add_repo_file() populates it as the workloads are built.
    docs.insert(1, {"apiVersion": "v1", "kind": "ConfigMap",
                    "metadata": meta(CM_NAME, ns), "data": dict(sorted(_cm_data.items()))})
    return docs



def network_policies(ns: str) -> list[dict]:
    """The egress lock, expressed the only way k8s can express it.

    Under compose this is structural: the default network is `internal: true`,
    so nothing on it has a route off the host, and egress-proxy is dual-homed.
    A cluster has no such thing -- every pod can reach the internet until a
    policy says otherwise -- so the invariant has to be restated here. It is not
    cosmetic: an agent that can reach the real model endpoint, or github, or the
    task's upstream source, has voided the run.

    Four rules, in the order they compose:
      1. deny ALL egress in the namespace (an empty egress list on an
         all-pods selector);
      2. put DNS back, or nothing resolves `gitea` and every rule below is moot;
      3. put same-namespace traffic back -- this is what keeps gitea:3000,
         mattermost:8065 and board-service:8660 working exactly as before;
      4. give egress-proxy, and only egress-proxy, the outside world.

    Requires a policy-enforcing dataplane. The cluster is created with
    `--network-dataplane cilium --network-policy cilium`; on a cluster without
    one these objects are accepted and silently enforce NOTHING, so probe the
    behaviour rather than trusting that the objects exist: a pod carrying an
    agent's labels must fail to reach a public host.
    """
    def np(name, spec):
        return {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
                "metadata": meta(name, ns), "spec": spec}

    return [
        np("default-deny-egress", {
            "podSelector": {}, "policyTypes": ["Egress"], "egress": []}),
        np("allow-dns", {
            "podSelector": {}, "policyTypes": ["Egress"],
            "egress": [{
                "to": [{"namespaceSelector": {"matchLabels": {
                    "kubernetes.io/metadata.name": "kube-system"}}}],
                "ports": [{"protocol": "UDP", "port": 53},
                          {"protocol": "TCP", "port": 53}]}]}),
        np("allow-same-namespace", {
            "podSelector": {}, "policyTypes": ["Egress"],
            "egress": [{"to": [{"podSelector": {}}]}]}),
        np("egress-proxy-to-internet", {
            "podSelector": {"matchLabels": {"app": "egress-proxy"}},
            "policyTypes": ["Egress"],
            "egress": [{"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}]}]}),
    ]


def env_val(key: str) -> str:
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""


def mounts_from(svc: dict, name: str) -> tuple[list, list, list]:
    """-> (volumeMounts, pod volumes, extra PVC docs)"""
    vm, vols, pvcs = [], [], []
    seen_disk = {}
    dir_vols: dict[str, list] = {}
    for v in svc.get("volumes", []):
        src, tgt = v.get("source", ""), v.get("target", "")
        kind, detail = classify(src, tgt)
        ro = bool(v.get("read_only"))
        if kind == "skip":
            continue
        if kind == "files":
            m = {"name": "files", "mountPath": tgt, "readOnly": ro}
            if detail:                      # "" means the share root (bootstrap's /data)
                m["subPath"] = detail
            vm.append(m)
        elif kind == "disk":
            vol = f"{name}-{detail.replace('/', '-')}"
            seen_disk[vol] = next((s for t, s in DISK_MOUNTS.get(name, []) if t == tgt), "5Gi")
            vm.append({"name": vol, "mountPath": tgt})
        elif kind == "repo":
            entries = add_repo_file(detail)
            if (ROOT / detail).is_dir():
                # A DIRECTORY bind mount REPLACES the target directory. Per-file
                # subPath mounts do not: they leave whatever the image already
                # shipped in place. nginx-edge is where that bites -- the stock
                # image's /etc/nginx/conf.d/default.conf survived, kept :80 as
                # the default server, and every request to localhost got the
                # welcome page's 404 instead of gitea. Project the whole dir.
                vol = "repo-" + re.sub(r"[^a-z0-9-]", "-", detail.lower()).strip("-")
                vm.append({"name": vol, "mountPath": tgt, "readOnly": True})
                dir_vols[vol] = [{"key": k, "path": sub} for k, sub in entries]
            else:
                for key, sub in entries:
                    vm.append({"name": "repo", "mountPath": tgt if not sub else f"{tgt}/{sub}",
                               "subPath": key, "readOnly": True})
    if any(m["name"] == "files" for m in vm):
        vols.append({"name": "files", "persistentVolumeClaim": {"claimName": FILES_PVC}})
    if any(m["name"] == "repo" for m in vm):
        # 0755: acp-bridge.py is executed, and a mount that made it 0644 looped
        # every agent once already (dev 43cdc1e).
        vols.append({"name": "repo", "configMap": {"name": CM_NAME, "defaultMode": 0o755}})
    for vol, items in dir_vols.items():
        vols.append({"name": vol, "configMap": {"name": CM_NAME, "defaultMode": 0o755,
                                                "items": items}})
    for vol, size in seen_disk.items():
        vols.append({"name": vol, "persistentVolumeClaim": {"claimName": vol}})
        pvcs.append({"apiVersion": "v1", "kind": "PersistentVolumeClaim",
                     "metadata": {"name": vol, "namespace": "PLACEHOLDER"},
                     "spec": {"accessModes": ["ReadWriteOnce"], "storageClassName": SC_DISK,
                              "resources": {"requests": {"storage": size}}}})
    return vm, vols, pvcs


def secret_env(name: str, ns: str, env: dict) -> tuple[dict, dict]:
    s = {"apiVersion": "v1", "kind": "Secret", "metadata": meta(f"{name}-env", ns),
         "type": "Opaque", "stringData": env}
    return s, {"secretRef": {"name": f"{name}-env"}}


def infra_workload(name: str, svc: dict, ns: str, svcs: dict) -> list[dict]:
    docs = []
    vm, vols, pvcs = mounts_from(svc, name)
    for p in pvcs:
        p["metadata"]["namespace"] = ns
        docs.append(p)
    svc_env = env_of(svc)
    if name == "bootstrap":
        # k8s owns "has this run": the Job's completion status is the record and
        # pbench_k8s_up.sh recreates the Job. bootstrap.sh's own .bootstrap-done
        # marker lives on the shared volume and would outlive the Job, turning
        # every redeploy into a silent no-op that still reports success.
        svc_env["PBENCH_BOOTSTRAP_FORCE"] = "1"
    sec, envfrom = secret_env(name, ns, svc_env)
    docs.append(sec)

    container = {
        "name": name, "image": pin_digest(qualify(svc["image"])),
        "imagePullPolicy": pull_policy(pin_digest(qualify(svc["image"]))), "envFrom": [envfrom],
        "volumeMounts": vm,
    }
    if svc.get("command"):
        container["args"] = [str(x) for x in svc["command"]]
    if svc.get("entrypoint"):
        container["command"] = [str(x) for x in svc["entrypoint"]]
    if name in PORTS:
        container["ports"] = [{"containerPort": PORTS[name], "name": "svc"}]
    if name == "nginx-edge":
        container["ports"] = [{"containerPort": v, "name": k} for k, v in EDGE_PORTS.items()]
    if name == "mattermost":
        # The image runs as uid 2000 and cannot chown an Azure Disk root.
        pass

    pod = {"containers": [container], "volumes": vols,
           "imagePullSecrets": [{"name": PULL_SECRET}]}
    if name in ("mysql", "mattermost", "gitea"):
        pod["securityContext"] = {"fsGroup": 2000 if name == "mattermost" else 1000}
    if name == "gitea":
        # gitea-admin-init writes into the SAME RWO disk gitea serves from, so it
        # cannot be its own pod on k8s -- and it cannot be an initContainer
        # either: it reads /data/gitea/conf/app.ini, which does not exist until
        # gitea has started once (under compose it waits on service_healthy).
        # So it becomes a SIDECAR that waits for the local server, runs the
        # unmodified script, then parks. Same image, same mounts, same script.
        ai = svcs.get("gitea-admin-init")
        if ai and ai.get("entrypoint"):
            script = str(ai["entrypoint"][-1])
            wait = ("until wget -q -O- http://localhost:3000/api/v1/version >/dev/null 2>&1; "
                    "do sleep 2; done; ")
            side = {"name": "gitea-admin-init", "image": pin_digest(qualify(ai["image"])),
                    "imagePullPolicy": pull_policy(pin_digest(qualify(ai["image"]))),
                    "command": ["/bin/sh", "-c"],
                    # Wrapped in a SUBSHELL: the script ends with `exit 0` on the
                    # already-provisioned path, which would short-circuit the
                    # keep-alive below: the container exits, the kubelet
                    # restarts it, gitea-0 sits at 1/2 CrashLoopBackOff, the
                    # Service drops its only endpoint, and bootstrap times out
                    # waiting for a gitea that is in fact serving fine.
                    "args": [wait + "( " + script + " )\n"
                             "echo '[admin-init] done'; sleep infinity"],
                    "env": [{"name": k, "value": v} for k, v in sorted(env_of(ai).items())],
                    "volumeMounts": [m for m in vm if m["mountPath"] == "/data"]}
            if ai.get("user"):
                uid, _, gid = str(ai["user"]).partition(":")
                side["securityContext"] = {"runAsUser": int(uid), "runAsGroup": int(gid or uid)}
            pod["containers"].append(side)

    labels = {"app": name}
    ann = {"pbench/env-checksum": env_checksum(svc_env)}
    if name == "bootstrap":
        # Under compose this waits on `gitea-admin-init: service_completed_successfully`.
        # On k8s admin-init is a sidecar of the gitea pod, so there is no
        # completion to depend on and bootstrap raced it: the first pod died with
        # "Admin user 'chairman' check failed (HTTP 401)" and only the Job retry
        # succeeded. backoffLimit is not a synchronisation primitive -- wait for
        # the credential the script's very first call needs.
        pod["initContainers"] = [{
            "name": "wait-for-gitea-admin",
            "image": "curlimages/curl:8.11.1",
            "envFrom": [envfrom],
            "command": ["/bin/sh", "-c",
                        'n=0; until curl -sf -u "$GITEA_ADMIN_USER:$GITEA_ADMIN_PASSWORD" '
                        'http://gitea:3000/api/v1/user >/dev/null 2>&1; do '
                        'n=$((n+1)); [ $n -gt 150 ] && echo "gitea admin never appeared" && exit 1; '
                        'sleep 2; done; echo "gitea admin ready after $((n*2))s"'],
        }]
        docs.append({"apiVersion": "batch/v1", "kind": "Job",
                     "metadata": meta(name, ns),
                     "spec": {"backoffLimit": 2, "template": {
                         "metadata": {"labels": labels, "annotations": ann},
                         "spec": dict(pod, restartPolicy="Never")}}})
        return docs

    kind = "StatefulSet" if name in DISK_MOUNTS else "Deployment"
    spec = {"replicas": 1, "selector": {"matchLabels": labels},
            "template": {"metadata": {"labels": labels, "annotations": ann},
                         "spec": pod}}
    if kind == "StatefulSet":
        spec["serviceName"] = name
    elif name == "board-service":
        # Its board is hydrated into process memory. A rolling Deployment would
        # briefly split reads and writes across two divergent copies, even though
        # the pending-delivery mutex itself is durable in MySQL.
        spec["strategy"] = {"type": "Recreate"}
    docs.append({"apiVersion": "apps/v1", "kind": kind, "metadata": meta(name, ns), "spec": spec})

    if name in PORTS:
        docs.append({"apiVersion": "v1", "kind": "Service", "metadata": meta(name, ns),
                     "spec": {"selector": labels,
                              "ports": [{"port": PORTS[name], "targetPort": PORTS[name]}]}})
    if name == "nginx-edge":
        docs.append({"apiVersion": "v1", "kind": "Service", "metadata": meta(name, ns),
                     "spec": {"selector": labels,
                              "ports": [{"name": k, "port": v, "targetPort": v}
                                        for k, v in EDGE_PORTS.items()]}})
    return docs


def agent_statefulset(agent: dict, router: dict, ns: str, replicas: int) -> list[dict]:
    """One StatefulSet, two containers per pod. This is where scaling lives."""
    docs = []
    org = env_val("ORG_NAME") or "pbench"

    a_env = env_of(agent)
    r_env = env_of(router)
    # Per-ordinal at runtime, not per-service at render time.
    for k in ("AGENT_NAME", "GITEA_TOKEN_FILE"):
        a_env.pop(k, None)
    for k in ("AGENT_NAME", "GITEA_PASSWORD_FILE"):
        r_env.pop(k, None)

    docs.append({"apiVersion": "v1", "kind": "Secret", "metadata": meta("agent-env", ns),
                 "type": "Opaque", "stringData": a_env})
    docs.append({"apiVersion": "v1", "kind": "Secret", "metadata": meta("router-env", ns),
                 "type": "Opaque", "stringData": r_env})

    a_vm, a_vols, _ = mounts_from(agent, "agent")
    # Drop the compose token + home binds: they name worker1, and a StatefulSet
    # has ONE spec for every ordinal.
    a_vm = [m for m in a_vm if not m.get("mountPath", "").startswith("/run/omcgitea/tokens")
            and m.get("mountPath") != "/opt/data"]
    a_vm += [
        {"name": "acp", "mountPath": "/var/run/acp"},
        {"name": "tokens-mine", "mountPath": "/run/omcgitea/tokens", "readOnly": True},
        {"name": "pbench-bin", "mountPath": "/opt/pbench"},
        # The whole agents/ tree, not one agent's dir: AGENT_HOME below picks
        # the per-ordinal subdir at start. Keeping the layout as
        # <share>/agents/<agent-name>/ is what pbench_run.sh's idle watchdog
        # glob and pbench_chain.sh's trajectory snapshot read.
        {"name": "files", "mountPath": "/opt/data-root", "subPath": "agents"},
    ]

    r_vm = [{"name": "acp", "mountPath": "/var/run/acp"},
            {"name": "tokens-mine", "mountPath": "/run/omcgitea/tokens", "readOnly": True}]

    name_expr = (f'i=${{HOSTNAME##*-}}; export AGENT_NAME="{org}-worker$((i+1))"; ')
    agent_cmd = (name_expr +
                 'export GITEA_TOKEN_FILE="/run/omcgitea/tokens/agent-$AGENT_NAME.token"; '
                 'export AGENT_HOME="/opt/data-root/$AGENT_NAME"; '
                 'mkdir -p "$AGENT_HOME"; '
                 'exec /opt/omcgitea/entrypoint.sh')
    router_cmd = (name_expr +
                  'export GITEA_PASSWORD_FILE="/run/omcgitea/tokens/agent-$AGENT_NAME.password"; '
                  'cd /app && exec node dist/main.js')

    # Stage the reference binary run-not-read. The per-task agent image is FROM
    # the task cleanroom, so /workspace/executable is already inside it and no
    # host staging is needed (tools/pbench_submission.py:246).
    stage_bin = {
        "name": "stage-reference-binary", "image": pin_digest(qualify(agent["image"])),
        "securityContext": {"runAsUser": 0},
        # AGENT_KIND=sim images are built FROM the generic agent image, not from a
        # ProgramBench cleanroom, so they carry no /workspace/executable -- and a
        # sim agent never runs one. Absence is therefore legal, but it is stated
        # in the log rather than passed over: on a REAL task the same silence
        # would mean the team is reverse-engineering nothing and the run is void,
        # and that must not look like a normal startup.
        "command": ["/bin/sh", "-c",
                    "if [ -f /workspace/executable ]; then "
                    "  cp /workspace/executable /pbench/executable && "
                    "  chown 0:0 /pbench/executable && chmod 0111 /pbench/executable && "
                    "  ls -l /pbench/executable; "
                    "else "
                    "  echo 'NO /workspace/executable in this image -- expected only for "
                    "AGENT_KIND=sim; a real task image without it means the reference is "
                    "missing and the run is void'; "
                    "fi"],
        "volumeMounts": [{"name": "pbench-bin", "mountPath": "/pbench"}],
    }
    # The ONLY container that ever sees the whole tokens dir. It copies out the
    # three files this ordinal owns; the agent and router mount the result, so a
    # peer's token is not reachable from either.
    take_tokens = {
        "name": "take-own-tokens", "image": pin_digest(qualify(agent["image"])),
        "securityContext": {"runAsUser": 0},
        "command": ["/bin/sh", "-c", name_expr + (
            'for t in .token -mm.token .password; do '
            '  case "$t" in -mm.token) f="agent-$AGENT_NAME-mm.token";; '
            '                .token) f="agent-$AGENT_NAME.token";; '
            '                .password) f="agent-$AGENT_NAME.password";; esac; '
            '  n=0; while [ ! -f "/all-tokens/$f" ] && [ $n -lt 600 ]; do sleep 2; n=$((n+1)); done; '
            '  cp "/all-tokens/$f" "/mine/$f" || echo "MISSING $f"; done; '
            'chown -R ' + (env_val("ACP_CHILD_UID") or "10000") + ' /mine; chmod 0400 /mine/*; ls -l /mine')],
        "volumeMounts": [{"name": "files", "mountPath": "/all-tokens", "subPath": "tokens", "readOnly": True},
                         {"name": "tokens-mine", "mountPath": "/mine"}],
    }

    # Select by what the mounts actually reference, not by a hardcoded pair:
    # the per-directory ConfigMap volumes (mcp-board, mcp-notice-shim) are named
    # after their path, so an allow-list of ("files", "repo") silently dropped
    # them and the API server rejected the StatefulSet with "volumeMounts[11]:
    # Not found".
    _referenced = {m["name"] for m in a_vm}
    pod_vols = [v for v in a_vols if v["name"] in _referenced] + [
        {"name": "acp", "emptyDir": {}},
        {"name": "tokens-mine", "emptyDir": {}},
        {"name": "pbench-bin", "emptyDir": {}},
    ]

    sts = {
        "apiVersion": "apps/v1", "kind": "StatefulSet",
        "metadata": meta("agent", ns),
        "spec": {
            "serviceName": "agent",
            "replicas": replicas,
            # Pod N+1 starts only after N is Ready: the staggered bringup
            # pbench_run.sh does by hand under compose.
            # OrderedReady is REQUIRED for a real agent: 128 CLIs unpacking at
            # once left 80 of them broken, so pod N+1 must wait for N. A sim
            # agent unpacks nothing, and the serialisation costs an hour of ramp
            # at 256 and four at 1024 -- and worse, it makes the fleet fragile:
            # one pod stuck Terminating (which the autoscaler causes routinely
            # when it consolidates nodes) halts every remaining pod behind it.
            # Observed here: 255/256 frozen for 40+ minutes behind one pod.
            "podManagementPolicy": ("Parallel" if a_env.get("AGENT_KIND") == "sim"
                                    else "OrderedReady"),
            "selector": {"matchLabels": {"app": "agent"}},
            "template": {
                "metadata": {"labels": {"app": "agent"},
                             "annotations": {
                                 "pbench/env-checksum":
                                     env_checksum({**a_env, **r_env}),
                                 # An agent owns hours of unrecoverable work in an
                                 # emptyDir. scaleDownUtilizationThreshold is 0.5 and
                                 # a D32ds_v5 holding ONE agent sits at 45.6%
                                 # requested, so the autoscaler would consider that
                                 # node for removal whenever the fleet is odd -- and
                                 # skipNodesWithLocalStorage is false here, so the
                                 # emptyDir does not protect it.
                                 "cluster-autoscaler.kubernetes.io/safe-to-evict":
                                     "false"}},
                "spec": {
                    "initContainers": [stage_bin, take_tokens],
                    "containers": [
                        {"name": "agent", "image": pin_digest(qualify(agent["image"])),
                         "command": ["/bin/sh", "-c"], "args": [agent_cmd],
                         "envFrom": [{"secretRef": {"name": "agent-env"}}],
                         "volumeMounts": a_vm,
                         "resources": {"requests": {"cpu": AGENT_CPU, "memory": AGENT_MEM},
                                       "limits": {"memory": AGENT_MEM_LIMIT}}},
                        {"name": "router", "image": pin_digest(qualify(router["image"])),
                         "imagePullPolicy": pull_policy(pin_digest(qualify(router["image"]))),
                         "command": ["/bin/sh", "-c"], "args": [router_cmd],
                         "envFrom": [{"secretRef": {"name": "router-env"}}],
                         "volumeMounts": r_vm,
                         "resources": {"requests": {"cpu": "100m", "memory": "256Mi"},
                                       "limits": {"memory": "2Gi"}}},
                    ],
                    "volumes": pod_vols,
                    "imagePullSecrets": [{"name": PULL_SECRET}],
                    # Keep agents off the system pool: at 2 CPU requested each,
                    # 16 of them do not fit beside the control-plane add-ons, and
                    # the cluster autoscaler only grows the pool they ask for.
                    "nodeSelector": {"workload": "agents"},
                },
            },
            "volumeClaimTemplates": [],
        },
    }
    # Pin to named nodes and force an even spread across them. Added ALONGSIDE
    # nodeSelector, not instead of it: the pool label is what keeps agents off
    # the system pool, and dropping it would let one land beside the
    # control-plane add-ons the moment the named hosts fill.
    #
    # maxSkew: 1 is the mechanism, not decoration. With N nodes permitted, it is
    # what makes the scheduler REFUSE a lopsided placement instead of merely
    # preferring a balanced one -- at maxSkew 2 a 4-replica run over 2 nodes
    # accepts 3+1. And whenUnsatisfiable must be DoNotSchedule: ScheduleAnyway
    # degrades silently under pressure, which produces a run that reports
    # healthy while testing a topology nobody asked for. Pending pods are the
    # louder failure, and the one you can act on.
    if AGENT_NODES:
        pod_spec = sts["spec"]["template"]["spec"]
        pod_spec["affinity"] = {
            "nodeAffinity": {
                "requiredDuringSchedulingIgnoredDuringExecution": {
                    "nodeSelectorTerms": [{
                        "matchExpressions": [{
                            "key": "kubernetes.io/hostname",
                            "operator": "In",
                            "values": AGENT_NODES,
                        }],
                    }],
                },
            },
        }
        pod_spec["topologySpreadConstraints"] = [{
            "maxSkew": 1,
            "topologyKey": "kubernetes.io/hostname",
            "whenUnsatisfiable": "DoNotSchedule",
            "labelSelector": {"matchLabels": {"app": "agent"}},
        }]
    docs.append(sts)
    docs.append({"apiVersion": "v1", "kind": "Service", "metadata": meta("agent", ns),
                 "spec": {"clusterIP": "None", "selector": {"app": "agent"},
                          "ports": [{"port": 8645, "name": "metrics"}]}})
    return docs


def main() -> int:
    try:
        import yaml
    except ImportError:
        sys.exit("FATAL: pyyaml required (pip install pyyaml)")
    docs = build(compose_render())
    print(yaml.dump_all(docs, default_flow_style=False, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
