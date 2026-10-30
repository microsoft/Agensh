// Characterize how large group-chat batches are saved and summarized.
// Run with `npm test`, which builds dist/ first.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { groupMessagePayloads, isGroupMessage } from "../dist/group_messages.js";

function row(id, kind, message, extra = {}) {
  return {
    id,
    payload: {
      event_id: `e${id}`, source: "mattermost", target_agent: "org-worker1", kind,
      summary: `sender: ${message}`, observed_at: id,
      raw: { data: { post: JSON.stringify({ id: `p${id}`, message }), ...extra } },
    },
  };
}

async function withDirectory(fn) {
  const directory = await mkdtemp(join(tmpdir(), "group-messages-"));
  try {
    return await fn(directory);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

test("group message classification", () => {
  assert.equal(isGroupMessage(row(1, "post", "x").payload), true);
  assert.equal(isGroupMessage(row(1, "group", "x").payload), true);
  assert.equal(isGroupMessage(row(1, "dm", "x").payload), false);
  assert.equal(isGroupMessage(row(1, "post_edited", "x", { channel_type: "O" }).payload), true);
  assert.equal(isGroupMessage(row(1, "post_deleted", "x", { channel_type: "D" }).payload), false);
  assert.equal(isGroupMessage({ ...row(1, "post", "x").payload, source: "gitea" }), false);
});

test("batches with at most 32 group messages pass through unchanged", async () => {
  await withDirectory(async (directory) => {
    const batch = Array.from({ length: 32 }, (_, i) => row(i + 1, "post", `m${i}`));
    batch.push(row(100, "dm", "direct"));
    const payloads = await groupMessagePayloads(batch, directory, "org-worker1");
    assert.deepEqual(payloads, batch.map((r) => r.payload));
    assert.deepEqual(await readdir(directory), []);
  });
});

test("larger batches keep the latest 32 inline and save every group message", async () => {
  await withDirectory(async (directory) => {
    const batch = [row(1, "dm", "direct first")];
    for (let i = 2; i <= 41; i += 1) {
      const text = i === 2 ? "ping @org-worker1 and @org-worker10" : i === 3 ? "@Org-Worker1, again" : `m${i}`;
      batch.push(row(i, "post", text));
    }
    const payloads = await groupMessagePayloads(batch, join(directory, "nested"), "@org-worker1");

    const [notice, ...rest] = payloads;
    assert.equal(notice.kind, "group_message_history");
    assert.equal(notice.source, "system");
    assert.equal(notice.target_agent, "org-worker1");
    assert.equal(notice.raw.total, 40);
    assert.equal(notice.raw.earlier, 8);
    assert.equal(notice.raw.mentions, 2);
    assert.match(notice.summary, /^Showing the latest 32 group-chat messages\. 8 earlier messages are saved in /);
    assert.match(notice.summary, /Search the file for "@org-worker1"/);

    assert.deepEqual(rest.map((p) => p.event_id), ["e1", ...Array.from({ length: 32 }, (_, i) => `e${i + 10}`)]);

    const lines = (await readFile(notice.raw.path, "utf8")).trimEnd().split("\n").map((l) => JSON.parse(l));
    assert.equal(lines.length, 40);
    assert.equal(lines[0].id, 2);
    assert.equal(lines[0].message, "ping @org-worker1 and @org-worker10");
    assert.deepEqual(await readdir(join(directory, "nested")), [notice.raw.path.split("/").pop()]);
  });
});

test("the saved file name is stable for the same batch", async () => {
  await withDirectory(async (directory) => {
    const batch = Array.from({ length: 33 }, (_, i) => row(i + 1, "post", "x"));
    const first = await groupMessagePayloads(batch, directory, "a");
    const second = await groupMessagePayloads(batch, directory, "a");
    assert.equal(first[0].raw.path, second[0].raw.path);
    assert.equal(first[0].event_id, second[0].event_id);
  });
});
