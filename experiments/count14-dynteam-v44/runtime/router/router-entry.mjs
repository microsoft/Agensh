#!/usr/bin/env node
/** Cold preload before ORIGINAL main.js; no replacement router/dispatcher. */
import { readFile, realpath } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve, join } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { installSessionHook, SOURCE_COMMIT } from './router-session-hook.mjs';

function need(ok, code) { if (!ok) throw new Error(code); }

export async function nativeBudgetClock(route, environment = process.env) {
  const keys = ['COUNT14_BUDGET_PAUSE_FILE', 'COUNT14_BUDGET_PAUSE_BINDING_SHA256',
    'COUNT14_BUDGET_PAUSE_OWNER_UID'];
  const values = keys.map(k => environment[k]);
  // Historical OWN fixtures may still exercise the byte-pinned unadapted beta
  // channel. Real production/smoke ALWAYS uses the exact qualified reader.
  if (route.mode === 'own-zero' && values.every(v => v === undefined)) return undefined;
  need(values.every(v => typeof v === 'string') && /^[0-9a-f]{64}$/.test(values[1]) &&
    /^(0|[1-9][0-9]*)$/.test(values[2]) && Number.isSafeInteger(Number(values[2])),
    'DYNTEAM_NATIVE_PHASE_ORIGINAL_CLOCK_BINDING_REQUIRED');
  need(route.mode === 'own-zero' || values[0] === '/run/count14-budget-clock/' + route.role_slot + '.json',
    'DYNTEAM_NATIVE_PHASE_CLOCK_EXACT_ROLE_MOUNT');
  const path = join(route.native_router_dist, 'count14_budget_pause_clock.js');
  need(path === await realpath(path) && createHash('sha256').update(await readFile(path)).digest('hex') ===
    'ee22d21d1285b251aa872e0b3f2a25d5d959b3a910ff9e28db4b4a65b99e2b6f',
    'DYNTEAM_NATIVE_PHASE_EXACT_QUALIFIED120_READER');
  const { BudgetPauseClock } = await import(pathToFileURL(path).href);
  return new BudgetPauseClock(values[0], values[1], Number(values[2]));
}

export async function prepareRoute(configurationPath) {
  need(resolve(configurationPath) === await realpath(configurationPath), 'DYNTEAM_ROUTE_CANONICAL');
  const route = JSON.parse(await readFile(configurationPath, 'utf8'));
  need(route.schema === 'count14-dynteam-router-cold-route-v1' && route.source_commit === SOURCE_COMMIT &&
    ['production', 'smoke', 'own-zero'].includes(route.mode), 'DYNTEAM_COLD_ROUTE_SCHEMA_SOURCE');
  const dist = route.native_router_dist;
  need(typeof dist === 'string' && resolve(dist) === await realpath(dist), 'DYNTEAM_NATIVE_DIST_CANONICAL');
  need(route.mode === 'own-zero' || dist === '/app/dist', 'DYNTEAM_IMAGE_ORIGINAL_NATIVE_DIST');
  for (const name of ['acp_socket_channel.js', 'main.js']) {
    const path = join(dist, name);
    need(path === await realpath(path), 'DYNTEAM_NATIVE_MODULE_NO_SYMLINK');
    const raw = await readFile(path);
    need(createHash('sha256').update(raw).digest('hex') === route.native_module_pins[name],
      'DYNTEAM_FROZEN_NATIVE_MODULE_PIN');
  }
  const { ACPSocketChannel } = await import(pathToFileURL(join(dist, 'acp_socket_channel.js')).href);
  const installed = installSessionHook(ACPSocketChannel, route);
  return { route, ACPSocketChannel, ...installed };
}

async function main() {
  const verifyOnly = process.argv[2] === '--verify-only';
  need((verifyOnly && process.argv.length === 4) || (!verifyOnly && process.argv.length === 2),
    'DYNTEAM_ROUTER_ENTRY_EXACT_ARGUMENTS');
  const path = verifyOnly ? process.argv[3] : '/run/count14-dynteam/route.json';
  const prepared = await prepareRoute(path);
  if (verifyOnly) {
    process.stdout.write(JSON.stringify({ COLD_PRELOAD_IMPORT_PASS: true, source_commit: SOURCE_COMMIT,
      original_main_started: false, models: 0 }) + '\n');
    return;
  }
  need(prepared.route.mode !== 'own-zero', 'DYNTEAM_OWN_ZERO_NEVER_STARTS_NATIVE_MAIN');
  need(process.env.ACP_SOCKET_PATH === prepared.route.native_acp_socket,
    'DYNTEAM_ORIGINAL_MAIN_ACP_SOCKET_ROUTE_MATCH');
  // Original factory, event store, listeners and dispatcher. Import exactly once.
  await import(pathToFileURL(join(prepared.route.native_router_dist, 'main.js')).href);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => {
    // Fixed code/type only. Never print original error args/stack/message.
    process.stderr.write(JSON.stringify({ status: 'DYNTEAM_COLD_ROUTER_PRELOAD_FAILED_NO_RETRY',
      exception_type: error?.constructor?.name ?? 'Error' }) + '\n');
    process.exitCode = 1;
  });
}
