## Common causes of merge failure + handling

- `head branch is behind the base branch` → call Gitea API `/repos/{owner}/{repo}/pulls/{n}/update` to sync the PR to the latest main, then retry merge
- `Not all required status checks successful` → CI is still running, wait a few seconds and retry
- Repeated same race (updated then someone else merged first) → write a small loop of update + wait for status + merge

## Common problems while working

- Can't do it / requirements are vague → @ the lead on the sub-issue to ask clearly; don't just wing it
- Reviewer REQUEST_CHANGES but you disagree → argue it out on the PR with reasons; don't silently change and don't stubbornly refuse
- Tests won't pass → fix the test first, then push; don't bypass tests
- Lead said "small adjustment / quick triage" and 10 minutes in you still have no clue → report the current state as options (A/B/C + which I lean toward); don't hold on trying to force it and blow the budget
- After receiving a sub-issue you find it needs cross-module changes, contract changes, or exceeds budget → stop, and on the issue give the lead a one-line diagnosis + options for him to decide

## What to do about your own mistakes

- You find a PR you previously merged is wrong → self-revert immediately; don't "fix next time". Transparent self-correction reputation is accumulated; a single hide destroys it
- Your estimate / claim gets punched in the face by real tests → explicitly retract on the original thread / channel, saying which assumption was wrong; don't quietly change it
- Data / test results fall short of expectations → report to the lead in the original words; don't dress it up; the team's data credibility is more important than a pretty report
