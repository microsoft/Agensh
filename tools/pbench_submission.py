#!/usr/bin/env python3
# Move cleanroom assets into a fresh workspace and export committed source for eval.
# Keep the reference executable outside the repository; submissions contain a root
# compile.sh and exclude the root executable so the evaluator must rebuild it.

import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile
import urllib.parse
import uuid
from pathlib import Path


def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def _redact(text: str, url: str) -> str:
    userinfo = urllib.parse.urlsplit(url).netloc.rpartition("@")[0]
    if userinfo:
        user, _, pw = userinfo.partition(":")
        secret = pw or user
        for s in sorted({userinfo, secret, urllib.parse.unquote(secret)} - {""},
                        key=len, reverse=True):
            text = text.replace(s, "***")
    return re.sub(r"://[^/\s@]+@", "://***@", text)


DOCKER = os.environ.get("PBENCH_DOCKER", "docker").split()

BANNED_ROOT_ENTRIES = ("executable",)

DEFAULT_COMPILE_SH = """#!/bin/sh
set -e
cd "$(dirname "$0")"
if [ -f Makefile ] || [ -f makefile ]; then
    make
    exit $?
fi
SRCS=$(find . -name '*.c' -not -path './tests/*' -not -path './test/*' 2>/dev/null | sort)
if [ -n "$SRCS" ]; then
    ${CC:-cc} -O2 -I. -Isrc -o executable $SRCS -lm ${LDLIBS:-}
    exit $?
fi
echo "compile.sh: no Makefile and no C sources found" >&2
exit 1
"""


