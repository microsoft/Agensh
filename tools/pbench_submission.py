#!/usr/bin/env python3
"""pbench_submission.py — ProgramBench submission export/feed pipeline.

ProgramBench's I/O contract (measured from ProgramBench/src/programbench/eval/eval.py
+ container.py):

  INPUT  (seed): the cleanroom image `programbench/<task>:task_cleanroom`
                 has under /workspace the reference binary (0111) + docs + compile.sh template.
                 The agent team must, in its own Gitea repo, rebuild the codebase based on these materials.

  OUTPUT (export): after the run, the agent team's Gitea repo HEAD = the full codebase
                 (including compile.sh at the root). eval streams submission.tar.gz into the container via
                 `tar -xzf - -C /workspace`, then runs `./compile.sh` to produce
                 ./executable. So the submission has hard constraints:
                   * the tar root is the workspace content (compile.sh at the root, no nested subdirectory)
                   * .git is not included in the tar (eval seeds a deterministic git itself)
                   * only include committed source (git archive), do not include untracked build artifacts
                 Written to: <run>/<task_id>/submission.tar.gz

Two subcommands:
  export  --from-dir <repo> | --from-gitea <url> --task <id> --out-dir <run>
  seed    --image <task_cleanroom_img> --into <gitea_repo_path>   (placeholder, see below)

This tool only does pure git/tar/docker moving, with no network side effects (unless explicit --from-gitea
clone or seed exporting from image); all real pipelines are covered by real-container tests under tests/pbench/.
"""
import argparse
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


# docker may need sudo on hosts where the user isn't in the docker group.
# PBENCH_DOCKER lets the orchestrator inject e.g. "sudo docker".
DOCKER = os.environ.get("PBENCH_DOCKER", "docker").split()

# Never ship a pre-built binary. `compile.sh` is supposed to produce
# ./executable at eval time; a submission that already contains one can score
# without ever building, which makes the result meaningless — and we have
# already seen a task (ditaa) score 99% by repackaging the reference artifact.
#
# The role fragments tell agents not to do this, but a prompt is not an
# enforcement boundary: on the delm-1a run of 2026-07-27 the agent shipped
# ./executable anyway. Stripping here makes it structural.
BANNED_ROOT_ENTRIES = ("executable",)

