/**
 * UEM mapping unit tests for mini-router (R7) — pure function, no I/O.
 *
 * Ported from router/test/uem.test.ts. Updated for the post-B7 event_id
 * format `gitea:notif:<id>:<updated_at>` (so follow-up comments don't
 * silently dedup).
 */
import { describe, expect, it } from "vitest";
import { giteaNotificationToUEM } from "../../mini-router/src/listeners/gitea/notification.ts";

describe("giteaNotificationToUEM", () => {
  const baseNotif = {
    id: 42,
    updated_at: "2026-04-27T08:00:00Z",
    subject: {
      title: "fix: webhook idempotency",
      type: "Issue",
      url: "http://gitea:3000/api/v1/repos/team/test-sandbox/issues/3",
      html_url: "http://gitea.localhost:28081/team/test-sandbox/issues/3",
    },
    repository: { full_name: "team/test-sandbox" },
  };

  it("populates required UEM fields from a typical Gitea notification", () => {
    const uem = giteaNotificationToUEM(baseNotif, "agent1", 1_700_000_000_000);
    expect(uem.source).toBe("gitea");
    expect(uem.target_agent).toBe("agent1");
    expect(uem.kind).toBe("issue");
    expect(uem.summary).toContain("team/test-sandbox");
    expect(uem.summary).toContain("fix: webhook idempotency");
    expect(uem.summary).toContain("#3");
    expect(uem.observed_at).toBe(1_700_000_000_000);
  });

  it("never leaks internal URLs", () => {
    const uem = giteaNotificationToUEM(baseNotif, "agent1", 0);
    expect(JSON.stringify(uem)).not.toContain("details_url");
    expect(uem).not.toHaveProperty("details_url");
  });

  it("event_id includes updated_at so follow-up comments don't dedup", () => {
    const first = giteaNotificationToUEM(baseNotif, "agent1", 0);
    const followup = giteaNotificationToUEM(
      { ...baseNotif, updated_at: "2026-04-27T09:00:00Z" },
      "agent1",
      0,
    );
    expect(first.event_id).toBe("gitea:notif:42:2026-04-27T08:00:00Z");
    expect(followup.event_id).toBe("gitea:notif:42:2026-04-27T09:00:00Z");
    expect(first.event_id).not.toBe(followup.event_id);
  });

  it("survives a sparse notification (missing subject/repo)", () => {
    const uem = giteaNotificationToUEM(
      { id: 7, updated_at: "2026-01-01T00:00:00Z" },
      "agent1",
      0,
    );
    expect(uem.event_id).toBe("gitea:notif:7:2026-01-01T00:00:00Z");
    expect(uem.kind).toBe("unknown");
    expect(uem.summary).toContain("(no title)");
  });

  it("preserves raw payload for audit", () => {
    const uem = giteaNotificationToUEM(baseNotif, "agent1", 0);
    expect(uem.raw).toBe(baseNotif);
  });

  it("handles PR (Pull) subject type", () => {
    const prNotif = { ...baseNotif, subject: { ...baseNotif.subject, type: "Pull", url: "http://gitea:3000/api/v1/repos/team/repo/pulls/9" } };
    const uem = giteaNotificationToUEM(prNotif, "agent1", 0);
    expect(uem.kind).toBe("pull");
    expect(uem.summary).toContain("#9");
  });
});
