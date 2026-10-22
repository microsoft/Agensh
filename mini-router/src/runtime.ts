/** Shared error formatting and abort-aware delays for router background loops. */
import { setTimeout as delay } from "node:timers/promises";

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}

export function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (!signal) return delay(ms);
  return new Promise((resolve) => {
    const onAbort = () => {
      clearTimeout(timer);
      signal.removeEventListener("abort", onAbort);
      resolve();
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}