# Last-resort build script, staged when a team wrote source but never produced
# a compile.sh. Same script the DeLM path stages into /work.
#
# The alternative — refusing to export — is strictly worse: on the method-2b
# run of 2026-07-27 the team had written cmd_import.c and a README, the
# exporter found no root compile.sh, aborted, and the caller fell back to
# shipping an EMPTY tarball. That converts "built something that does not
# compile" (recoverable, and informative) into a guaranteed 0 with the
# evidence destroyed. Staging a default keeps the failure honest: if the
# sources do not build, the build still fails and eval records it.
DEFAULT_COMPILE_SH = """#!/bin/sh
# Staged by the harness: the submission had no root-level compile.sh.
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
    """Add a default compile.sh to the tarball when the root lacks one.

    Returns True if one was staged. Never overwrites a compile.sh the team
    actually wrote.
    """
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
    """Remove banned entries from an already-written submission tarball.

    Rewrites through a temp file so a failure cannot leave a truncated
    submission behind.
    """
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
    """git archive HEAD of repo_dir → <out_dir>/<task>/submission.tar.gz.

    git archive guarantees the three hard constraints for free:
      - tree root = archive root (compile.sh lands at ./compile.sh)
      - .git is never included
      - only tracked (committed) files ship; untracked/gitignored junk drops
    """
    repo_dir = repo_dir.resolve()
    if not (repo_dir / ".git").exists():
        sys.exit(f"[export] {repo_dir} is not a git repo (no .git)")

    dest_dir = out_dir / task
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "submission.tar.gz"

    # `git archive --format=tar.gz HEAD` writes a flat-rooted gzip tar.
    with dest.open("wb") as f:
        _run(
            ["git", "-C", str(repo_dir), "archive", "--format=tar.gz", "HEAD"],
            stdout=f,
        )

    _strip_banned(dest)
    _ensure_compile_sh(dest)

    # Sanity: compile.sh must exist at the archive root, else eval can't build.
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


def export_from_workdir(work_dir: Path, task: str, out_dir: Path) -> Path:
    """tar the contents of a plain (non-git) directory as the submission.

    Used by the DeLM baseline path where agents write source files directly to
    a shared /work bind-mount instead of committing to a Gitea repo. Excludes
    common junk (.git, target/, __pycache__, node_modules, *.o, *.pyc) and
    requires compile.sh at the root.
    """
    work_dir = work_dir.resolve()
    if not work_dir.exists():
        sys.exit(f"[export] {work_dir} does not exist")
    # No hard exit on a missing compile.sh: _ensure_compile_sh() below stages a
    # default so the team's sources still get a build attempt. Bailing here
    # would ship an empty tarball and destroy the evidence — the same failure
    # already fixed on the gitea path.
    if not (work_dir / "compile.sh").exists():
        print(f"[export] WARNING: {work_dir}/compile.sh missing; a default will be staged")

    dest_dir = out_dir / task
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "submission.tar.gz"

    # Use tar with --transform to flatten "./x" → "x" and exclude build junk.
    _run(
        [
            "tar", "-C", str(work_dir), "--exclude=.git", "--exclude=target",
            "--exclude=__pycache__", "--exclude=node_modules",
            "--exclude=*.o", "--exclude=*.pyc",
            "-czf", str(dest), ".",
        ]
    )
    _strip_banned(dest)
    _ensure_compile_sh(dest)

    listing = subprocess.run(
        ["tar", "-tzf", str(dest)], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    roots = {p.lstrip("./").split("/", 1)[0] for p in listing if p.strip()}
    print(f"[export] wrote {dest} ({dest.stat().st_size} bytes); "
          f"root entries: {sorted(roots)[:12]}")
    return dest


def export_from_gitea(url: str, task: str, out_dir: Path, ref: str = "HEAD") -> Path:
    """Clone a Gitea repo (shallow) then export its HEAD as a submission.

    Used by `make pbench` after the agent team finishes: the team's repo lives
    in Gitea, we clone it to a temp dir and archive it. The clone URL may embed
    credentials (http://user:token@host/...); we don't log it.
    """
    with tempfile.TemporaryDirectory(prefix="pbench-clone-") as tmp:
        clone_dir = Path(tmp) / "repo"
        _run(["git", "clone", "--quiet", "--depth", "1", "--branch", ref, url, str(clone_dir)]) \
            if ref not in ("HEAD",) else \
            _run(["git", "clone", "--quiet", "--depth", "1", url, str(clone_dir)])
        return export_from_dir(clone_dir, task, out_dir)


def seed_from_image(image: str, into_dir: Path, bin_out: Path | None = None) -> Path:
    """Extract a cleanroom image's /workspace into a local dir for committing
    as the agent repo's initial state — WITHOUT leaking the reference binary.

    The cleanroom /workspace contains: docs (README, LICENSE), test assets,
    a compile.sh template, and the reference `executable` (root:root 0111 —
    runnable, not readable). ProgramBench's anti-cheat hinges on the agent
    being able to RUN that binary but never READ its bytes.

    Therefore this function SEPARATES the binary from the repo:
      - `executable` is moved to `bin_out` (default: into_dir/../bin/executable),
        which the compose mounts root:root 0111 at /opt/pbench/executable. It
        MUST NOT be committed to git (a git blob is world-readable → cheat).
      - `.git` from the cleanroom is stripped (the agent team starts a fresh
        history; eval seeds its own deterministic git at eval time anyway).
    Everything else (docs + assets + compile.sh) is what gets committed.
    """
    into_dir.mkdir(parents=True, exist_ok=True)
    # Create a throwaway container and tar /workspace out of it.
    cid = subprocess.run(
        [*DOCKER, "create", image], capture_output=True, text=True, check=True
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
        subprocess.run([*DOCKER, "rm", "-f", cid], capture_output=True)

    # --- anti-cheat: pull the reference binary OUT of the repo tree ---------
    exe = into_dir / "executable"
    if exe.exists():
        if bin_out is None:
            bin_out = into_dir.parent / "bin" / "executable"
        bin_out.parent.mkdir(parents=True, exist_ok=True)
        # Move preserving bytes; perms get re-applied root:root 0111 at mount.
        os.replace(exe, bin_out)
        print(f"[seed] moved reference binary OUT of repo → {bin_out} "
              f"(mounted 0111; never committed)")
    else:
        print("[seed] WARN: no /workspace/executable found in cleanroom image")

    # --- strip the cleanroom .git (no upstream history leaks into the repo) -
    import shutil
    dotgit = into_dir / ".git"
    if dotgit.exists():
        shutil.rmtree(dotgit, ignore_errors=True)
        print("[seed] stripped cleanroom .git (fresh history for the team)")

    print(f"[seed] repo seed (docs + assets + compile.sh, NO binary) ready at {into_dir}")
    return into_dir


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    ex = sub.add_parser("export", help="repo HEAD → <run>/<task>/submission.tar.gz")
    src = ex.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-dir", type=Path, help="local git working tree")
    src.add_argument("--from-gitea", help="Gitea clone URL (may embed creds)")
    src.add_argument("--from-workdir", type=Path,
                     help="plain (non-git) directory; tar it directly (DeLM baseline path)")
    ex.add_argument("--task", required=True, help="ProgramBench task/instance id")
    ex.add_argument("--out-dir", type=Path, required=True, help="run output dir")
    ex.add_argument("--ref", default="HEAD", help="branch/ref to export (gitea)")

    sd = sub.add_parser("seed", help="cleanroom image /workspace → local dir")
    sd.add_argument("--image", required=True, help="task_cleanroom docker image")
    sd.add_argument("--into", type=Path, required=True, help="dir to populate")
    sd.add_argument("--bin-out", type=Path, default=None,
                    help="where to move the reference binary (default: <into>/../bin/executable)")

    args = ap.parse_args(argv)
    if args.cmd == "export":
        if args.from_dir:
            export_from_dir(args.from_dir, args.task, args.out_dir)
        elif args.from_workdir:
            export_from_workdir(args.from_workdir, args.task, args.out_dir)
        else:
            export_from_gitea(args.from_gitea, args.task, args.out_dir, args.ref)
    elif args.cmd == "seed":
        seed_from_image(args.image, args.into, args.bin_out)


if __name__ == "__main__":
    main()
