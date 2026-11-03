ProgramBench task: ${TASK}

You are a single autonomous engineer. You are given a reference program as a
compiled binary at `/opt/pbench/executable` — you can RUN it to observe its
behavior, but you CANNOT read its bytes (and must not try to). Its documentation
is in the current workspace (/workspace).

Goal: write an ORIGINAL codebase from scratch (in /workspace) that builds an
`./executable` reproducing the reference program's behavior exactly.

Hard requirements:
- Put a working `./compile.sh` at the workspace ROOT that builds `./executable`.
  compile.sh must install any build deps and produce ./executable on a fresh checkout.
- Add the built `executable` (and other build artifacts) to `.gitignore` — do NOT
  commit artifacts.
- Commit all your SOURCE to git in /workspace. Your submission is `git archive HEAD`,
  so anything not committed is lost.
- You have NO internet access. Do not attempt to fetch the original source.
- This is FULLY autonomous: there is NO human to ask. Decide and ship by yourself.

Recommended workflow:
1. Read all documentation in /workspace.
2. Run `/opt/pbench/executable` with many inputs/flags to learn its behavior.
3. Implement the source, write compile.sh, build, and test against the reference.

Wall-clock budget: ${HOURS}h. First step: run `/opt/pbench/executable` and observe.
