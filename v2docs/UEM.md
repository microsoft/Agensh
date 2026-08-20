# UEM — Unified Event Message

Environment → Agent inbound event protocol. The dual of MCP: MCP is Agent → environment outbound tool protocol,
UEM is environment → Agent inbound event protocol.

> Status: Draft v0.1 (M2-E.2 internal use, not published externally).
> R7 note: router → sidecar refactor **does not change UEM payload or ACP rendering format**.
> The naming "Unified" implies it is decoupled from source — any environment surface
> (Gitea / Slack / Email / Calendar / self-built system) can push events to agents in UEM form.

---

## 1. Design Principles

### 1.1 Agent Autonomous, Environment Only Notifies
The environment **only** tells the agent "what happened". The agent decides on its own whether to respond, how to respond,
when to respond. The environment does not command the agent, does not stipulate flow, does not interpret intent.

→ Direct consequence: UEM fields are all **facts** (observable facts), with no "commanding" fields like
`action_required`, `priority`, `should_respond`, etc.

### 1.2 Agent is a Stateless Responder
Agents do not "continuously think" between UEMs. Each UEM (or batch) triggers **one turn**,
after the turn ends the agent returns to silence. Agent "long-term autonomy" is accumulated across N turns,
not a resident process inside a single turn.

→ Direct consequence: UEM must be **self-contained locator information** — when the agent receives a UEM, it must be able to use UEM fields +
preset MCP tools to locate and pull details. The environment cannot assume the agent remembers context.

### 1.3 Source-agnostic
The UEM schema does not distinguish source (gitea / slack / email…). `source` is a **string field**,
not an enum. The agent infers how to respond via `source + kind + summary`, without environment prompting.

→ Direct consequence: adding future sources requires **zero schema changes**. New environments only need to implement UEM push + hook up the corresponding MCP.

### 1.4 At-least-once, Agent Self-deduplicates
Transport guarantee is at-least-once. The agent must use `event_id` to self-deduplicate — typical approach is
to persist processed event_ids to the agent's own memory store.

→ Direct consequence: `event_id` is a protocol-required field, the unique anchor for agent-side deduplication.

### 1.5 Batch is Optimization, Single is Base
UEM single is the base unit. The environment **may** merge multiple UEMs arriving simultaneously into one batch
push (reduces turn count → higher prefix cache hit + cheaper), but the agent must
be able to correctly handle deduplication and priority judgment within the batch.

---

## 2. Wire Schema

### 2.1 Single UEM (router-internal TypeScript form)

```ts
interface UEM {
  /** Globally unique dedup key. Agent uses this to detect repeats. */
  event_id: string;

  /** Source system identifier. Free string, not an enum. */
  source: string;

  /** Event subtype within the source. Free string. */
  kind: string;

  /**
   * Self-contained one-line locator. Must give the agent enough info to
   * locate the underlying object via available MCP tools.
   *
   * Examples:
   *   "team-x/api-gateway issue #42: login returns 500"
   *   "channel #devops received @alice: CI down again"
   *   "calendar event 14:00 1:1 with bob"
   */
  summary: string;

  /** Wall-clock observation time at the source (epoch ms). */
  observed_at: number;

  /** Logical destination agent name. The router routes UEM to one agent. */
  target_agent: string;

  /**
   * Source-specific structured payload. Opaque to UEM protocol.
   * Agent SHOULD prefer pulling fresh detail via MCP over consuming `raw`.
   * Useful for audit / debugging / future enrichment.
   */
  raw: unknown;
}
```

### 2.2 Rendering During ACP Transport

UEM is transported via ACP `session/prompt`. `prompt[].text` is plain text rendered per a
fixed template (no prose introduction, no behavior instructions):

#### 2.2.1 Single UEM Rendering

```
[event]
event_id=<id>
source=<src>
kind=<k>
observed_at=<iso8601>
summary: <one line>
```

#### 2.2.2 Batch Rendering

```
[event-batch] N events

--- event 1/N ---
event_id=...
source=...
kind=...
observed_at=...
summary: ...

--- event 2/N ---
...
```

**Rendering principles**:
- Field names lowercase snake_case, consistent with schema
- No prose like "please ...", "suggest ...", "if ..."
- No source-specific guidance (does not teach agent "how gitea handles it")
- Time uniformly ISO8601, for agent parsing
- Field order fixed: `event_id → source → kind → observed_at → summary`
  (`event_id` first, so agent can dedupe judgment at first glance)

