// Characterize listener normalization, cursors and prompt rendering.
// Run with `npm test`, which builds dist/ first.
import { test } from "node:test";
import assert from "node:assert/strict";

import { giteaNotificationToUEM } from "../dist/listeners/gitea/notification.js";
import { advanceCursor } from "../dist/listeners/gitea/fetcher.js";
import {
  isSelfAuthored,
  isSystemPost,
  mattermostEventToUEM,
} from "../dist/listeners/mattermost/notification.js";
import { parseBoardIds } from "../dist/board_client.js";
import { defaultRenderBatch, defaultRenderUEM, runAge } from "../dist/uem_render.js";

function post(fields) {
  return JSON.stringify({ id: "p1", create_at: 1, edit_at: 0, user_id: "u1", channel_id: "c1", message: "hi", ...fields });
}

function wsEvent(event, data = {}, seq = 9) {
  return { event, data, broadcast: { channel_id: "bc" }, seq };
}

test("gitea notification keeps a revision-specific id and issue number", () => {
  const uem = giteaNotificationToUEM({
    id: 4,
    updated_at: "2026-01-01T00:00:00Z",
    subject: { title: "Fix parser", type: "Pull", url: "http://gitea:3000/api/v1/repos/o/r/pulls/12" },
    repository: { full_name: "o/r" },
  }, "o-worker1", 123);
  assert.equal(uem.event_id, "gitea:notif:4:2026-01-01T00:00:00Z");
  assert.equal(uem.kind, "pull");
  assert.equal(uem.summary, "o/r pull #12: Fix parser");
  assert.equal(uem.target_agent, "o-worker1");
  assert.equal(uem.observed_at, 123);
});

