"""Pinned native cold-only JS selectors; inverse reproduces exact fresh bytes.

No source/asset traversal, SDK execution, owner or financial action. The return
is prospective CODE, never a capability/installation or scientific restore.
"""
from pathlib import Path
import hashlib

CHANNEL_SHA='ae2756c6bb6938a30fdb07e25c87377dcb44033c5b0ea3e75d4b4243720d7319'
MAIN_SHA='58a777132b1e196e2b96d3dcb54bf75710ae2a7da97999622c4b79fbaabd9038'
BRIDGE_SHA='13405f8d723dd6e5b9724c0bc8602d5a17da6372071668ecd3c57ef48d4fb1c5'


def need(ok,code):
    if not ok:raise ValueError(code)


def compile_overlay(channel_path,main_path,bridge_path=None):
    originals={};out={};proof={}
    for name,path,pin in [('acp_socket_channel.js',channel_path,CHANNEL_SHA),('main.js',main_path,MAIN_SHA)]:
        path=Path(path);raw=path.read_bytes()
        need(path.resolve()==path and not path.is_symlink() and hashlib.sha256(raw).hexdigest()==pin,'SDK_RESTORE_PINNED_NATIVE_CLOCK_CODE_ONLY')
        originals[name]=raw.decode();out[name]=raw.decode();proof[name]=[]
    def replace(name,old,new):
        need(out[name].count(old)==1,'SDK_RESTORE_EXACT_NATIVE_SELECTOR')
        out[name]=out[name].replace(old,new);proof[name].append((old,new))
    c='acp_socket_channel.js';m='main.js'
    replace(c,'import { randomUUID } from "node:crypto";','import { randomUUID, createHash } from "node:crypto";')
    replace(c,'    connecting = null;','    connecting = null;\n    coldRestoreFailed = false;')
    replace(c,'        this.opts = opts;','''        this.opts = opts;
        if (opts.coldRestore !== undefined && (!/^[0-9a-f]{64}$/.test(opts.coldRestore.session_sha256) ||
            createHash("sha256").update(opts.coldRestore.native_session_uuid,"utf8").digest("hex") !== opts.coldRestore.session_sha256))
            throw Error("COLD_SDK_ORIGINAL_SID_PIN_INVALID");''')
    replace(c,'    async connectWithBackoff() {','''    async connectWithBackoff() {
        if (this.opts.coldRestore !== undefined && this.coldRestoreFailed)
            throw Error("COLD_SDK_FAILED_NO_RETRY_OR_NEW_SESSION");''')
    replace(c,'                    lastErr = e;','''                    if (this.opts.coldRestore !== undefined) {
                        this.coldRestoreFailed = true;
                        throw Error("COLD_SDK_LOAD_FAILED_NO_FALLBACK");
                    }
                    lastErr = e;''')
    replace(c,'''            const ns = await conn.newSession({ cwd: this.opts.cwd, mcpServers: [] });
            const finalId = ns.sessionId;''','''            let finalId;
            if (this.opts.coldRestore !== undefined) {
                finalId = this.opts.coldRestore.native_session_uuid;
                await conn.loadSession({cwd:this.opts.cwd,sessionId:finalId,mcpServers:[]});
                if (createHash("sha256").update(finalId,"utf8").digest("hex") !== this.opts.coldRestore.session_sha256)
                    throw Error("COLD_SDK_SID_CHANGED_DURING_LOAD");
            } else {
                const ns = await conn.newSession({ cwd: this.opts.cwd, mcpServers: [] });
                finalId = ns.sessionId;
            }''')
    replace(c,'            this.turnId = turn.turn_id;','''            if (this.opts.coldRestore !== undefined && turn.turn_id !== this.opts.coldRestore.native_turn)
                throw Error("COLD_SDK_ORIGINAL_TURN_CHANGED");
            this.turnId = turn.turn_id;''')
    replace(c,'            this.freshContextPending = true;','            this.freshContextPending = this.opts.coldRestore === undefined;')
    # Fail before any state-store queue reset. Fresh startup remains original.
    replace(m,'    const store = new EventStore(env.mysqlDsn, identity.username);','''    const coldRestore = await readColdRestore();
    const store = new EventStore(env.mysqlDsn, identity.username);''')
    replace(m,'    if (!isChecker)\n','    if (!isChecker && coldRestore === undefined)\n')
    replace(m,'    const recovered = await store.recoverSendingToPending(env.agent);','    const recovered = coldRestore === undefined ? await store.recoverSendingToPending(env.agent) : 0;')
    replace(m,'        budgetPauseClock,','        budgetPauseClock,\n        coldRestore,')
    replace(m,'    const onWorkerRestart = (request) => {','''    if (coldRestore !== undefined) {
        await channel.preparePrompt();
        const route = JSON.parse(await readFile('/run/count14-dynteam/route.json','utf8'));
        await finishColdLoad(channel,coldRestore,route,registerCurrentNativeSession,store,env.agent);
    }
    const onWorkerRestart = (request) => {''')
    out[m]='''import {readColdRestore,finishColdLoad} from './sdk_restore_guest.mjs';
import {registerCurrentNativeSession} from '/app/count14/router-session-hook.mjs';
import {readFile} from 'node:fs/promises';
'''+out[m]
    proof[m].append(('',out[m][:out[m].index(originals[m].splitlines()[0])]))
    # Removing exactly the enumerated cold additions/replacements restores all
    # original bytes, including every prompt/scientific/header/default branch.
    for name in out:
        reverted=out[name]
        for old,new in reversed(proof[name]):
            need(reverted.count(new)==1,'SDK_RESTORE_UNIQUE_INVERSE_SELECTOR')
            reverted=reverted.replace(new,old,1)
        need(reverted==originals[name],'SDK_RESTORE_ALL_FRESH_NATIVE_SOURCE_BYTES_RESTORED')
    if bridge_path is not None:
        path=Path(bridge_path);raw=path.read_bytes()
        need(path.resolve()==path and not path.is_symlink()and hashlib.sha256(raw).hexdigest()==BRIDGE_SHA,'SDK_RESTORE_PINNED_ORIGINAL_GUARDED_BRIDGE')
        old='_count14_lifecycle = bridge_lifecycle()\n';addition='''from sdk_restore_bridge_guest import serve_if_cold as _serve_cold_sdk
if _serve_cold_sdk(server,sock_path=sock_path,child_cmd=child_cmd,child_popen_kwargs=_child_popen_kwargs,lifecycle=_count14_lifecycle):
    raise SystemExit(0)
'''
        source=raw.decode();need(source.count(old)==1,'SDK_RESTORE_ONE_BRIDGE_PRE_STARTUP_SELECTOR')
        candidate=source.replace(old,old+addition)
        need(candidate.replace(addition,'')==source,'SDK_RESTORE_BRIDGE_FRESH_BYTES_RESTORED')
        out['acp-bridge.py']=candidate
    return out,dict(schema='count14-formal-sdk-cold-overlay-proof-v1',
        original_channel_sha256=CHANNEL_SHA,original_main_sha256=MAIN_SHA,
        reverse_bytes_equal=True,selector_counts={k:len(v)for k,v in proof.items()},
        no_prompt_model_header_or_fresh_dispatch_formula_changed=True,
        bridge_original_sha256=BRIDGE_SHA if bridge_path is not None else None,
        bridge_cold_path_preserves_original_turn_and_files_no_cleanup=True,
        cold_load_uses_normal_ACP_loadSession=True,cold_queues_not_reset_or_replayed=True,
        prospective_not_installed_or_SDK_qualified=True)


