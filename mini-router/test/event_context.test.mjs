// Inline event context (EVENT_CONTEXT=inline): Gitea events carry the latest comment's
// author and opening text, spilling long text behind its API path; Mattermost replies
// name their thread and how it started. Run with `npm test`, which builds dist/ first.
import { test } from "node:test";
import assert from "node:assert/strict";

import { detailPath, excerpt, toDetail, withDetail } from "../dist/listeners/gitea/context.js";
import { mattermostEventToUEM, withThreadContext } from "../dist/listeners/mattermost/notification.js";

const ROOT = "http://gitea.localhost:23000/api/v1/repos/team/main";

test("the latest comment is preferred over the subject", () => {
  const n = { id: 1, updated_at: "t", subject: { url: `${ROOT}/pulls/12`, latest_comment_url: `${ROOT}/issues/comments/345` } };
  assert.deepEqual(detailPath(n), { path: "/api/v1/repos/team/main/issues/comments/345", isComment: true });
  const opened = { id: 2, updated_at: "t", subject: { url: `${ROOT}/issues/7`, latest_comment_url: `${ROOT}/issues/7` } };
  assert.deepEqual(detailPath(opened), { path: "/api/v1/repos/team/main/issues/7", isComment: false });
  assert.equal(detailPath({ id: 3, updated_at: "t", subject: {} }), null);
});

test("short comments are inlined whole", () => {
  const detail = toDetail({ id: 345, user: { login: "team-worker2" }, body: "LGTM,\n merging" },
    "/api/v1/repos/team/main/issues/comments/345", true);
  assert.equal(withDetail("team/main pull #12: Add --json", detail),
    'team/main pull #12: Add --json — latest comment by @team-worker2: "LGTM, merging" [comment 345]');
});

test("long text spills behind its API path", () => {
  const detail = toDetail({ user: { login: "owner" }, body: "x".repeat(500) }, "/api/v1/repos/team/main/issues/7", false);
  const summary = withDetail("team/main issue #7: Sorting", detail);
  assert.match(summary, /^team\/main issue #7: Sorting — by @owner: "x{199}…" \(full text: GET \/api\/v1\/repos\/team\/main\/issues\/7\)$/);
  assert.deepEqual(excerpt("a  b\n c", 10), { text: "a b c", truncated: false });
  assert.equal(withDetail("s", null), "s");
});

function posted(message, extra = {}) {
  return {
    event: "posted",
    data: { post: JSON.stringify({ id: "p2", message, edit_at: 0, ...extra }), sender_name: "@team-worker2",
            channel_type: "P", channel_name: "team-task" },
    broadcast: {}, seq: 1,
  };
}

test("a reply names its thread and how it started", () => {
  const ev = posted("I can take the sorting part", { root_id: "p1" });
  const uem = withThreadContext(mattermostEventToUEM(ev, "team-worker1", 1), ev,
    { author: "owner", message: "Who picks up --sort?" });
  assert.equal(uem.summary, '@team-worker2 in #team-task: I can take the sorting part '
    + '(reply in the thread of post p1, started by owner: "Who picks up --sort?")');
});

test("root posts stay as they are; long ones name their post", () => {
  const short = posted("plain status");
  assert.equal(withThreadContext(mattermostEventToUEM(short, "team-worker1", 1), short, null).summary,
    "@team-worker2 in #team-task: plain status");
  const long = posted("y".repeat(300));
  assert.match(withThreadContext(mattermostEventToUEM(long, "team-worker1", 1), long, null).summary,
    /\(post p2; read the rest of it in Mattermost\)$/);
});
