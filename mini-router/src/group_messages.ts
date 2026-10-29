/**
 * Keep the latest 32 group messages in a batch inline; save larger batches as JSONL.
 * The saved file contains every group message in that batch, with full post text.
 */
import { createHash, randomUUID } from "node:crypto";
import { mkdir, open, rename, unlink } from "node:fs/promises";
import { join } from "node:path";
import type { EventRow, UEMLike } from "./state.ts";

// Keep SQL selection aligned with isGroupMessage(), including edits and deletions.
export const GROUP_CHAT_SQL = `COALESCE(source = 'mattermost' AND (
  JSON_UNQUOTE(JSON_EXTRACT(payload, '$.kind')) IN ('post', 'group')
  OR (JSON_UNQUOTE(JSON_EXTRACT(payload, '$.kind')) IN ('post_edited', 'post_deleted')
      AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.raw.data.channel_type')) IN ('O', 'P', 'G'))
), FALSE)`;

export function isGroupMessage(payload: UEMLike): boolean {
  if (payload.source !== "mattermost") return false;
  if (payload.kind === "post" || payload.kind === "group") return true;
  const raw = payload.raw as { data?: { channel_type?: string } } | undefined;
  return (payload.kind === "post_edited" || payload.kind === "post_deleted")
    && ["O", "P", "G"].includes(raw?.data?.channel_type ?? "");
}

function messageText(payload: UEMLike): string {
  const raw = payload.raw as { data?: { post?: string } } | undefined;
  if (typeof raw?.data?.post === "string") {
    try {
      const post = JSON.parse(raw.data.post) as { message?: unknown };
      if (typeof post.message === "string") return post.message;
    } catch {   }
  }
  return String(payload.summary ?? "");
}

export async function groupMessagePayloads(batch: EventRow[], directory: string, username: string): Promise<UEMLike[]> {
  const limit = 32;
  const messages = batch.filter((row) => isGroupMessage(row.payload));
  if (messages.length <= limit) return batch.map((row) => row.payload);
  const earlier = messages.slice(0, -limit);
  const latest = new Set(messages.slice(-limit).map((row) => row.id));
  const digest = createHash("sha256").update(messages.map((row) => row.id).join(",")).digest("hex").slice(0, 16);
  const path = join(directory, `group-messages-${digest}.jsonl`);
  await mkdir(directory, { recursive: true, mode: 0o755 });
  const temporary = path + "." + randomUUID() + ".tmp";
  try {
    const file = await open(temporary, "wx", 0o644);
    try {
      await file.writeFile(messages.map((row) => JSON.stringify({
        id: row.id, ...row.payload, message: messageText(row.payload),
      })).join("\n") + "\n");
      await file.sync();
    } finally {
      await file.close();
    }
    await rename(temporary, path);
    // Seal the file and its directory entry before advertising the path to the worker.
    const parent = await open(directory, "r");
    try { await parent.sync(); } finally { await parent.close(); }
  } catch (error) {
    await unlink(temporary).catch(() => undefined);
    throw error;
  }
  const handle = "@" + username.replace(/^@/, "");
  // Match the complete handle so worker1 does not count mentions of worker10.
  const escaped = handle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const mention = new RegExp(`(?<![a-zA-Z0-9_.@-])${escaped}(?![a-zA-Z0-9_-]|\\.[a-zA-Z0-9_.-])`, "gi");
  const count = earlier.reduce((n, row) => n + (messageText(row.payload).match(mention)?.length ?? 0), 0);
  const last = messages[messages.length - 1]!.payload;
  const notice: UEMLike = {
    event_id: `group-message-history:${digest}`, source: "system", target_agent: last.target_agent,
    kind: "group_message_history", observed_at: last.observed_at,
    summary: `Showing the latest ${limit} group-chat messages. ${earlier.length} earlier messages are saved in ${path} `
      + `(the file contains all ${messages.length} queued group-chat messages, including full message text). `
      + `You are mentioned ${count} times in the earlier messages. Search the file for "${handle}" to find your mentions.`,
    raw: { path, total: messages.length, earlier: earlier.length, mentions: count, username },
  };
  return [notice, ...batch.filter((row) => !isGroupMessage(row.payload) || latest.has(row.id)).map((row) => row.payload)];
}