def build(destination):
    import json,os
    here=Path(__file__).resolve().parent;frozen=here.parent/'racing-complete-cold-tree-v4-msg237-held20-v1-msg237-prefix21-v1'
    dist=frozen/'native-clock-overlay-v1/dist';bridge=frozen/'native-guarded-control-source-v2/acp-bridge.py'
    sources,proof=compile_overlay(dist/'acp_socket_channel.js',dist/'main.js',bridge)
    sources['sdk_restore_guest.mjs']=(here/'sdk_restore_guest.mjs').read_text()
    sources['sdk_restore_bridge_guest.py']=(here/'sdk_restore_bridge_guest.py').read_text()
    dest=Path(destination);need(dest.is_absolute()and dest.parent.resolve()==dest.parent and
        dest.is_relative_to(here)and not dest.exists(),'SDK_RESTORE_NEW_CODE_ONLY_OVERLAY_DIRECTORY')
    dest.mkdir(mode=0o755);files={}
    for name,value in sources.items():
        raw=value.encode();p=dest/name
        with p.open('xb')as handle:handle.write(raw);handle.flush();os.fsync(handle.fileno())
        p.chmod(0o555 if name=='acp-bridge.py'else 0o444);files[name]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    manifest=dict(schema='count14-formal-cold-sdk-prospective-code-overlay-v1',files=files,proof=proof,
        installed=False,actual_SDK_restore_qualified=False,whole_cold_owner_restore_qualified=False)
    p=dest/'CODE_MAP_PUBLIC.json';p.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n');p.chmod(0o444)
    return dict(path=str(dest),manifest_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),**manifest)


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser();parser.add_argument('--destination',required=True);args=parser.parse_args()
    print(json.dumps(build(args.destination),sort_keys=True))