### 2.3 Deleted Fields and Reasons

Fields that existed in the old v0.0 draft:

| Field | Deletion reason |
|---|---|
| `details_url` | Leaks internal hostname; agents should self-query via MCP, not rely on URL |
| `target_agent` (in ACP prompt body) | Already selected at the ACP session routing layer, repetition in body meaningless |
| `priority` / `action_required` | Violates §1.1 "environment only notifies"; priority is agent decision |
| Old name `dedup_key` | Changed to `event_id`, more protocolized, more external |

Note: the `target_agent` field is retained in router internal TypeScript schema
(for routing decisions), but **not rendered into ACP prompt body**.

---

## 3. End-to-End Contract

### 3.1 Router (environment-side) Responsibilities

1. **Collection**: pull/subscribe events from each source (gitea notifications API / slack RTM / …)
2. **Mapping**: source-native event → UEM
   - `event_id` must be globally unique and stable (multiple pulls of same event must give the same id)
   - `summary` must be self-contained locator (**forbidden** to contain internal URLs)
3. **Routing**: decide which `target_agent` each UEM is delivered to based on business rules
4. **Deduplication**: the central `events` store guarantees `(dedup_key, agent)` unique
5. **Transport**: deliver via ACP `session/prompt` to the target agent, can be single or batch
6. **Do not**: command agents, interpret event meaning, add prose to prompt

### 3.2 Agent (Hermes-side) Responsibilities

1. **Deduplicate**: query own memory store with `event_id`; ignore if already processed
2. **Pull details**: based on `summary` + known tools, use MCP to pull real data
3. **Decide**: autonomously judge response method
4. **Execute**: call MCP tools to complete response (comment / open PR / send message / …)
5. **Persist**: after handling, write `event_id` + processing result to memory, for next dedupe use
6. **Do not**: poll environment, assume prompt has instructions, request environment clarification

### 3.3 Errors and Failures

- **Agent throws exception**: ACP `prompt()` returns non-`end_turn` stopReason;
  router marks `failed` but **does not resend** (avoiding double side effects); recorded to events table
  for human review
- **Agent unresponsive (stuck)**: router-side watchdog (default 20 minutes) triggers
  ACP `session/cancel`; ACP session preserved, next batch still goes same session
  → cancel does not kill session; events table marks `cancelled`, awaits human judgment on whether to redeliver
- **Agent container crashes**: docker `restart: unless-stopped` auto pulls up;
  router re-`loadSession(sessionId)` restores; rows in events table in `sending` state
  need startup scavenge (M2-E.3 work item)

---

## 4. Relation to Existing Standards

| Protocol | Direction | Scope | UEM relation |
|---|---|---|---|
| **MCP** | agent → environment | Tool invocation | Dual. Agent uses MCP outbound, environment uses UEM inbound |
| **ACP** | client ↔ agent | Session channel | UEM travels via ACP `session/prompt` |
| **AGENTS.md** | project → agent | system prompt | UEM protocol contract written in AGENTS.md, agent self-loads |
| **A2A** | agent ↔ agent | Agent interconnect | Orthogonal. UEM is environment-side, A2A is agent mesh-side |

UEM chooses **not to invent new transport** — reuses ACP existing stdio JSON-RPC channel.
UEM is **the content convention of ACP `prompt[].text`**, not a new protocol stack.

---

## 5. Evolution Roadmap

- **v0.1 (now, M2-E.2)**: internal use; source only gitea; schema locked
- **v0.2**: add second source (slack/email), verify source-agnostic
- **v1.0**: consider public naming (candidate: **AEP — Agent Event Protocol**) +
  external schema documentation; together with MCP/ACP/A2A forming the agent protocol four-piece set

### 5.1 Compatibility Constraints (from v0.1)

- Fields **only add, no delete**: future field additions are non-breaking changes
- Unknown fields agent must ignore rather than error
- `source` and `kind` are always strings, do not become enum

---

## 6. Non-Goals (explicit non-do)

- ❌ UEM does not transmit system prompt / behavior instructions
  → that is AGENTS.md's responsibility
- ❌ UEM does not do ACK backflow
  → at-least-once + agent self-dedupe already suffices; do not introduce bidirectional state machine
- ❌ UEM does not do "event subscription" protocol
  → who pushes to whom, what to push is router's internal decision, not exposed to agent
- ❌ UEM does not standardize how agents respond
  → agents fully autonomous; environment does not accept agent output
