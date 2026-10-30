// Characterize turn delivery: shown-row reconciliation, acknowledgement, retry
// marking, board context and serialization. Run with `npm test`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { Dispatcher } from "../dist/dispatcher.js";

function row(id) {
  return { id, payload: { event_id: `e${id}`, source: "gitea", target_agent: "a", kind: "pull", summary: "s", observed_at: 0, raw: null } };
}

function fakeState({ batch = [], shown = [], claimed, failSent = 0 } = {}) {
  const calls = [];
  let sentFailures = failSent;
  return {
    calls,
    async nextPendingBatch(agent, limit) { calls.push(["next", agent, limit]); return batch; },
    async claimShown(agent, ids) { calls.push(["claimShown", ids]); return new Set(shown); },
    async markBatchSending(ids) { calls.push(["sending", ids]); return claimed ?? ids.length; },
    async markBatchSent() {
      calls.push(["sent"]);
      if (sentFailures > 0) { sentFailures -= 1; throw new Error("db down"); }
    },
    async markFailed(id, msg) { calls.push(["failed", id, msg]); },
  };
}

function fakeChannel({ fail = false, gate } = {}) {
  const calls = [];
  return {
    calls,
    async prompt(payloads) {
      calls.push(["prompt", payloads.map((p) => p.event_id)]);
      if (gate) await gate();
      if (fail) throw new Error("acp closed");
      return { stopReason: "end_turn" };
    },
    async promptText(text) { calls.push(["promptText", text]); return { stopReason: "end_turn" }; },
    setPromptPrefix(prefix) { calls.push(["prefix", prefix]); },
  };
}

function fakeBoard({ enabled = false, gists = [] } = {}) {
  const ids = [...gists];
  return {
    enabled,
    async renderForPrompt() { return "==== SHARED CONTEXT ===="; },
    async latestOwnGistId() { return ids.length ? ids.shift() : null; },
    buildForcedWriteNudge() { return "please publish"; },
  };
}

async function dispatcher(options) {
  const directory = await mkdtemp(join(tmpdir(), "dispatcher-"));
  const logs = [];
  const instance = new Dispatcher({
    agent: "a", groupMessageDirectory: directory, onLog: (entry) => logs.push(entry),
    board: fakeBoard(), ...options,
  });
  return { instance, logs, cleanup: () => rm(directory, { recursive: true, force: true }) };
}

test("an empty queue dispatches nothing", async () => {
  const state = fakeState();
  const channel = fakeChannel();
  const { instance, cleanup } = await dispatcher({ state, channel });
  assert.deepEqual(await instance.tick(), { dispatched: 0 });
  assert.deepEqual(state.calls, [["next", "a", 32]]);
  assert.deepEqual(channel.calls, []);
  await cleanup();
});

test("a batch is prompted and then acknowledged", async () => {
  const state = fakeState({ batch: [row(1), row(2)] });
  const channel = fakeChannel();
  const { instance, cleanup } = await dispatcher({ state, channel });
  assert.deepEqual(await instance.tick(), { dispatched: 2 });
  assert.deepEqual(channel.calls, [["prompt", ["e1", "e2"]]]);
  assert.deepEqual(state.calls.map((c) => c[0]), ["next", "claimShown", "sending", "sent"]);
  await cleanup();
});

test("rows already shown mid-turn are retired, not prompted again", async () => {
  const state = fakeState({ batch: [row(1), row(2)], shown: [1] });
  const channel = fakeChannel();
  const { instance, cleanup } = await dispatcher({ state, channel });
  assert.deepEqual(await instance.tick(), { dispatched: 1 });
  assert.deepEqual(channel.calls, [["prompt", ["e2"]]]);

  const allShown = fakeState({ batch: [row(3)], shown: [3] });
  const quiet = fakeChannel();
  const second = await dispatcher({ state: allShown, channel: quiet });
  assert.deepEqual(await second.instance.tick(), { dispatched: 0 });
  assert.deepEqual(quiet.calls, []);
  await cleanup();
  await second.cleanup();
});

test("a batch claimed by another dispatcher is skipped", async () => {
  const state = fakeState({ batch: [row(1)], claimed: 0 });
  const channel = fakeChannel();
  const { instance, cleanup } = await dispatcher({ state, channel });
  await instance.tick();
  assert.deepEqual(channel.calls, []);
  await cleanup();
});

test("a failed prompt marks every row failed and does not acknowledge", async () => {
  const state = fakeState({ batch: [row(1), row(2)] });
  const channel = fakeChannel({ fail: true });
  const { instance, logs, cleanup } = await dispatcher({ state, channel });
  await instance.tick();
  assert.deepEqual(state.calls.filter((c) => c[0] === "failed"), [["failed", 1, "acp closed"], ["failed", 2, "acp closed"]]);
  assert.equal(state.calls.some((c) => c[0] === "sent"), false);
  assert.match(logs.at(-1).msg, /^acp prompt failed \(2 events\)/);
  await cleanup();
});

test("a bookkeeping failure after delivery never re-queues the turn", async () => {
  const state = fakeState({ batch: [row(1)], failSent: 1 });
  const channel = fakeChannel();
  const { instance, logs, cleanup } = await dispatcher({ state, channel });
  await instance.tick();
  assert.deepEqual(state.calls.filter((c) => c[0] === "sent").length, 2);
  assert.equal(state.calls.some((c) => c[0] === "failed"), false);
  assert.match(logs.at(-1).msg, /^post-delivery step failed/);
  await cleanup();
});

test("board context is set before the prompt and a silent turn is nudged", async () => {
  const state = fakeState({ batch: [row(1)] });
  const channel = fakeChannel();
  const { instance, cleanup } = await dispatcher({ state, channel, board: fakeBoard({ enabled: true, gists: [5, 5] }) });
  await instance.tick();
  assert.deepEqual(channel.calls, [
    ["prefix", "==== SHARED CONTEXT ===="],
    ["prompt", ["e1"]],
    ["prefix", null],
    ["promptText", "please publish"],
  ]);
  await cleanup();
});

test("a turn that published a gist is not nudged", async () => {
  const state = fakeState({ batch: [row(1)] });
  const channel = fakeChannel();
  const { instance, cleanup } = await dispatcher({ state, channel, board: fakeBoard({ enabled: true, gists: [5, 6] }) });
  await instance.tick();
  assert.equal(channel.calls.some((c) => c[0] === "promptText"), false);
  await cleanup();
});

test("ticks never prompt the session concurrently", async () => {
  let active = 0;
  let maxActive = 0;
  const gate = async () => {
    active += 1;
    maxActive = Math.max(maxActive, active);
    await new Promise((resolve) => setTimeout(resolve, 20));
    active -= 1;
  };
  const state = fakeState({ batch: [row(1)] });
  const channel = fakeChannel({ gate });
  const { instance, cleanup } = await dispatcher({ state, channel });
  await Promise.all([instance.tick(), instance.tick(), instance.dispatchSpecific([row(2)])]);
  assert.equal(channel.calls.length, 3);
  assert.equal(maxActive, 1);
  await cleanup();
});
