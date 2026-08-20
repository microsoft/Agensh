import { execFileSync, spawnSync, type ExecFileSyncOptions } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { TOKENS_DIR } from "./env.ts";

/** existsSync that falls back to `sudo test -e` for 0700-root paths. */
function pathExists(p: string): boolean {
  if (existsSync(p)) return true;
  const r = spawnSync("sudo", ["test", "-e", p], { stdio: "ignore" });
  return r.status === 0;
}

/**
 * Read a token file under .claude-team-data/<profile>/tokens/. The
 * directory is 0600 root-owned (created by the bootstrap container), so
 * we shell out to `sudo cat`. Tests on hosts where the user can read it
 * directly still work — sudo is a no-op for already-readable files.
 */
export function readTokenFile(name: string): string {
  const path = resolve(TOKENS_DIR, name);
  if (!pathExists(path)) {
    throw new Error(`token file not found: ${path}`);
  }
  const out = execFileSync("sudo", ["cat", path], {
    encoding: "utf8",
    timeout: 10_000,
  });
  return out.trim();
}

export function readAdminToken(): string {
  return readTokenFile("admin.token");
}

export function readAgentToken(agent: string): string {
  return readTokenFile(`agent-${agent}.token`);
}

/** Stat a token file via sudo (mtime / size); returns null if missing. */
export interface TokenStat {
  name: string;
  size: number;
  mtimeNs: bigint;
}

export function statTokenFile(name: string): TokenStat | null {
  const path = resolve(TOKENS_DIR, name);
  if (!pathExists(path)) return null;
  // %s = size in bytes, %Y = seconds since epoch (mtime, integer), %y = human
  // We use %s and the GNU stat extension --printf to combine size+mtime ns.
  const opts: ExecFileSyncOptions = { encoding: "utf8", timeout: 5_000 };
  const out = execFileSync(
    "sudo",
    ["stat", "--printf=%s\t%Y\t%.9Y", path],
    opts,
  ).toString();
  const [size, _mtimeSec, mtimeWithFraction] = out.split("\t");
  return {
    name,
    size: Number(size ?? 0),
    // %.9Y on coreutils stat prints seconds.nanoseconds. Convert to bigint ns.
    mtimeNs: parseMtimeNs(mtimeWithFraction ?? "0"),
  };
}

function parseMtimeNs(s: string): bigint {
  const [sec, frac = "0"] = s.trim().split(".");
  const fracPad = (frac + "000000000").slice(0, 9);
  return BigInt(sec ?? "0") * 1_000_000_000n + BigInt(fracPad);
}
