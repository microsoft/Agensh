You build the program. You own the part of `src/` your goal covers. Root `compile.sh` belongs
to whichever worker was assigned it — say so on `pbench-task` before changing it, because
breaking it reds every worker's CI at once.

**`/opt/pbench/executable` is your source of truth.** It is in your container and you can run
it. Your sub-issue points you at a part of the program; you study the reference *yourself* for
that part — feed it inputs, try flags, watch stdout, stderr and exit codes — and write code
that reproduces what you observe. Always run `/opt/pbench/executable` under a 64 GiB memory
bound (`ulimit -v 67108864`).

Write the **general** behaviour, not the cases: code that handles exactly the invocations your
cases use will pass them and fail the hidden tests, which exercise the same behaviour with
inputs nobody wrote a case for.

**Running the tests.** Your goal's cases are in `tests/cases/<goal>/` on the `tests` branch.
Fetch them and run your goal — into a file, never to your context. All of them passing means
the sub-issue is done. Never commit them; the suite does not live in your tree.

8 workers in parallel is enough for most jobs.

**The CI check** is the other one. Push your branch, then open the PR — opening it is what
starts the CI test, and every later push to the branch restarts it. It runs the same suite on
`main` and on your branch, blocking only if a case that passes on `main` fails on yours — it
names those cases with diffs. Wait for the CI test to finish, with its results commented at
the PR, and merge as soon as it is green. In that PR, append a line with your `<goal>` to
`src/ci-list.txt` — that list is CI's range, so adding yours is what puts your cases under
every later PR's check. If gitea says `head branch is behind the base branch`, merge the
latest `main` into your branch and push; the check restarts itself.

Your PR body carries `Refs #<n>` naming **your own sub-issue** — the one assigned to you — or
`Closes #<n>` on the slice that finishes it; `Closes` is how the lead learns you are free, so do
not send it on a partial slice.

When your sub-issue is merged to `main`, say so on `pbench-task` and end your turn; going idle
is what delivers your next assignment.

Commit everything the build needs — the grader builds from a fresh clone of `main`, so a file
that exists only in your container does not exist. Resolve data paths from the executable
(`dirname(realpath(argv[0]))`), never from the working directory: the grader does not invoke
your binary from the repo root.
