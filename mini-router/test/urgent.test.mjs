// The product owner's DMs and @mentions of the worker are marked urgent, so the
// board service delivers them mid-turn. Run with `npm test`, which builds dist/ first.
import { test } from "node:test";
import assert from "node:assert/strict";

import { markUrgentFromHuman, mattermostEventToUEM, mentions } from "../dist/listeners/mattermost/notification.js";

function posted(sender, message, channelType = "P") {
  return {
    event: "posted",
    data: { post: JSON.stringify({ id: "p1", message, edit_at: 0 }), sender_name: `@${sender}`,
            channel_type: channelType, channel_name: "team-task" },
    broadcast: {}, seq: 1,
  };
}

function mark(ev, human = "owner") {
  return markUrgentFromHuman(mattermostEventToUEM(ev, "team-worker1", 1), ev, human);
}

test("the product owner's DM and mention are urgent", () => {
  const dm = mark(posted("owner", "please check the CLI flag", "D"));
  assert.equal(dm.urgent, true);
  assert.match(dm.summary, /^URGENT from the product owner: /);
  assert.equal(mark(posted("owner", "@team-worker1 use JSON lines")).urgent, true);
  assert.equal(mark(posted("Owner", "ping @TEAM-WORKER1.")).urgent, true);
});

test("other posts stay queued", () => {
  assert.equal(mark(posted("owner", "status update for everyone")).urgent, undefined);
  assert.equal(mark(posted("owner", "@team-worker10 only")).urgent, undefined);
  assert.equal(mark(posted("team-worker2", "@team-worker1 look", "D")).urgent, undefined);
  assert.equal(mark(posted("owner", "@team-worker1 hi"), "").urgent, undefined);
  const edited = { ...posted("owner", "@team-worker1 hi"), event: "post_edited" };
  assert.equal(markUrgentFromHuman(mattermostEventToUEM(edited, "team-worker1", 1), edited, "owner").urgent, undefined);
});

test("mentions need a word boundary", () => {
  assert.equal(mentions("cc @team-worker1, thanks", "team-worker1"), true);
  assert.equal(mentions("mail x@team-worker1", "team-worker1"), false);
  assert.equal(mentions("@team-worker1-bot", "team-worker1"), false);
});
