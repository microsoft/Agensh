"""Cold beta adapter reusing the qualified v2 watchdog and exact120s reader.

No live source patch, scientific prompt/context/RNG change or new timeout rule.
Only the old proven pause-clock call-sites are transplanted onto beta's class;
its freshSession, identity, task-first rendering and other methods stay intact.
"""
from pathlib import Path
import hashlib
import json
import shutil

from common import need

READER_SHA='ee22d21d1285b251aa872e0b3f2a25d5d959b3a910ff9e28db4b4a65b99e2b6f'
READER_SIZE=8341
QUALIFIED_CHANNEL_SHA='98fbaa7be8c7ecb9cb9ebc598883b2c2b3ea4d17ce46a2013423ecef7c1dcdfb'


def _method(text,start,end):
    need(text.count(start)==1 and text.count(end)==1,'DYNTEAM_NATIVE_CLOCK_EXACT_METHOD_BOUNDARIES')
    a,b=text.index(start),text.index(end)
    need(a<b,'DYNTEAM_NATIVE_CLOCK_METHOD_ORDER')
    return text[a:b]


def channel_delta(beta,qualified):
    clock_type='  budgetPauseClock?: { assertReadyForPrompt(): void; recordRx(): void; silenceMs(): number | undefined };\n'
    need(beta.count('  stuckMs?: number;\n')==1,'DYNTEAM_BETA_CLOCK_OPTION_SITE')
    out=beta.replace('  stuckMs?: number;\n','  stuckMs?: number;\n'+clock_type)
    header='  private async sendText(text: string): Promise<{ stopReason: string }> {\n'
    need(out.count(header)==1,'DYNTEAM_BETA_CLOCK_SEND_SITE')
    # Outside original try/catch: stale clock forbids new prompt, not close().
    out=out.replace(header,header+'    this.opts.budgetPauseClock?.assertReadyForPrompt();\n')
    rx='this.lastUpdateAt = Date.now();'
    need(out.count(rx)==2,'DYNTEAM_BETA_TWO_ORIGINAL_RX_CLOCK_SITES')
    out=out.replace(rx,rx+'\n      this.opts.budgetPauseClock?.recordRx();')
    old=_method(out,'  private watchSilence(', '  async close():')
    native=_method(qualified,'  private watchSilence(', '  async close():')
    need('silenceMs()'in native and 'adjusted === undefined'in native and 'NO_RECONNECT'in native,
         'DYNTEAM_QUALIFIED_V2_WATCHDOG_PAUSE_AND_UNKNOWN_GUARDS')
    out=out.replace(old,native)
    return out


def retired_router_hold_delta(clocked):
    """Keep the registered init alive after ORIGINAL account retirement.

    This is no retirement permission and does not send a signal. Only the
    count14 preload's fail-closed worker hook can hold here; vanilla beta and
    every non-retired path keep the original process.exit. Normal owner stop
    uses main's ORIGINAL SIGTERM handler, never a new signal implementation.
    """
    needle='    if (replacement.retired || replacement.username !== identity.username) {\n'
    need(clocked.count(needle)==1,'DYNTEAM_NATIVE_EXACT_ORIGINAL_RETIRED_EXIT_SITE')
    block='      // A paid worker\'s original bridge still owes TERM/wait/archive/END.\n      // Do not destroy its pinned router init before those guards complete.\n      const count14Hold = (channel as unknown as {\n        count14RetiredRouterQuiescence?: (request: { id: string; reason: string }) => Promise<never>;\n      }).count14RetiredRouterQuiescence;\n      if (replacement.retired === true && typeof count14Hold === "function") {\n        await count14Hold.call(channel, request);\n        throw new Error("DYNTEAM_RETIRED_ROUTER_QUIESCENCE_MUST_NOT_RETURN");\n      }\n'
    out=clocked.replace(needle,needle+block)
    start='  const onWorkerRestart = async (request: { id: string; reason: string }) => {\n'
    end='  };\n\n  if (isChecker) {\n'
    need(out.count(start)==1 and out.count(end)==1,
         'DYNTEAM_NATIVE_EXACT_ORIGINAL_RESTART_CALLBACK')
    out=out.replace(start,'  let count14WorkerRetirement: Promise<void> | undefined;\n'+
        start.replace('onWorkerRestart','count14OriginalWorkerRestart'))
    wrapper='  };\n  const onWorkerRestart = (request: { id: string; reason: string }) => {\n    const operation = count14OriginalWorkerRestart(request);\n    // Capture before the original identity request can complete: retiring its\n    // Gitea/MM identity may naturally finish another original listener task.\n    if (typeof (channel as unknown as { count14RetiredRouterQuiescence?: unknown })\n        .count14RetiredRouterQuiescence === "function") count14WorkerRetirement = operation;\n    return operation;\n  };\n\n  if (isChecker) {\n'
    out=out.replace(end,wrapper)
    race='  await Promise.race(tasks);\n'
    need(out.count(race)==1,'DYNTEAM_NATIVE_EXACT_ORIGINAL_PRIMARY_LOOP_EXIT')
    out=out.replace(race,race+
        '  // Do not race an ORIGINAL account retirement with a listener EOF.\n'+
        '  if (!ctrl.signal.aborted && count14WorkerRetirement) await count14WorkerRetirement;\n')
    return out


