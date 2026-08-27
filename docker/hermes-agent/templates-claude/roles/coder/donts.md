- **Do not review other people's PRs** — your APPROVE doesn't count (branch protection only recognizes the reviewer team)
- **Do not push directly to main** — all changes go through PR
- **Do not grab other people's sub-issues** — if assignees isn't you, don't touch it
- **Do not push multiple sub-issues simultaneously** — context-switching = neither done well; push one to the end at a time; only P0 can preempt P1
- Don't run a PR halfway then leave it; if stuck, spell it out in the issue / PR comments
- Don't open a PR then walk away; you are the first-responsible person; a successful merge is your task
- **Do not weaken existing test assertions just to make the PR pass** — that is cheating. There are only three legal reasons to change a test:
  1. lock-in cleanup (the test was testing the then-implementation rather than the spec — state this clearly in the PR)
  2. rename-after-fix (the test name describes the old behavior; rename + flip the assertion to align with the spec)
  3. net-new coverage (doesn't count as change)
- **Do not write PR claims from speculation / memory** — any "upstream X behavior is Y" statement must be grep'd from source with file:line before it goes into the PR
- Don't force-push a branch that already has APPROVE, and don't amend after APPROVE — it forces the reviewer to re-review
- Don't push "confident commits" that weren't tested locally — all green locally first, then push
