/**
 * F8 mattermost notification → UEM mapper unit tests.
 *
 * Pure function, no I/O. Pinning the wire-level contract.
 */
import { describe, expect, it } from "vitest";
import { mattermostEventToUEM, type MattermostWsEvent } from "../../mini-router/src/listeners/mattermost/notification.ts";

function postEvent(over: Partial<MattermostWsEvent> = {}): MattermostWsEvent {
  return {
    event: "posted",
    data: {
      channel_display_name: "Town Square",
      channel_name: "town-square",
      channel_type: "O",
      mentions: '["agent3"]',
      post: JSON.stringify({
        id: "post-abc",
        create_at: 1_700_000_000_000,
        edit_at: 0,
        user_id: "user-coder1",
        channel_id: "channel-xyz",
        message: "hello @agent3 please look at this",
        type: "",
      }),
      sender_name: "@coder1",
      set_online: true,
      team_id: "team-eng",
    },
    broadcast: { user_id: "user-agent3", channel_id: "channel-xyz", team_id: "team-eng", omit_users: null },
    seq: 42,
    ...over,
  };
}

describe("mattermostEventToUEM", () => {
  it("maps a `posted` channel message to a well-formed UEM", () => {
    const uem = mattermostEventToUEM(postEvent(), "agent3", 1_777_000_000_000);
    expect(uem.source).toBe("mattermost");
    expect(uem.target_agent).toBe("agent3");
    expect(uem.kind).toBe("post");
    expect(uem.summary).toContain("@coder1");
    expect(uem.summary).toContain("Town Square");
    expect(uem.summary).toContain("hello @agent3");
    expect(uem.observed_at).toBe(1_777_000_000_000);
  });

  it("event_id includes post_id + edit_at so edits don't dedup", () => {
    const a = mattermostEventToUEM(postEvent(), "agent3", 0);
    const edited = postEvent({
      data: {
        ...postEvent().data,
        post: JSON.stringify({
          id: "post-abc",
          create_at: 1_700_000_000_000,
          edit_at: 1_700_000_900_000,
          user_id: "user-coder1",
          channel_id: "channel-xyz",
          message: "hello @agent3 please look at this (edited)",
          type: "",
        }),
      },
    });
    const b = mattermostEventToUEM(edited, "agent3", 0);
    expect(a.event_id).toBe("mattermost:post:post-abc:0");
    expect(b.event_id).toBe("mattermost:post:post-abc:1700000900000");
    expect(a.event_id).not.toBe(b.event_id);
  });

  it("kind=dm when channel_type=D (direct message)", () => {
    const ev = postEvent({
      data: {
        ...postEvent().data,
        channel_type: "D",
        channel_display_name: "",
        channel_name: "user-coder1__user-agent3",
      },
    });
    const uem = mattermostEventToUEM(ev, "agent3", 0);
    expect(uem.kind).toBe("dm");
    expect(uem.summary).toContain("DM");
  });

  it("kind=group when channel_type=G", () => {
    const ev = postEvent({ data: { ...postEvent().data, channel_type: "G" } });
    expect(mattermostEventToUEM(ev, "agent3", 0).kind).toBe("group");
  });

  it("kind=post for public channel (O) and private (P)", () => {
    expect(mattermostEventToUEM(postEvent({ data: { ...postEvent().data, channel_type: "O" } }), "a", 0).kind).toBe("post");
    expect(mattermostEventToUEM(postEvent({ data: { ...postEvent().data, channel_type: "P" } }), "a", 0).kind).toBe("post");
  });

  it("kind=post_edited for `post_edited` event", () => {
    const ev = postEvent({ event: "post_edited" });
    expect(mattermostEventToUEM(ev, "agent3", 0).kind).toBe("post_edited");
  });

  it("kind=post_deleted for `post_deleted` event", () => {
    const ev = postEvent({ event: "post_deleted" });
    expect(mattermostEventToUEM(ev, "agent3", 0).kind).toBe("post_deleted");
  });

  it("never leaks raw token / cookie material in summary", () => {
    const ev = postEvent();
    const uem = mattermostEventToUEM(ev, "agent3", 0);
    expect(uem.summary).not.toMatch(/Bearer|token|MMAUTHTOKEN/i);
  });

  it("preserves raw event for audit", () => {
    const ev = postEvent();
    const uem = mattermostEventToUEM(ev, "agent3", 0);
    expect(uem.raw).toBe(ev);
  });

  it("survives malformed post JSON without crashing", () => {
    const ev = postEvent({ data: { ...postEvent().data, post: "{not valid json" } });
    expect(() => mattermostEventToUEM(ev, "agent3", 0)).not.toThrow();
    const uem = mattermostEventToUEM(ev, "agent3", 0);
    expect(uem.kind).toBe("post");
    expect(uem.summary).toContain("(malformed");
  });

  it("uses broadcast fields when channel_id missing in data", () => {
    const ev: MattermostWsEvent = {
      event: "posted",
      data: { post: JSON.stringify({ id: "p1", create_at: 0, edit_at: 0, user_id: "u1", channel_id: "", message: "hi" }) },
      broadcast: { user_id: "user-agent3", channel_id: "ch-from-broadcast", team_id: "t1", omit_users: null },
      seq: 1,
    };
    const uem = mattermostEventToUEM(ev, "agent3", 0);
    expect(uem.summary).toContain("ch-from-broadcast");
  });

  it("maps reaction_added to a UEM with kind=reaction_added", () => {
    const ev: MattermostWsEvent = {
      event: "reaction_added",
      data: {
        reaction: JSON.stringify({
          user_id: "user-mmadmin",
          post_id: "post-abc",
          emoji_name: "thumbsup",
          create_at: 1_700_000_000_000,
          channel_id: "ch-1",
        }),
      },
      broadcast: { channel_id: "ch-1" },
      seq: 7,
    };
    const uem = mattermostEventToUEM(ev, "coder30", 1_777_000_000_000);
    expect(uem.kind).toBe("reaction_added");
    expect(uem.summary).toMatch(/user-mmadmin reacted :thumbsup: on post post-abc/);
    expect(uem.event_id).toBe("mattermost:reaction_added:post-abc:user-mmadmin:thumbsup");
  });

  it("maps reaction_removed and uses a distinct event_id from add", () => {
    const base = (event: string): MattermostWsEvent => ({
      event,
      data: {
        reaction: JSON.stringify({
          user_id: "u1", post_id: "p1", emoji_name: "tada", create_at: 0,
        }),
      },
      broadcast: {},
      seq: 1,
    });
    const a = mattermostEventToUEM(base("reaction_added"), "x", 0);
    const r = mattermostEventToUEM(base("reaction_removed"), "x", 0);
    expect(a.kind).toBe("reaction_added");
    expect(r.kind).toBe("reaction_removed");
    expect(a.event_id).not.toBe(r.event_id);
  });

  it("survives malformed reaction payload without crashing", () => {
    const ev: MattermostWsEvent = {
      event: "reaction_added",
      data: { reaction: "{not json" },
      broadcast: {},
      seq: 9,
    };
    expect(() => mattermostEventToUEM(ev, "x", 0)).not.toThrow();
    const uem = mattermostEventToUEM(ev, "x", 0);
    expect(uem.summary).toContain("malformed");
  });
});
