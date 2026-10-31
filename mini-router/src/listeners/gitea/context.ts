/**
 * Inline context for Gitea events (EVENT_CONTEXT=inline): who wrote the latest
 * comment and how it starts, so a worker sees what happened without a tool call.
 * Longer text is cut ("spilled") and the event names the API path that reads the
 * rest. The notification itself carries only the subject's title.
 */
import type { GiteaNotificationRaw } from "./fetcher.ts";

export const EXCERPT_CHARS = 200;

export interface GiteaDetail {
  author: string;
  excerpt: string;
  truncated: boolean;
  /** API path (on http://gitea:3000) that returns the full text. */
  readMore: string;
  /** The comment's id, or null when the detail is the issue or PR body. */
  commentId: number | null;
}

interface GiteaTextObject {
  id?: number;
  user?: { login?: string };
  body?: string;
}

export function excerpt(text: string, max = EXCERPT_CHARS): { text: string; truncated: boolean } {
  const flat = text.replace(/\s+/g, " ").trim();
  if (flat.length <= max) return { text: flat, truncated: false };
  return { text: flat.slice(0, max - 1) + "…", truncated: true };
}

/** The API path of the text that explains this notification: latest comment, else the subject. */
export function detailPath(n: GiteaNotificationRaw): { path: string; isComment: boolean } | null {
  const comment = n.subject?.latest_comment_url;
  const subject = n.subject?.url;
  const pathOf = (url: string) => {
    try {
      return new URL(url).pathname;
    } catch {
      return null;
    }
  };
  if (comment && comment !== subject) {
    const path = pathOf(comment);
    if (path) return { path, isComment: true };
  }
  const path = subject ? pathOf(subject) : null;
  return path ? { path, isComment: false } : null;
}

export function toDetail(object: GiteaTextObject, path: string, isComment: boolean): GiteaDetail {
  const { text, truncated } = excerpt(object.body ?? "");
  return {
    author: object.user?.login ?? "?",
    excerpt: text,
    truncated,
    readMore: path,
    commentId: isComment && typeof object.id === "number" ? object.id : null,
  };
}

export function withDetail(summary: string, detail: GiteaDetail | null): string {
  if (!detail) return summary;
  const what = detail.commentId !== null ? `latest comment by @${detail.author}` : `by @${detail.author}`;
  const body = detail.excerpt ? `: "${detail.excerpt}"` : "";
  const more = detail.truncated ? ` (full text: GET ${detail.readMore})` : "";
  const id = detail.commentId !== null ? ` [comment ${detail.commentId}]` : "";
  return `${summary} — ${what}${body}${id}${more}`;
}
