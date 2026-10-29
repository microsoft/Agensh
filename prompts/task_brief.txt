ProgramBench task: ${TASK}

You are given a reference program as a compiled binary at `/opt/pbench/executable`
(you can RUN it to observe behavior, but you CANNOT read its bytes) plus its
documentation in this repo. Rebuild a complete codebase that reproduces the
program's behavior.

Requirements:
- Put a working `compile.sh` at the repo ROOT that builds `./executable`.
- Commit all source to the `${REPO}` repo's default branch.
- You have NO internet access. Do not attempt to fetch the original source.
- This is FULLY autonomous: there is NO human to ask. Define requirements,
  split the work, decide, and ship by yourselves. Do not wait for instructions.

First step: run `/opt/pbench/executable` and observe.

Mattermost coordination: your team is `${MM_TEAM_ID}` and the shared task
channel `pbench-task` is `${TASK_CHANNEL_ID}`. Pass those ids straight to the
mattermost tools — do not guess them and do not go looking them up. If a
mattermost call returns 403 or 404 you have used a wrong id, not lost access:
you are a member of that team and that channel.
