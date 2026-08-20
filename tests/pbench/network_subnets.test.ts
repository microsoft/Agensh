/**
 * pbench/network_subnets.test.ts — the three per-stack networks must be
 * addressable without the daemon's default pool.
 *
 * WHY
 * Each pbench stack creates three networks (default/internal, egress, edge).
 * Docker's built-in pool is 172.17.0.0/12 in /16s plus 192.168.0.0/16 in /20s
 * — 31 subnets. Nine stacks is 27, so 20 concurrent stacks cannot fit, and the
 * tenth `make up` dies with "all predefined address pools have been fully
 * subnetted". Worse, it dies AFTER the run script's teardown trap is armed, so
 * the chain exports an empty submission and scores it 0.00% with every test
 * not_run — indistinguishable from a task the agents genuinely failed.
 *
 * The obvious fix — default-address-pools in /etc/docker/daemon.json — does not
 * survive on this host: Ansible runs every 30 minutes (0,30 * * * *), reverts
 * daemon.json, and restarts dockerd. That restart killed seven live stacks
 * mid-run. Anything outside the repo is temporary here.
 *
 * So the subnets are pinned in compose instead, from a range Ansible does not
 * manage and nothing else on the host uses.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { REPO_ROOT } from "../lib/env.ts";

const PBENCH = resolve(REPO_ROOT, "docker/docker-compose.pbench.yml");
const GEN_ENV = resolve(REPO_ROOT, "scripts/pbench_gen_env_sweep.sh");

const text = (p: string) => readFileSync(p, "utf8");

/** Parse "10.176.3.0/24" into a comparable [a,b,c,d,bits]. */
function parseCidr(s: string): number[] {
  const [ip, bits] = s.split("/");
  return [...ip!.split(".").map(Number), Number(bits)];
}

describe("per-stack network subnets", () => {
  it("pins an explicit subnet for all three networks", () => {
    const body = text(PBENCH);
    for (const net of ["PBENCH_SUBNET_DEFAULT", "PBENCH_SUBNET_EGRESS", "PBENCH_SUBNET_EDGE"]) {
      expect(body).toContain(`\${${net}`);
    }
    // Three ipam blocks, one per network.
    expect(body.match(/ipam:/g) ?? []).toHaveLength(3);
  });

  it("keeps the default network internal — anti-cheat depends on it", () => {
    // Pinning subnets must not disturb the seal: agents/gitea sit only on the
    // internal net, so a stack cannot reach the internet except via egress-proxy.
    const body = text(PBENCH);
    expect(body).toMatch(/default:\s*\n(\s+#.*\n)*\s+internal:\s*true/);
  });

  it("falls back to a usable subnet when unparameterised", () => {
    // Single-profile runs (dev, smoke, sweep_5 reruns) set no subnet vars and
    // must still come up. Distinct fallbacks so the three do not collide.
    const body = text(PBENCH);
    const fallbacks = [...body.matchAll(/\$\{PBENCH_SUBNET_[A-Z]+:-([0-9./]+)\}/g)].map(
      (m) => m[1]!,
    );
    expect(fallbacks).toHaveLength(3);
    expect(new Set(fallbacks).size).toBe(3);
  });

  it("allocates 20 non-overlapping /24 triples, clear of host and k8s ranges", () => {
    const body = text(GEN_ENV);
    // The generator builds the CIDR in shell, then passes it through to the
    // PBENCH_SUBNET_* keys — so the literal range lives on the sub_* lines.
    const m = body.match(/sub_default="10\.(\d+)\./);
    expect(m).not.toBeNull();
    const second = Number(m![1]);
    // 10.176-10.191 is free here: the host routes 10.50.x and 10.217.24.0/21,
    // k8s defaults its service CIDR to 10.96.0.0/12, and kind uses 10.244.0.0/16.
    expect(second).toBeGreaterThanOrEqual(176);
    expect(second).toBeLessThan(192);
    // All three networks must come from the same profile-indexed triple.
    expect(body).toMatch(/sub_default="10\.\d+\.\$\(\(idx\*3\)\)\.0\/24"/);
    expect(body).toMatch(/sub_egress="10\.\d+\.\$\(\(idx\*3\+1\)\)\.0\/24"/);
    expect(body).toMatch(/sub_edge="10\.\d+\.\$\(\(idx\*3\+2\)\)\.0\/24"/);
    // idx must be the pre-increment index, or profile a starts at .3 and the
    // last profile can run past 255.
    expect(body).toMatch(/idx=\$i\s*#[^\n]*\n\s*i=\$\(\(i\+1\)\)/);
  });

  it("gives each profile a distinct triple with no overlap", () => {
    // Simulate the generator's arithmetic: profile i gets .{3i}, .{3i+1}, .{3i+2}
    const seen = new Set<string>();
    for (let i = 0; i < 20; i++) {
      for (const k of [0, 1, 2]) {
        const octet = i * 3 + k;
        expect(octet).toBeLessThan(256); // 20*3 = 60, comfortably inside one /16
        const cidr = `10.176.${octet}.0/24`;
        expect(seen.has(cidr)).toBe(false);
        seen.add(cidr);
        expect(parseCidr(cidr)[4]).toBe(24);
      }
    }
    expect(seen.size).toBe(60);
  });
});
