"""Byte-pinned original native board+notice shim with control-only completion fd.

No tool description, task/candidate/prompt content or service behavior is changed.
A dedicated trusted FD reports completion only after the original notice chain
(including shown acknowledgement) finishes. Unknown notice HTTP outcomes remain
unknown; the hook never changes the model-visible native response or retries.
"""
from pathlib import Path
import hashlib,json
from common import need,hash_file,publish,wire
BASE=Path(__file__).resolve().parent
PUBLIC=BASE.parent/'operations-agensh-comparison-20261026/native-public-text105-transfer-v1/source'

def build_overlay(destination):
 destination=Path(destination);need(destination.is_absolute()and destination.resolve()==destination and not destination.exists(),'MCP_OVERLAY_NEW_ROOT');destination.mkdir(mode=0o700)
 pins={r['path']:r['sha256']for r in json.loads((BASE/'NATIVE_PUBLIC105_CONSUMED.json').read_text())['sources']};files={}
 for relative,name in [('board-service/mcp.cjs','mcp-board.cjs'),('mini-router/mcp-notice-shim.cjs','mcp-notice-shim.cjs'),('agent/config/copilot-deny-tools.json','copilot-deny-tools.json')]:
  raw=(PUBLIC/relative).read_bytes();need(hashlib.sha256(raw).hexdigest()==pins[relative],'MCP_PUBLIC_NATIVE_SOURCE_CHANGED');files[name]={'original_path':relative,'original_sha256':pins[relative]}
  if name=='mcp-notice-shim.cjs':
   text=raw.decode();replacements=[
    ('const child = spawn(argv[0], argv.slice(1), { stdio: ["pipe", "pipe", "inherit"] });', '''// Independent count14 metadata-only host control. Never written to stdout.
const controlFs = require("node:fs");
const controlCrypto = require("node:crypto");
const controlFD = Number(process.env.AGENSH_MCP_CONTROL_FD);
if (!Number.isSafeInteger(controlFD) || controlFD < 3) throw new Error("MCP_CONTROL_FD_REQUIRED");
const child = spawn(argv[0], argv.slice(1), { stdio: ["pipe", "pipe", "inherit"] });
let controlNoticeUnknown = false;
function controlTextMetadata(message) {
    const content = message && message.result && message.result.content;
    if (!Array.isArray(content)) return {content_count:null, prefixes:[]};
    const prefixes = [];
    for (let index = 0; index < content.length; index++) {
        const item = content[index];
        if (item && item.type === "text" && typeof item.text === "string") {
            prefixes.push({index, bytes:Buffer.byteLength(item.text, "utf8"),
                sha256:controlCrypto.createHash("sha256").update(item.text, "utf8").digest("hex")});
        }
    }
    return {content_count:content.length, prefixes};
}
function controlDone(id, method, error, nativeText) {
    controlFs.writeSync(controlFD, JSON.stringify({schema:"agensh-native-mcp-terminal-v1", id, method,
        notice_unknown:controlNoticeUnknown, rpc_error:!!error, native_text:nativeText}) + "\\n");
}'''),
    ('if (res.statusCode >= 400) return resolve(null);','if (res.statusCode >= 400) { controlNoticeUnknown = true; return resolve(null); }'),
    ('try { resolve(JSON.parse(body)); } catch { resolve(null); }','try { resolve(JSON.parse(body)); } catch { controlNoticeUnknown = true; resolve(null); }'),
    ('req.on("error", () => resolve(null));','req.on("error", () => { controlNoticeUnknown = true; resolve(null); });'),
    ('req.setTimeout(timeoutMs, () => { req.destroy(); resolve(null); });','req.setTimeout(timeoutMs, () => { controlNoticeUnknown = true; req.destroy(); resolve(null); });'),
    ('(res) => { res.on("end", resolve); res.on("close", resolve); res.on("error", resolve); res.resume(); });','(res) => { if (res.statusCode >= 400) controlNoticeUnknown = true; let ended = false; res.on("end", () => { ended = true; resolve(); }); res.on("close", () => { if (!ended) controlNoticeUnknown = true; resolve(); }); res.on("error", () => { controlNoticeUnknown = true; resolve(); }); res.resume(); });'),
    ('req.on("error", resolve);','req.on("error", () => { controlNoticeUnknown = true; resolve(); });'),
    ('req.setTimeout(1500, () => { req.destroy(); resolve(); });','req.setTimeout(1500, () => { controlNoticeUnknown = true; req.destroy(); resolve(); });'),
    ('chain = chain.then(() => handleUpstreamLine(line));','''chain = chain.then(async () => {
            let controlMessage = null;
            try { controlMessage = JSON.parse(line); } catch (_) {}
            const controlMethod = controlMessage && methodById.get(controlMessage.id);
            const nativeText = controlTextMetadata(controlMessage);
            controlNoticeUnknown = false;
            await handleUpstreamLine(line);
            if (controlMessage && controlMessage.id != null && controlMethod) {
                controlDone(controlMessage.id, controlMethod,
                    controlMessage.error || (controlMessage.result && controlMessage.result.isError), nativeText);
            }
        });''')]
   for old,new in replacements:need(text.count(old)==1,'MCP_NATIVE_HOOK_SHAPE');text=text.replace(old,new)
   raw=text.encode();files[name]['control_only_replacement_count']=len(replacements)
  publish(destination/name,raw,mode=0o400);files[name]['installed']=hash_file(destination/name)
 receipt={'schema':'agensh-native-mcp-host-overlay-v1','scope':'native board and notice shim; control fd only, no tool/prompt/result semantic rewrite','files':files,'native_text_prefix_integrity':True};publish(destination/'origin.json',wire(receipt),mode=0o400);return receipt