test("gitea notification falls back when fields are missing", () => {
  const uem = giteaNotificationToUEM({ id: 5, updated_at: "t" }, "a", 0);
  assert.equal(uem.summary, "? unknown: (no title)");
  const html = giteaNotificationToUEM({ id: 6, updated_at: "t", subject: { html_url: "http://x/issues/3#c" } }, "a", 0);
  assert.match(html.summary, / #3: /);
});

test("notification cursor only moves forward", () => {
  assert.equal(advanceCursor(null, { items: [], maxUpdatedAt: null }), null);
  assert.equal(advanceCursor("b", { items: [], maxUpdatedAt: null }), "b");
  assert.equal(advanceCursor(null, { items: [], maxUpdatedAt: "a" }), "a");
  assert.equal(advanceCursor("b", { items: [], maxUpdatedAt: "a" }), "b");
  assert.equal(advanceCursor("b", { items: [], maxUpdatedAt: "c" }), "c");
});

test("mattermost posts are classified by channel type", () => {
  const kinds = { D: "dm", G: "group", O: "post", P: "post", undefined: "post" };
  for (const [channelType, kind] of Object.entries(kinds)) {
    const data = { post: post({}), sender_name: "@alice" };
    if (channelType !== "undefined") data.channel_type = channelType;
    assert.equal(mattermostEventToUEM(wsEvent("posted", data), "a", 0).kind, kind, channelType);
  }
  assert.equal(mattermostEventToUEM(wsEvent("post_edited", { post: post({}) }), "a", 0).kind, "post_edited");
});

test("DM bodies stay whole; channel bodies are capped at 200 characters", () => {
  const long = "word ".repeat(100);
  const dm = mattermostEventToUEM(wsEvent("posted", { post: post({ message: long }), channel_type: "D", sender_name: "@alice" }), "a", 0);
  assert.equal(dm.summary, `@alice in DM: ${long.trim()}`);
  const channel = mattermostEventToUEM(wsEvent("posted", {
    post: post({ message: long }), channel_type: "O", channel_display_name: "team", sender_name: "@bob",
  }), "a", 0);
  const body = channel.summary.slice("@bob in #team: ".length);
  assert.equal(body.length, 200);
  assert.ok(body.endsWith("…"));
});

test("mattermost summaries normalize whitespace and label channels", () => {
  const uem = mattermostEventToUEM(wsEvent("posted", { post: post({ message: " a\n\n b " }), channel_name: "dev" }), "a", 0);
  assert.equal(uem.summary, "u1 in #dev: a b");
  const fallback = mattermostEventToUEM(wsEvent("posted", { post: post({ channel_id: "" }) }), "a", 0);
  assert.equal(fallback.summary, "u1 in #bc: hi");
});

test("mattermost event ids distinguish edits and deletions", () => {
  assert.equal(mattermostEventToUEM(wsEvent("posted", { post: post({}) }), "a", 0).event_id, "mattermost:post:p1:0");
  assert.equal(mattermostEventToUEM(wsEvent("post_edited", { post: post({ edit_at: 7 }) }), "a", 0).event_id,
    "mattermost:post:p1:7");
  assert.equal(mattermostEventToUEM(wsEvent("post_deleted", { post: post({}) }), "a", 0).event_id,
    "mattermost:post_deleted:p1");
});

test("malformed posts and reactions are reported, not dropped", () => {
  const bad = mattermostEventToUEM(wsEvent("posted", { post: "{not json" }, 3), "a", 0);
  assert.equal(bad.event_id, "mattermost:post:seq-3:0");
  assert.match(bad.summary, /\(malformed post payload\)$/);
  const reaction = mattermostEventToUEM(wsEvent("reaction_added", {
    reaction: JSON.stringify({ user_id: "u2", post_id: "p1", emoji_name: "tada", create_at: 5 }),
  }), "a", 0);
  assert.equal(reaction.kind, "reaction_added");
  assert.equal(reaction.summary, "u2 reacted :tada: on post p1");
  assert.equal(reaction.event_id, "mattermost:reaction_added:p1:u2:tada:5");
  const broken = mattermostEventToUEM(wsEvent("reaction_removed", { reaction: "x" }, 4), "a", 0);
  assert.equal(broken.summary, "unreacted (unknown) (malformed reaction payload)");
  assert.equal(broken.event_id, "mattermost:reaction_removed:seq-4:?:?:seq-4");
});

test("self-authored and system posts are recognized", () => {
  assert.equal(isSelfAuthored(wsEvent("posted", { sender_name: "@Org-Worker1" }), "org-worker1"), true);
  assert.equal(isSelfAuthored(wsEvent("posted", { sender_name: "@org-worker10" }), "org-worker1"), false);
  assert.equal(isSelfAuthored(wsEvent("posted", { post: post({ user_id: "me" }) }), "me"), true);
  assert.equal(isSelfAuthored(wsEvent("posted", {}), "me"), false);
  assert.equal(isSelfAuthored(wsEvent("posted", { sender_name: "x" }), ""), false);
  assert.equal(isSystemPost(wsEvent("posted", { post: post({ type: "system_join_channel" }) })), true);
  assert.equal(isSystemPost(wsEvent("posted", { post: post({}) })), false);
  assert.equal(isSystemPost(wsEvent("posted", { post: "{bad" })), false);
});

test("board ids are split and trimmed", () => {
  assert.deepEqual(parseBoardIds(" a, ,b ,"), ["a", "b"]);
  assert.deepEqual(parseBoardIds(undefined), []);
});

test("event rendering uses the shared run start", () => {
  process.env.AGENSH_RUN_START_MS = "1000";
  try {
    assert.equal(runAge(1000 + 90_000), "+1.5m");
    assert.equal(runAge(0), "+0.0m");
    const uem = { event_id: "e1", source: "gitea", target_agent: "a", kind: "pull", summary: "s", observed_at: 61_000, raw: null };
    assert.equal(defaultRenderUEM(uem),
      "[event]\nevent_id=e1\nsource=gitea\nkind=pull\nobserved_at=+1.0m\nsummary: s");
    assert.equal(defaultRenderBatch([uem]), defaultRenderUEM(uem));
    const batch = defaultRenderBatch([uem, { ...uem, event_id: "e2" }]).split("\n");
    assert.equal(batch[0], "[event-batch] 2 events");
    assert.equal(batch[2], "--- event 1/2 ---");
    assert.ok(batch.includes("--- event 2/2 ---"));
  } finally {
    delete process.env.AGENSH_RUN_START_MS;
  }
});
