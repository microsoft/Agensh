#!/usr/bin/env node
/** Actual private scientific entry. No public model/body response channel. */
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { prepareRoute, nativeBudgetClock } from './router-entry.mjs';
import { NativeRacingPhasePort, physicalProofFromRoute, servePrivatePhase } from './native-racing-phase-port.mjs';

function need(ok, code) { if (!ok) throw new Error(code); }

export async function startNativePhase(routePath) {
  const { route, ACPSocketChannel } = await prepareRoute(routePath);
  need(route.private_phase_schema === 'count14-private-native-racing-phase-v1' &&
    typeof route.private_phase_socket === 'string' && typeof route.private_phase_secret === 'string' &&
    typeof route.native_agent_socket === 'string', 'DYNTEAM_RACING_FROZEN_PRIVATE_ENTRY_ROUTE');
  need(route.mode === 'own-zero' || (routePath === '/run/count14-dynteam/route.json' &&
    dirname(route.private_phase_socket) === '/run/count14-dynteam' &&
    dirname(route.private_phase_secret) === '/run/count14-dynteam'), 'DYNTEAM_RACING_PRIVATE_ENTRY_EXACT_MOUNT');
  const port = new NativeRacingPhasePort({ Channel: ACPSocketChannel, route,
    physicalProof: physicalProofFromRoute(route), budgetPauseClock: await nativeBudgetClock(route) });
  await port.startProxy();
  const server = await servePrivatePhase({ port, socketPath: route.private_phase_socket,
    secretPath: route.private_phase_secret });
  return { port, server, route };
}

async function main() {
  need(process.argv.length === 3, 'DYNTEAM_RACING_NATIVE_ENTRY_EXACT_ARGUMENT');
  const started = await startNativePhase(process.argv[2]);
  process.stdout.write(JSON.stringify({ PRIVATE_NATIVE_PHASE_READY: true, role: started.route.role_slot,
    source_commit: started.route.source_commit, frozen_native_channel_called_without_replacement_dispatcher: true,
    qualified_native120_clock_bound: started.port.budgetPauseClock !== undefined,
    science_or_model_body_exported_to_PUBLIC: false }) + '\n');
  let retiring = false;
  const retire = async () => {
    if (retiring) return; retiring = true;
    started.port.stopping = true; started.server.close();
    // Normal TERM never closes an admitted native turn or a paid model. Poll
    // bounded read-only receipts outside locks until original physical clear.
    while (true) {
      if (!started.port.busy) {
        try { await started.port.closeAfterDrained({ allowRetained: true }); break; }
        catch { /* same original custody retained; no restart/cancel/replay */ }
      }
      await new Promise(ok => setTimeout(ok, 250));
    }
    process.stdout.write('{"PRIVATE_NATIVE_PHASE_RETIRED_AFTER_PHYSICAL_CLEAR":true}\n');
  };
  process.on('SIGTERM', () => { void retire(); });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => {
    process.stderr.write(JSON.stringify({ PUBLIC_code: 'DYNTEAM_RACING_NATIVE_ENTRY_FAILED_RETAIN',
      exception_type: error?.constructor?.name ?? 'Error' }) + '\n');
    process.exitCode = 1;
  });
}