def main_delta(beta):
    needle='  const stuckMs = Number(process.env.MINI_ROUTER_STUCK_MS ?? "0") || undefined;\n'
    need(beta.count(needle)==1 and beta.count('    stuckMs,\n')==1,'DYNTEAM_BETA_NATIVE_MAIN_CLOCK_SITES')
    block='''  const pauseFile = process.env.COUNT14_BUDGET_PAUSE_FILE;
  const pausePin = process.env.COUNT14_BUDGET_PAUSE_BINDING_SHA256;
  const pauseUid = process.env.COUNT14_BUDGET_PAUSE_OWNER_UID;
  if ([pauseFile, pausePin, pauseUid].filter(x => x !== undefined).length !== 3)
    throw new Error("DYNTEAM_NATIVE_ORIGINAL_CLOCK_BINDING_REQUIRED");
  if (!/^(0|[1-9][0-9]*)$/.test(pauseUid!)) throw new Error("DYNTEAM_NATIVE_CLOCK_OWNER_UID");
  const budgetPauseClock = new BudgetPauseClock(pauseFile!, pausePin!, Number(pauseUid));
'''
    return retired_router_hold_delta('import { BudgetPauseClock } from "./count14_budget_pause_clock.js";\n'+
            beta.replace(needle,needle+block).replace('    stuckMs,\n','    stuckMs,\n    budgetPauseClock,\n'))


def build(beta_router,qualified_channel,reader,destination,*,expected_source_pins):
    beta_router,qualified_channel,reader,destination=map(Path,(beta_router,qualified_channel,reader,destination))
    need(not destination.exists()and hashlib.sha256(reader.read_bytes()).hexdigest()==READER_SHA and
         reader.stat().st_size==READER_SIZE,'DYNTEAM_NATIVE_EXACT120_READER_AND_NEW_COLD_BUILD')
    need(hashlib.sha256(qualified_channel.read_bytes()).hexdigest()==QUALIFIED_CHANNEL_SHA,
         'DYNTEAM_EXACT_QUALIFIED_V2_WATCHDOG_SOURCE')
    names={str(p.relative_to(beta_router))for p in(beta_router/'src').rglob('*.ts')}|{
        'package.json','package-lock.json','tsconfig.json'}
    need(set(expected_source_pins)==names,'DYNTEAM_COMPLETE_PINNED_NATIVE_ROUTER_SOURCE_SET')
    for name,pin in expected_source_pins.items():
        source=beta_router/name
        need(not source.is_symlink()and hashlib.sha256(source.read_bytes()).hexdigest()==pin,
             'DYNTEAM_BETA_NATIVE_ROUTER_SOURCE_PINS')
    destination.mkdir(mode=0o700)
    for name in ('package.json','package-lock.json','tsconfig.json'):
        (destination/name).write_bytes((beta_router/name).read_bytes())
    shutil.copytree(beta_router/'src',destination/'src')
    original_channel=(beta_router/'src/acp_socket_channel.ts').read_text()
    original_main=(beta_router/'src/main.ts').read_text()
    (destination/'src/acp_socket_channel.ts').write_text(channel_delta(original_channel,qualified_channel.read_text()))
    (destination/'src/main.ts').write_text(main_delta(original_main))
    (destination/'src/count14_budget_pause_clock.js').write_bytes(reader.read_bytes())
    (destination/'src/count14_budget_pause_clock.d.ts').write_text('''export class BudgetPauseClock {
  constructor(path: string, bindingSha256: string, ownerUid: number);
  recordRx(): void;
  assertReadyForPrompt(): void;
  silenceMs(): number | undefined;
}
''')
    # TS does not copy an imported JS asset when allowJs=false; stage exact
    # qualified reader directly into dist without a transpiler byte change.
    (destination/'dist').mkdir()
    (destination/'dist/count14_budget_pause_clock.js').write_bytes(reader.read_bytes())
    return dict(original_reader_sha256=READER_SHA,original_reader_bytes=READER_SIZE,
                original_beta_source_modified=False,other_beta_methods_changed=False,
                production_activated=False,needs_native_image_and_full_cold_entry_qualification=True)
