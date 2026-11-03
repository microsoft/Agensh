# Backlog synchronization for packs with [coordination] backlog = "issues": Gitea
# issues say what, board claims say who. A live CLAIM that cites #<number> makes
# its author an assignee of that issue; when the claim expires the assignment it
# made is removed. Closed issues keep their assignees as the record of who did the
# work. Synchronization is one-way: the board is the source of truth.

import re

ISSUE_REFERENCE = re.compile(r'(?<![\w/])#(\d+)\b')


def live_claims(entries, workers, now):
    """{issue number: {worker, ...}} for unexpired CLAIM entries by team workers."""
    claims = {}
    for entry in entries or []:
        if entry.get('type') != 'CLAIM' or entry.get('thread_id') not in workers:
            continue
        expires = entry.get('_expires_at')
        if expires is not None and float(expires) <= now:
            continue
        for number in ISSUE_REFERENCE.findall(str(entry.get('content', ''))):
            claims.setdefault(int(number), set()).add(entry['thread_id'])
    return claims


class Assignments:
    """Remembers which assignees the driver added, so it never removes anyone else's."""

    def __init__(self):
        self.managed = {}

    def issues(self, claims):
        return sorted(set(claims) | set(self.managed))

    def update(self, number, claims, current, state):
        """The assignee list issue `number` should have, or None to leave it alone."""
        wanted = claims.get(number, set())
        if state == 'closed':
            self.managed.pop(number, None)
            return None
        stale = self.managed.get(number, set()) - wanted
        desired = (set(current) - stale) | wanted
        if wanted:
            self.managed[number] = set(wanted)
        else:
            self.managed.pop(number, None)
        return sorted(desired) if desired != set(current) else None