def _ensure_compile_sh(dest: Path) -> bool:
    # Supply the legacy Make/C fallback only when a nonempty export lacks compile.sh.
    listing = subprocess.run(
        ["tar", "-tzf", str(dest)], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    roots = {p.lstrip("./").split("/", 1)[0] for p in listing if p.strip()}
    if "compile.sh" in roots or not roots:
        return False
    with tempfile.TemporaryDirectory(prefix="pbench-compilesh-") as tmp:
        stage = Path(tmp) / "stage"
        stage.mkdir()
        _run(["tar", "-xzf", str(dest), "-C", str(stage)])
        sh = stage / "compile.sh"
        sh.write_text(DEFAULT_COMPILE_SH)
        sh.chmod(0o755)
        out = Path(tmp) / "out.tar.gz"
        _run(["tar", "-C", str(stage), "-czf", str(out), "."])
        out.replace(dest)
    print("[export] WARNING: submission had no root compile.sh; staged the default "
          "so the team's sources still get a build attempt")
    return True


def _strip_banned(dest: Path) -> None:
    # Strip only root-level artifacts; similarly named source assets remain valid.
    listing = subprocess.run(
        ["tar", "-tzf", str(dest)], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    present = [
        p for p in listing
        if p.strip().lstrip("./").rstrip("/") in BANNED_ROOT_ENTRIES
    ]
    if not present:
        return
    tmp = dest.with_suffix(".stripped.tar.gz")
    subprocess.run(
        ["bash", "-c",
         f"rm -rf {shlex.quote(str(dest))}.d && "
         f"mkdir -p {shlex.quote(str(dest))}.d && "
         f"tar -xzf {shlex.quote(str(dest))} -C {shlex.quote(str(dest))}.d && "
         + " && ".join(
             f"rm -rf {shlex.quote(str(dest))}.d/{shlex.quote(b)}"
             for b in BANNED_ROOT_ENTRIES
         )
         + f" && tar -C {shlex.quote(str(dest))}.d -czf {shlex.quote(str(tmp))} . && "
         f"rm -rf {shlex.quote(str(dest))}.d"],
        check=True,
    )
    tmp.replace(dest)
    print(f"[export] STRIPPED pre-built artifact(s) from submission: "
          f"{sorted(set(p.strip() for p in present))}")


def export_from_dir(repo_dir: Path, task: str, out_dir: Path) -> Path:
    # git archive excludes uncommitted files and repository metadata by construction.
    repo_dir = repo_dir.resolve()
    if not (repo_dir / ".git").exists():
        sys.exit(f"[export] {repo_dir} is not a git repo (no .git)")

    dest_dir = out_dir / task
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "submission.tar.gz"

    with dest.open("wb") as f:
        _run(
            ["git", "-C", str(repo_dir), "archive", "--format=tar.gz", "HEAD"],
            stdout=f,
        )

    _strip_banned(dest)
    _ensure_compile_sh(dest)

    listing = subprocess.run(
        ["tar", "-tzf", str(dest)], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    roots = {p.lstrip("./").split("/", 1)[0] for p in listing if p.strip()}
    if "compile.sh" not in roots:
        sys.exit(
            f"[export] FATAL: submission has no root-level compile.sh "
            f"(top entries: {sorted(roots)[:8]}). ProgramBench eval requires "
            f"./compile.sh at the workspace root."
        )
    print(f"[export] wrote {dest} ({dest.stat().st_size} bytes); "
          f"root entries: {sorted(roots)}")
    return dest


def export_from_gitea(url: str, task: str, out_dir: Path, ref: str = "HEAD") -> Path:
    with tempfile.TemporaryDirectory(prefix="pbench-clone-") as tmp:
        clone_dir = Path(tmp) / "repo"
        cmd = ["git", "clone", "--quiet", "--depth", "1"]
        if ref != "HEAD":
            cmd += ["--branch", ref]
        p = subprocess.run(cmd + [url, str(clone_dir)],
                           capture_output=True, text=True, errors="replace")
        if p.returncode != 0:
            sys.exit(f"[export] git clone failed (exit {p.returncode}): "
                     f"{_redact(p.stderr.strip(), url)}")
        return export_from_dir(clone_dir, task, out_dir)


def seed_from_image(image: str, into_dir: Path, bin_out: Path | None = None) -> Path:
    into_dir.mkdir(parents=True, exist_ok=True)
    container_name = f"omcgitea-pbench-seed-{uuid.uuid4().hex}"
    cid = subprocess.run(
        [*DOCKER, "create", "--name", container_name, image], capture_output=True, text=True, check=True
    ).stdout.strip()
    try:
        tar_proc = subprocess.Popen(
            [*DOCKER, "cp", f"{cid}:/workspace/.", "-"], stdout=subprocess.PIPE
        )
        _run(["tar", "-xf", "-", "-C", str(into_dir)], stdin=tar_proc.stdout)
        tar_proc.stdout.close()
        if tar_proc.wait() != 0:
            sys.exit(f"[seed] docker cp from {image} failed")
    finally:
        subprocess.run([*DOCKER, "rm", "-f", container_name], capture_output=True)

    exe = into_dir / "executable"
    # Separate the reference before the seed is committed; the runner sets mode 0111.
    if exe.exists():
        if bin_out is None:
            bin_out = into_dir.parent / "bin" / "executable"
        bin_out.parent.mkdir(parents=True, exist_ok=True)
        os.replace(exe, bin_out)
        print(f"[seed] moved reference binary OUT of repo → {bin_out} "
              f"(mounted 0111; never committed)")
    else:
        print("[seed] WARN: no /workspace/executable found in cleanroom image")

    import shutil
    dotgit = into_dir / ".git"
    if dotgit.exists():
        shutil.rmtree(dotgit, ignore_errors=True)
        print("[seed] stripped cleanroom .git (fresh history for the team)")

    print(f"[seed] repo seed (docs + assets + compile.sh, NO binary) ready at {into_dir}")
    return into_dir


def main(argv=None):
    ap = argparse.ArgumentParser(description="pbench_submission.py — ProgramBench submission export/feed pipeline.\n\nProgramBench's I/O contract (measured from ProgramBench/src/programbench/eval/eval.py\n+ container.py):\n\n  INPUT  (seed): the cleanroom image `programbench/<task>:task_cleanroom_v6`\n                 has under /workspace the reference binary (0111) + docs + compile.sh template.\n                 The agent team must, in its own Gitea repo, rebuild the codebase based on these materials.\n\n  OUTPUT (export): after the run, the agent team's Gitea repo HEAD = the full codebase\n                 (including compile.sh at the root). eval streams submission.tar.gz into the container via\n                 `tar -xzf - -C /workspace`, then runs `./compile.sh` to produce\n                 ./executable. So the submission has hard constraints:\n                   * the tar root is the workspace content (compile.sh at the root, no nested subdirectory)\n                   * .git is not included in the tar (eval seeds a deterministic git itself)\n                   * only include committed source (git archive), do not include untracked build artifacts\n                 Written to: <run>/<task_id>/submission.tar.gz\n\nTwo subcommands:\n  export  --from-dir <repo> | --from-gitea <url> --task <id> --out-dir <run>\n  seed    --image <task_cleanroom_img> --into <gitea_repo_path>   (reference binary is separated from the repository)\n\nThis tool only does pure git/tar/docker moving, with no network side effects (unless explicit --from-gitea\nclone or seed exporting from image).\n",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    ex = sub.add_parser("export", help="repo HEAD → <run>/<task>/submission.tar.gz")
    src = ex.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-dir", type=Path, help="local git working tree")
    src.add_argument("--from-gitea", help="Gitea clone URL (may embed creds)")
    ex.add_argument("--task", required=True, help="ProgramBench task/instance id")
    ex.add_argument("--out-dir", type=Path, required=True, help="run output dir")
    ex.add_argument("--ref", default="HEAD", help="branch/ref to export (gitea)")

    sd = sub.add_parser("seed", help="cleanroom image /workspace → local dir")
    sd.add_argument("--image", required=True, help="task_cleanroom_v6 Docker image or resolved image ID")
    sd.add_argument("--into", type=Path, required=True, help="dir to populate")
    sd.add_argument("--bin-out", type=Path, default=None,
                    help="where to move the reference binary (default: <into>/../bin/executable)")

    args = ap.parse_args(argv)
    if args.cmd == "export":
        if args.from_dir:
            export_from_dir(args.from_dir, args.task, args.out_dir)
        else:
            export_from_gitea(args.from_gitea, args.task, args.out_dir, args.ref)
    elif args.cmd == "seed":
        seed_from_image(args.image, args.into, args.bin_out)


if __name__ == "__main__":
    main()
