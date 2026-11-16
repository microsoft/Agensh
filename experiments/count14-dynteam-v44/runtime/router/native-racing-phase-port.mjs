/** Private SCIENTIFIC ACP port; never a public diagnostic/body exporter.
 * Original ACPSocketChannel bytes/methods remain unchanged. A same-directory
 * byte-for-byte proxy observes native session/update chunks inside this runtime.
 * Parse/capture failure never aborts, closes or retries an admitted model call.
 */
import net from 'node:net';
import http from 'node:http';
import { StringDecoder } from 'node:string_decoder';
import { openSync, closeSync, fstatSync, writeSync, fsyncSync, lstatSync, realpathSync, constants } from 'node:fs';
import { lstat, readFile, realpath, readlink } from 'node:fs/promises';
import { dirname, resolve, join } from 'node:path';
import { timingSafeEqual, createHash } from 'node:crypto';
import { registerCurrentNativeSession } from './router-session-hook.mjs';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function need(ok, code) { if (!ok) throw new Error(code); }


const OWNED_INFRA_GUARDS = new Set(["DYNTEAM_SESSION_READY_UNSTARTED_RESUBMIT_EXHAUSTED_RETAIN","DYNTEAM_SESSION_READY_SAME_IDENTITY_BEFORE_CONTROL_RESUBMIT","DYNTEAM_ACTUAL_ORIGINAL_CHANNEL_SESSION_AND_SOCKET", "DYNTEAM_BOUNDED_METADATA_FILE_READ_TIMEOUT", "DYNTEAM_BOUNDED_METADATA_TIMEOUT", "DYNTEAM_BOUNDED_NORMAL_RECONNECT_CONTROL_TIMEOUT", "DYNTEAM_BOUNDED_SESSION_READY_CONTROL_TIMEOUT", "DYNTEAM_CHANNEL_CHANGED_DURING_CONTROL_RECEIPT", "DYNTEAM_CHANNEL_NATIVE_TURN_EXACT", "DYNTEAM_COLD_ROUTER_PRELOAD_FAILED_NO_RETRY", "DYNTEAM_COLD_ROUTE_SCHEMA_SOURCE", "DYNTEAM_CONTROL_DIGEST", "DYNTEAM_CONTROL_EXACT_ACK", "DYNTEAM_CONTROL_RECEIPT_UNAVAILABLE", "DYNTEAM_CONTROL_RESPONSE_BOUND", "DYNTEAM_CONTROL_TIMEOUT", "DYNTEAM_EXACT_NATIVE_TURN_METADATA_FILE", "DYNTEAM_EXACT_ORIGINAL_NATIVE_TURN_METADATA_ROUTE", "DYNTEAM_EXACT_PUBLIC_ROUTER_ROUTE", "DYNTEAM_FROZEN_NATIVE_MODULE_PIN", "DYNTEAM_IMAGE_ORIGINAL_NATIVE_DIST", "DYNTEAM_METADATA_READ_TIMEOUT", "DYNTEAM_NATIVE_DIST_CANONICAL", "DYNTEAM_NATIVE_MODULE_NO_SYMLINK", "DYNTEAM_NATIVE_PHASE_CLOCK_EXACT_ROLE_MOUNT", "DYNTEAM_NATIVE_PHASE_EXACT_QUALIFIED120_READER", "DYNTEAM_NATIVE_PHASE_ORIGINAL_CLOCK_BINDING_REQUIRED", "DYNTEAM_NATIVE_TURN_CONTROL_FIELDS", "DYNTEAM_NATIVE_TURN_METADATA_CHANGED", "DYNTEAM_NATIVE_TURN_METADATA_UNAVAILABLE", "DYNTEAM_ORIGINAL_MAIN_ACP_SOCKET_ROUTE_MATCH", "DYNTEAM_ORIGINAL_NATIVE_SENDTEXT_SINGLE_PRELOAD", "DYNTEAM_OWN_ZERO_NEVER_STARTS_NATIVE_MAIN", "DYNTEAM_RACING_CAPTURE_NEW_SESSION_NO_ACTIVE_TOOLS", "DYNTEAM_RACING_EXACT_NATIVE_PRIVATE_PROXY", "DYNTEAM_RACING_EXACT_PREREGISTERED_TURN_ALIAS_BEFORE_PRODUCER", "DYNTEAM_RACING_FIRST_ZERO_PREPARE_NO_OLD_TURN_OR_TOOL", "DYNTEAM_RACING_FROZEN_PRIVATE_ENTRY_ROUTE", "DYNTEAM_RACING_NATIVE_AGENT_SOCKET_BIRTH_CHANGED", "DYNTEAM_RACING_NATIVE_CLOCK_HELD_UNADMITTED", "DYNTEAM_RACING_NATIVE_CLOSE_RETAIN_UNPROVEN_PHYSICAL_WORK", "DYNTEAM_RACING_NATIVE_ENTRY_EXACT_ARGUMENT", "DYNTEAM_RACING_NATIVE_ENTRY_FAILED_RETAIN", "DYNTEAM_RACING_NATIVE_PHASE_CAPTURE_UNPROVEN", "DYNTEAM_RACING_NATIVE_PHASE_EXACT_PHYSICAL_PROOF", "DYNTEAM_RACING_NATIVE_PHASE_FAILED_RETAIN_NO_REPLAY", "DYNTEAM_RACING_NATIVE_PHASE_HELD_UNADMITTED", "DYNTEAM_RACING_NATIVE_PHASE_PHYSICAL_CUSTODY_UNPROVEN", "DYNTEAM_RACING_NATIVE_PHASE_PHYSICAL_PROOF_UNAVAILABLE", "DYNTEAM_RACING_NATIVE_PHASE_RETAINED_NOT_RETIRABLE", "DYNTEAM_RACING_NATIVE_PHASE_RETAIN_NO_REPLAY", "DYNTEAM_RACING_NATIVE_PHASE_SERIAL_NO_REPLAY", "DYNTEAM_RACING_NATIVE_PREVIOUS_PHASE_NOT_PHYSICALLY_PROVEN", "DYNTEAM_RACING_NATIVE_PROXY_CANONICAL_PARENT", "DYNTEAM_RACING_NATIVE_PROXY_START_ONCE", "DYNTEAM_RACING_ORIGINAL_ACP_SOCKET_REQUIRED", "DYNTEAM_RACING_ORIGINAL_TURN_METADATA_ALIAS_EXACT", "DYNTEAM_RACING_PRIVATE_ENTRY_EXACT_MOUNT", "DYNTEAM_RACING_PRIVATE_REQUEST_BOUND", "DYNTEAM_RACING_PRIVATE_RPC_BEARER_LENGTH", "DYNTEAM_RACING_PRIVATE_RPC_BEARER_OWNER_MODE", "DYNTEAM_RACING_PRIVATE_RPC_CANONICAL_PARENT", "DYNTEAM_RACING_PRIVATE_RPC_EXACT_ROLE", "DYNTEAM_RACING_PRIVATE_RPC_REFUSED", "DYNTEAM_RACING_UNUSED_ZERO_MODEL_SESSION_EXACT_AT_PREFLIGHT", "DYNTEAM_RACING_UNUSED_ZERO_MODEL_SESSION_EXACT_BEFORE_PROMPT", "DYNTEAM_RACING_ZERO_MODEL_PREPARED_ORIGINAL_PHYSICAL_BOUNDARY", "DYNTEAM_RACING_ZERO_MODEL_PREPARE_FAILED_RETAIN", "DYNTEAM_RACING_ZERO_MODEL_PREPARE_ORIGINAL_PHYSICAL_BOUNDARY", "DYNTEAM_RACING_ZERO_MODEL_PREPARE_SERIAL", "DYNTEAM_RECONNECT_CHANNEL_UNCHANGED_AFTER_TRUE_ACK", "DYNTEAM_RECONNECT_EXACT_OLD_CONNECTION_TURN_AND_SID", "DYNTEAM_RECONNECT_GUARDED_ORIGINAL_CLOSE_MUST_REALLY_DISCONNECT", "DYNTEAM_RECONNECT_NO_CONCURRENT_PROMPT_OR_INIT", "DYNTEAM_RECONNECT_NO_SECOND_CLOSE_OR_INIT", "DYNTEAM_RECONNECT_ORIGINAL_SAME_ACCOUNT_LIFECYCLE_METHODS", "DYNTEAM_RECONNECT_PARTIAL_RETAINED", "DYNTEAM_RETIRED_ROUTER_EXACT_CURRENT_TURN_AND_ACCOUNT", "DYNTEAM_RETIRED_ROUTER_HOLD_SINGLE_PRELOAD", "DYNTEAM_RETIRED_ROUTER_ONLY_ORIGINAL_BOUND_END_TURN", "DYNTEAM_RETIRED_ROUTER_QUIESCENCE_MUST_NOT_RETURN", "DYNTEAM_ROUTER_ENTRY_EXACT_ARGUMENTS", "DYNTEAM_ROUTE_CANONICAL", "DYNTEAM_SESSION_CONTROL_PARTIAL_OR_CONCURRENT_RETAIN"]);

function noteOwnedPhaseInfra(port, phase, error) {
  // Error observer ONLY. Never log parts, text/thinking, tool input/output,
  // session/request IDs, secrets, or an arbitrary upstream error message.
  let fd;
  try {
    const stage = port._ownedPhaseStage ?? 'UNKNOWN';
    const code = OWNED_INFRA_GUARDS.has(error?.message)
      ? error.message : 'UNAVAILABLE_NOT_AN_OWNED_GUARD';
    const kind = typeof error?.name === 'string' && /^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(error.name)
      ? error.name : 'OTHER';
    const phaseName = ['background','submit','review','defend','prepare-zero-model','setup-completion'].includes(phase) ? phase : 'OTHER';
    const key = `${phaseName}:${stage}:${code}`;
    port._ownedPhaseInfraSeen ??= new Set();
    if (port._ownedPhaseInfraSeen.has(key) || port._ownedPhaseInfraSeen.size >= 32) return;
    const directory = dirname(port.route.native_acp_socket);
    const parent = lstatSync(directory);
    if (!parent.isDirectory() || realpathSync(directory) !== directory ||
        parent.uid !== process.getuid() || (parent.mode & 0o022)) return;
    fd = openSync(join(directory, 'NATIVE_PHASE_INFRA_PUBLIC.jsonl'),
      constants.O_WRONLY | constants.O_APPEND | constants.O_CREAT | constants.O_NOFOLLOW, 0o600);
    const node = fstatSync(fd);
    if (!node.isFile() || node.nlink !== 1 || node.uid !== process.getuid() || (node.mode & 0o777) !== 0o600) return;
    const value = {schema:'count14-native-racing-owned-phase-infra-diagnostic-v2',
      role:port.route.role_slot, phase:phaseName, stage, error_type:kind, owned_guard_code:code,
      before_models_clear:typeof port._ownedBeforeModels === 'boolean' ? port._ownedBeforeModels : null,
      before_tools_clear:typeof port._ownedBeforeTools === 'boolean' ? port._ownedBeforeTools : null,
      native_error_code: ['ECONNRESET','ETIMEDOUT','ECONNREFUSED','EPIPE','ENOENT','EACCES','EPERM'].includes(error?.code) ? error.code : null,
      json_rpc_error_code: Number.isSafeInteger(error?.code) && Math.abs(error.code) <= 65536 ? error.code : null,
      busy:port.busy === true, retained:port.retained === true, stopping:port.stopping === true,
      tap_failed:port.tap?.failed === true, pending_tap_tools:port.tap?.tools?.size ?? null,
      session_present:typeof port.channel?.sessionId === 'string',
      unadmitted:error?.unadmitted === true, no_model_or_physical_terminal_claim:true};
    const row = JSON.stringify(value) + '\n';
    if (writeSync(fd, row) === Buffer.byteLength(row)) port._ownedPhaseInfraSeen.add(key);
  } catch { /* Missing observer never changes original admission/custody. */ }
  finally { if (fd !== undefined) { try { closeSync(fd); } catch {} } }
}


function retainOriginalHandshakeInfraError(port, site, error) {
  // msg213/214: this exact original WARN is emitted ONLY during ACP
  // connect/initialize/newSession, BEFORE any prompt/body is submitted.
  // Keep the actual infrastructure message and stack; never args/cause/env,
  // headers, prompt parts, session updates, tools or RX log data.
  let fd;
  try {
    if (!error || port._ownedOriginalPromptStarted === true ||
        !(typeof site === 'string' &&
          (/^connect attempt [1-6] failed; sleeping [0-9]+ms$/.test(site) ||
           site === 'new session on the live connection failed; reconnecting'))) return;
    if ((port._originalHandshakeErrors ?? 0) >= 16) return;
    const directory = dirname(port.route.native_acp_socket);
    const parent = lstatSync(directory);
    if (!parent.isDirectory() || realpathSync(directory) !== directory ||
        parent.uid !== process.getuid() || (parent.mode & 0o022)) return;
    fd = openSync(join(directory, 'ORIGINAL_HANDSHAKE_INFRA_ERRORS.jsonl'),
      constants.O_WRONLY | constants.O_APPEND | constants.O_CREAT | constants.O_NOFOLLOW, 0o600);
    const node = fstatSync(fd);
    if (!node.isFile() || node.nlink !== 1 || node.uid !== process.getuid() || (node.mode & 0o777) !== 0o600) return;
    const value = {
      schema:'count14-original-preprompt-handshake-infrastructure-error-v1',
      role:port.route.role_slot, original_fixed_warning_site:site,
      exception_type:typeof error.name === 'string' ? error.name.slice(0,128) : null,
      original_infra_message:typeof error.message === 'string' ? error.message.slice(0,8192) : null,
      original_infra_stack:typeof error.stack === 'string' ? error.stack.slice(0,16384) : null,
      no_prompt_submitted:true, no_args_cause_env_headers_or_RX_exported:true,
    };
    const row = JSON.stringify(value) + '\n';
    if (writeSync(fd,row) === Buffer.byteLength(row)) port._originalHandshakeErrors = (port._originalHandshakeErrors ?? 0)+1;
  } catch { /* Observation failures never affect the original phase. */ }
  finally { if (fd !== undefined) { try { closeSync(fd); } catch {} } }
}

export class PrivateCaptureTap {
  constructor({ maximumFrameBytes = 16 * 1024 * 1024, maximumTextBytes = 4 * 1024 * 1024 } = {}) {
    this.maximumFrameBytes = maximumFrameBytes;
    this.maximumTextBytes = maximumTextBytes;
    this.decoder = new StringDecoder('utf8');
    this.buffer = ''; this.discard = false; this.session = null;
    this.text = ''; this.thinking = ''; this.failed = false; this.tools = new Set();
  }
  begin(session) {
    need(UUID.test(session) && this.tools.size === 0, 'DYNTEAM_RACING_CAPTURE_NEW_SESSION_NO_ACTIVE_TOOLS');
    this.session = session; this.text = ''; this.thinking = ''; this.failed = false;
  }
  ingest(chunk) {
    // Observation only. The caller ALWAYS forwards original bytes regardless
    // of parse/capture limits; these flags can only retain/fault the result.
    const data = this.decoder.write(chunk);
    const lines = data.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const piece = lines[i];
      const complete = i < lines.length - 1;
      if (!this.discard) {
        if (Buffer.byteLength(this.buffer) + Buffer.byteLength(piece) > this.maximumFrameBytes) {
          this.failed = true; this.buffer = ''; this.discard = true;
        } else this.buffer += piece;
      }
      if (complete) {
        if (!this.discard && this.buffer) this.frame(this.buffer);
        this.buffer = ''; this.discard = false;
      }
    }
  }
  frame(line) {
    let message;
    try { message = JSON.parse(line); } catch { this.failed = true; return; }
    if (message?.method !== 'session/update') return;
    const params = message.params;
    if (!params || params.sessionId !== this.session) return;
    const update = params.update;
    if (!update || typeof update.sessionUpdate !== 'string') { this.failed = true; return; }
    const kind = update.sessionUpdate;
    if (kind === 'agent_message_chunk' || kind === 'agent_thought_chunk') {
      if (update.content?.type !== 'text' || typeof update.content.text !== 'string') return;
      const field = kind === 'agent_message_chunk' ? 'text' : 'thinking';
      if (Buffer.byteLength(this.text) + Buffer.byteLength(this.thinking) + Buffer.byteLength(update.content.text) > this.maximumTextBytes) {
        this.failed = true; return;
      }
      this[field] += update.content.text;
    } else if (kind === 'tool_call' || kind === 'tool_call_update') {
      // Only framework control fields; never tool arguments, title or result.
      const id = update.toolCallId, status = update.status;
      if (typeof id !== 'string' || id.length > 256) { this.failed = true; return; }
      if (status === 'completed' || status === 'failed') this.tools.delete(id);
      else if (status === 'pending' || status === 'in_progress') this.tools.add(id);
      else if (kind === 'tool_call') this.tools.add(id);
    }
  }
}

export class NativeRacingPhasePort {
  constructor({ Channel, route, physicalProof, budgetPauseClock }) {
    need(typeof Channel === 'function' && typeof physicalProof === 'function' &&
      /^(racing-background-00|racing-player-0[0-6])$/.test(route.role_slot) &&
      route.native_acp_socket !== route.native_agent_socket,
      'DYNTEAM_RACING_EXACT_NATIVE_PRIVATE_PROXY');
    this.route = Object.freeze({ ...route }); this.proof = physicalProof;
    this.tap = new PrivateCaptureTap(); this.clients = new Set(); this.upstreams = new Set();
    this.busy = false; this.retained = false; this.started = false; this.stopping = false;
    this.unusedPreparedSession = null;
    this.backgroundPromptCount = 0; this.completedFirstBackground = null;
    this.budgetPauseClock = budgetPauseClock;
    this.channel = new Channel({ socketPath: route.native_acp_socket, cwd: '/work', stuckMs: 0,
      budgetPauseClock, onLog: (level, message, error) => {
        // Original channel info includes raw RX bytes: NEVER forward/log them.
        // Only these original fixed connect/reconnect WARN sites are observed.
        if (typeof message === 'string' &&
            (/^connect attempt [1-6] failed; sleeping [0-9]+ms$/.test(message) ||
             message === 'new session on the live connection failed; reconnecting')) {
          this._ownedPhaseStage = message.startsWith('connect attempt') ? 'CHANNEL_CONNECT_WARNING' : 'CHANNEL_NEW_SESSION_WARNING';
          noteOwnedPhaseInfra(this, this._ownedPhaseName ?? 'OTHER', error);
          retainOriginalHandshakeInfraError(this, message, error);
        }
      } });
    // The original method may close on an ACP error. Guard this INSTANCE, not
    // its source/class, so an unproven SENT model/tool cannot be cancelled.
    const close = this.channel.close.bind(this.channel);
    this.channel.close = async () => {
      const proof = await this.proof(this.channel.sessionId ?? null);
      need(proof?.models_clear === true && proof?.tools_clear === true && this.tap.tools.size === 0,
        'DYNTEAM_RACING_NATIVE_CLOSE_RETAIN_UNPROVEN_PHYSICAL_WORK');
      return close();
    };
  }
  async startProxy() {
    need(!this.started, 'DYNTEAM_RACING_NATIVE_PROXY_START_ONCE');
    for (const path of [this.route.native_acp_socket, this.route.native_agent_socket]) {
      need(resolve(path) === path && await realpath(dirname(path)) === dirname(path),
        'DYNTEAM_RACING_NATIVE_PROXY_CANONICAL_PARENT');
    }
    const agent = await lstat(this.route.native_agent_socket);
    need(agent.isSocket(), 'DYNTEAM_RACING_ORIGINAL_ACP_SOCKET_REQUIRED');
    if (dirname(this.route.native_acp_socket) !== dirname(this.route.native_agent_socket)) {
      const source = join(dirname(this.route.native_agent_socket), 'current-turn.json');
      const alias = join(dirname(this.route.native_acp_socket), 'current-turn.json');
      const node = await lstat(alias);
      const target = await readlink(alias);
      need(this.route.native_turn_metadata === source && node.isSymbolicLink() &&
        (target === source || (source === '/run/acp/current-turn.json' &&
          target === '/var/run/acp/current-turn.json')),
        'DYNTEAM_RACING_EXACT_PREREGISTERED_TURN_ALIAS_BEFORE_PRODUCER');
      // The first original ACP connection produces the real marker. Never
      // fabricate a placeholder or weaken its full guard before any prompt.
    }
    this.agentIdentity = [agent.dev, agent.ino, agent.uid, agent.gid];
    this.server = net.createServer(client => {
      this.clients.add(client);
      const upstream = net.createConnection(this.route.native_agent_socket);
      this.upstreams.add(upstream);
      upstream.on('data', data => {
        try { this.tap.ingest(data); } catch { this.tap.failed = true; }
      });
      upstream.on('error', () => { this.tap.failed = true; });
      client.on('error', () => { this.retained = true; });
      client.on('close', () => this.clients.delete(client));
      upstream.on('close', () => this.upstreams.delete(upstream));
      client.pipe(upstream); upstream.pipe(client);
    });
    await new Promise((ok, bad) => {
      this.server.once('error', bad); this.server.listen(this.route.native_acp_socket, ok);
    });
    this.started = true;
  }
  async verifyTurnMetadataAlias() {
    if (dirname(this.route.native_acp_socket) !== dirname(this.route.native_agent_socket)) {
      const source = join(dirname(this.route.native_agent_socket), 'current-turn.json');
      const alias = join(dirname(this.route.native_acp_socket), 'current-turn.json');
      const metadata = await lstat(source);
      need(this.route.native_turn_metadata === source && metadata.isFile() && !metadata.isSymbolicLink() &&
        await realpath(alias) === await realpath(source), 'DYNTEAM_RACING_ORIGINAL_TURN_METADATA_ALIAS_EXACT');
      // Only a new private export contains the proxy/alias. Original ACP mount
      // remains read-only, with native UID unchanged and no privilege increase.
    }
  }
  preparedSessionStillExact() {
    const value = this.unusedPreparedSession;
    return value !== null && value.session === this.channel.sessionId &&
      value.connection === this.channel.connection && value.turn === this.channel.turnId &&
      this.tap.session === value.session && this.tap.tools.size === 0 && !this.tap.failed;
  }
  consumeSetupCompletionIntent(anchor) {
    const directory = dirname(this.route.native_acp_socket);
    const parent = lstatSync(directory);
    need(this.route.role_slot === 'racing-background-00' && anchor === this.completedFirstBackground &&
      anchor?.stopReason === 'end_turn' && anchor.first === true &&
      parent.isDirectory() && realpathSync(directory) === directory &&
      parent.uid === process.getuid() && !(parent.mode & 0o022),
      'RACING_SETUP_COMPLETION_EXACT_ORIGINAL_ROLE_AND_PERSISTENT_CONTROL');
    const path = join(directory, 'RACING_SETUP_COMPLETION_PUBLIC.json');
    let fd;
    try { fd = openSync(path, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o400); }
    catch (error) {
      if (error?.code === 'EEXIST') throw new Error('RACING_SETUP_COMPLETION_ALREADY_USED_NO_REPLAY');
      throw error;
    }
    try {
      const state = {schema:'count14-racing-router-setup-completion-once-public-v1',
        authority:'CARETAKER_USER_APPROVE_ONE_BOUNDED_PAID_RACING_SETUP_COMPLETION',
        approved_proposal_sha256:'c44c0eeaecad6a306e1a7396b12a6f5700d11390a0e740fc57df6c88c77857a7',
        role:this.route.role_slot, trigger_count:1, used_per_trajectory:true,
        stage:'DURABLE_INTENT_BEFORE_ORIGINAL_SAME_SID_TURN_PROMPT_NO_REPLAY',
        original_background_normal_end_turn:true, original_receipts_physical_terminal:true,
        all_calls_charged_SEARCH:true};
      const raw = Buffer.from(JSON.stringify(state)+'\n');
      need(writeSync(fd,raw) === raw.length, 'RACING_SETUP_COMPLETION_DURABLE_COMPLETE_WRITE');
      fsyncSync(fd);
    } finally { closeSync(fd); }
    const parentFD = openSync(directory, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW);
    try {
      const current = fstatSync(parentFD);
      need(current.dev === parent.dev && current.ino === parent.ino,
        'RACING_SETUP_COMPLETION_PERSISTENT_CONTROL_DIRECTORY_IDENTITY');
      fsyncSync(parentFD);
    } finally { closeSync(parentFD); }
  }
  async run(parts, phase, setupResume = null) {
    this._ownedPhaseStage = 'SERIAL_ENTRY';
    this._ownedPhaseName = phase; this._ownedBeforeModels = null; this._ownedBeforeTools = null;
    this._ownedOriginalPromptStarted = false;
    need(this.started && !this.busy && !this.retained && !this.stopping &&
      ['background', 'submit', 'review', 'defend', 'setup-completion'].includes(phase) && Array.isArray(parts) &&
      parts.every(p => p?.type === 'text' && typeof p.text === 'string'),
      'DYNTEAM_RACING_NATIVE_PHASE_SERIAL_NO_REPLAY');
    const completing = phase === 'setup-completion';
    const anchor = this.completedFirstBackground;
    if (completing) need(this.route.role_slot === 'racing-background-00' &&
      this.backgroundPromptCount === 1 && anchor?.first === true && anchor.stopReason === 'end_turn' &&
      setupResume && Object.keys(setupResume).sort().join(',') === 'session,turn' &&
      setupResume.session === anchor.session && setupResume.turn === anchor.turn &&
      this.channel.sessionId === anchor.session && this.channel.turnId === anchor.turn &&
      this.channel.connection === anchor.connection && this.channel.connection !== null &&
      this.unusedPreparedSession === null && this.tap.session === anchor.session && !this.tap.failed,
      'RACING_SETUP_COMPLETION_ONLY_EXACT_FIRST_NORMAL_BACKGROUND_SID_TURN_CONNECTION');
    else need(setupResume === null, 'RACING_SETUP_COMPLETION_NOT_A_GENERAL_RESUME_PORT');
    this.busy = true;
    try {
      this._ownedPhaseStage = 'BEFORE_PHYSICAL_PROOF';
      const before = await this.proof(this.channel.sessionId ?? null);
      this._ownedBeforeModels = before?.models_clear ?? null;
      this._ownedBeforeTools = before?.tools_clear ?? null;
      if (before?.models_clear === false || before?.tools_clear === false) {
        const hold = new Error('DYNTEAM_RACING_NATIVE_PHASE_HELD_UNADMITTED');
        hold.unadmitted = true; throw hold;
      }
      need(before?.models_clear === true && before?.tools_clear === true,
        'DYNTEAM_RACING_NATIVE_PREVIOUS_PHASE_NOT_PHYSICALLY_PROVEN');
      this._ownedPhaseStage = 'BEFORE_BUDGET_CLOCK';
      try { this.budgetPauseClock?.assertReadyForPrompt(); }
      catch {
        // Unknown control clock before admission is a HOLD, not a model
        // failure or permission to create another session/replay a prompt.
        const hold = new Error('DYNTEAM_RACING_NATIVE_CLOCK_HELD_UNADMITTED');
        hold.unadmitted = true; throw hold;
      }
      this._ownedPhaseStage = 'AGENT_SOCKET_BINDING';
      const stat = await lstat(this.route.native_agent_socket);
      need(stat.isSocket() && [stat.dev, stat.ino, stat.uid, stat.gid].every((v, i) => v === this.agentIdentity[i]),
        'DYNTEAM_RACING_NATIVE_AGENT_SOCKET_BIRTH_CHANGED');
      // Real original method, including first initialize/newSession handshake.
      // Every distinct phase/parse continuation remains stateless like Thinker.
      this._ownedPhaseStage = 'FRESH_SESSION';
      if (completing) {
        need(this.channel.sessionId === anchor.session && this.channel.turnId === anchor.turn &&
          this.channel.connection === anchor.connection && this.tap.tools.size === 0,
          'RACING_SETUP_COMPLETION_NEVER_FRESH_OR_REPLACEMENT_SESSION');
      } else if (this.unusedPreparedSession === null) {
        await this.channel.freshSession();
      } else {
        need(this.preparedSessionStillExact(), 'DYNTEAM_RACING_UNUSED_ZERO_MODEL_SESSION_EXACT_BEFORE_PROMPT');
      }
      this._ownedPhaseStage = 'TURN_METADATA_ALIAS';
      await this.verifyTurnMetadataAlias();
      const session = this.channel.sessionId;
      // Consume once BEFORE the original prompt. No prepared session that
      // has carried a prompt may ever be reused by this preflight shortcut.
      this.unusedPreparedSession = null;
      this.tap.begin(session);
      this._ownedPhaseStage = 'ORIGINAL_PROMPT';
      if (completing) this.consumeSetupCompletionIntent(anchor);
      if (phase === 'background') this.backgroundPromptCount += 1;
      const turn = this.channel.turnId, connection = this.channel.connection;
      need(!completing || (connection === anchor.connection && session === anchor.session && turn === anchor.turn),
        'RACING_SETUP_COMPLETION_SAME_ORIGINAL_IDENTITY_AT_PROMPT');
      this._ownedOriginalPromptStarted = true;
      const result = await this.channel.promptText(parts.map(p => p.text).join(''));
      need(this.channel.sessionId === session && !this.tap.failed,
        'DYNTEAM_RACING_NATIVE_PHASE_CAPTURE_UNPROVEN');
      this._ownedPhaseStage = 'AFTER_PROMPT_PHYSICAL_PROOF';
      let proof = await this.proof(session);
      while (proof?.models_clear === false || proof?.tools_clear === false || this.tap.tools.size !== 0) {
        // Accepted work drains naturally. These are bounded metadata probes,
        // not another model call, transport abort or a held-lock capacity wait.
        await new Promise(ok => setTimeout(ok, 250));
        proof = await this.proof(session);
      }
      need(proof?.models_clear === true && proof?.tools_clear === true,
        'DYNTEAM_RACING_NATIVE_PHASE_PHYSICAL_CUSTODY_UNPROVEN');
      need(!completing || (this.channel.sessionId === session && this.channel.turnId === turn &&
        this.channel.connection === connection), 'RACING_SETUP_COMPLETION_IDENTITY_PRESERVED_AFTER_PHYSICAL_PROOF');
      if (phase === 'background' && this.backgroundPromptCount === 1)
        this.completedFirstBackground = Object.freeze({session,turn,connection,stopReason:result.stopReason,first:true});
      return { text: this.tap.text, thinking: this.tap.thinking, native_session_uuid: session, native_turn_id: turn,
        stop_reason: result.stopReason, original_relay_receipts_complete: true, physical_terminal: true,
        fresh_stateless_session: !completing, setup_same_session_turn: completing };
    } catch (error) {
      noteOwnedPhaseInfra(this, phase, error);
      if (error?.unadmitted === true) throw error;
      this.retained = true;
      // Do not close a socket/session, cancel, discard a model reservation, or
      // create another native turn. Owner retains original physical custody.
      throw new Error('DYNTEAM_RACING_NATIVE_PHASE_FAILED_RETAIN_NO_REPLAY');
    } finally { this.busy = false; }
  }
  async prepareZeroModel() {
    this._ownedPhaseStage = 'ZERO_SERIAL_ENTRY';
    this._ownedPhaseName = 'prepare-zero-model';
    this._ownedBeforeModels = null; this._ownedBeforeTools = null;
    this._ownedOriginalPromptStarted = false;
    need(this.started && !this.busy && !this.retained && !this.stopping,
      'DYNTEAM_RACING_ZERO_MODEL_PREPARE_SERIAL');
    this.busy = true;
    try {
      this._ownedPhaseStage = 'ZERO_CONNECTION_STATE';
      const firstConnection = this.channel.sessionId == null && !this.channel.connection;
      if (firstConnection) {
        need(this.tap.session == null && this.tap.tools.size === 0,
          'DYNTEAM_RACING_FIRST_ZERO_PREPARE_NO_OLD_TURN_OR_TOOL');
      } else {
        this._ownedPhaseStage = 'ZERO_BEFORE_PHYSICAL_PROOF';
        const before = await this.proof(this.channel.sessionId ?? null);
        this._ownedBeforeModels = before?.models_clear ?? null;
        this._ownedBeforeTools = before?.tools_clear ?? null;
        if (before?.models_clear === false || before?.tools_clear === false) {
          const hold = new Error('DYNTEAM_RACING_NATIVE_PHASE_HELD_UNADMITTED'); hold.unadmitted = true; throw hold;
        }
        need(before?.models_clear === true && before?.tools_clear === true,
          'DYNTEAM_RACING_ZERO_MODEL_PREPARE_ORIGINAL_PHYSICAL_BOUNDARY');
      }
      this._ownedPhaseStage = 'ZERO_AGENT_SOCKET_BINDING';
      const agent = await lstat(this.route.native_agent_socket);
      need(agent.isSocket() && [agent.dev, agent.ino, agent.uid, agent.gid].every((v, i) => v === this.agentIdentity[i]),
        'DYNTEAM_RACING_NATIVE_AGENT_SOCKET_BIRTH_CHANGED');
      // On a truly fresh connection the original bridge first authenticates
      // its actual agent peer, enforces BEFORE_CLEANUP's original physical and
      // opaque archive guards, and enforces CLI_BIRTH's original kernel/epoch
      // guards. A router-only pre-peer census cannot authorize the agent's
      // control ancestry. No model prompt is sent, and no guard returns green.
      if (this.unusedPreparedSession === null) {
        this._ownedPhaseStage = 'ZERO_ORIGINAL_FRESH_SESSION';
        await this.channel.freshSession();  // original initialize/newSession only
      } else {
        this._ownedPhaseStage = 'ZERO_UNUSED_SESSION_IDENTITY';
        need(this.preparedSessionStillExact(), 'DYNTEAM_RACING_UNUSED_ZERO_MODEL_SESSION_EXACT_AT_PREFLIGHT');
      }
      this._ownedPhaseStage = 'ZERO_TURN_METADATA_ALIAS';
      await this.verifyTurnMetadataAlias();
      this._ownedPhaseStage = 'ZERO_SESSION_READY_RECEIPT';
      const session = await registerCurrentNativeSession(this.channel, this.route);
      this._ownedPhaseStage = 'ZERO_PREPARED_PHYSICAL_PROOF';
      const prepared = await this.proof(session);
      this._ownedBeforeModels = prepared?.models_clear ?? null;
      this._ownedBeforeTools = prepared?.tools_clear ?? null;
      need(prepared?.models_clear === true && prepared?.tools_clear === true,
        'DYNTEAM_RACING_ZERO_MODEL_PREPARED_ORIGINAL_PHYSICAL_BOUNDARY');
      this._ownedPhaseStage = 'ZERO_CAPTURE_BEGIN';
      this.tap.begin(session);
      this.unusedPreparedSession = Object.freeze({session, connection:this.channel.connection, turn:this.channel.turnId});
      return { ZERO_MODEL_NATIVE_SESSION_PREPARED: true, text: '', thinking: '', native_session_uuid: session,
        stop_reason: 'no_prompt_sent', original_relay_receipts_complete: true, physical_terminal: true,
        fresh_stateless_session: true };
    } catch (error) {
      if (error?.unadmitted === true) throw error;
      this.retained = true;
      noteOwnedPhaseInfra(this, 'prepare-zero-model', error);
      throw new Error('DYNTEAM_RACING_ZERO_MODEL_PREPARE_FAILED_RETAIN');
    } finally { this.busy = false; }
  }
  async closeAfterDrained({ allowRetained = false } = {}) {
    need(!this.busy && (!this.retained || allowRetained), 'DYNTEAM_RACING_NATIVE_PHASE_RETAINED_NOT_RETIRABLE');
    await this.channel.close();
    for (const socket of this.clients) socket.end();
    for (const socket of this.upstreams) socket.end();
    await new Promise(ok => this.server.close(ok));
  }
}

export function physicalProofFromRoute(route) {
  return session => new Promise((ok, bad) => {
    const body = Buffer.from(JSON.stringify({ schema: 'count14-native-phase-physical-proof-v1',
      source_commit: route.source_commit, trajectory_id: route.trajectory_id, role_slot: route.role_slot,
      native_session_uuid: session }));
    let done = false;
    const finish = (error, value) => {
      if (done) return; done = true; clearTimeout(timer);
      if (error) bad(new Error('DYNTEAM_RACING_NATIVE_PHASE_PHYSICAL_PROOF_UNAVAILABLE'));
      else ok(value);
    };
    const req = http.request({ socketPath: route.control_socket, path: '/native-phase-physical-proof', method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': body.length } }, res => {
      let total = 0; const chunks = [];
      res.on('data', chunk => {
        total += chunk.length;
        if (total > 2048) { finish(true); res.destroy(); } else chunks.push(chunk);
      });
      res.on('error', () => finish(true));
      res.on('end', () => {
        try {
          const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          need(res.statusCode === 200 && value.schema === 'count14-native-phase-physical-proof-ack-v1' &&
            value.binding_sha256 === createHash('sha256').update(body).digest('hex') &&
            typeof value.models_clear === 'boolean' && typeof value.tools_clear === 'boolean',
            'DYNTEAM_RACING_NATIVE_PHASE_EXACT_PHYSICAL_PROOF');
          finish(false, { models_clear: value.models_clear, tools_clear: value.tools_clear });
        } catch { finish(true); }
      });
    });
    req.on('error', () => finish(true));
    const timer = setTimeout(() => { finish(true); req.destroy(); }, 32000);
    req.end(body);
  });
}

export async function servePrivatePhase({ port, socketPath, secretPath }) {
  need(await realpath(dirname(socketPath)) === dirname(socketPath), 'DYNTEAM_RACING_PRIVATE_RPC_CANONICAL_PARENT');
  const secretStat = await lstat(secretPath);
  need(secretStat.isFile() && !secretStat.isSymbolicLink() && (secretStat.mode & 0o077) === 0,
    'DYNTEAM_RACING_PRIVATE_RPC_BEARER_OWNER_MODE');
  const secret = (await readFile(secretPath, 'utf8')).trim();
  need(secret.length >= 32 && secret.length <= 512, 'DYNTEAM_RACING_PRIVATE_RPC_BEARER_LENGTH');
  const server = http.createServer(async (req, res) => {
    const supplied = Buffer.from(req.headers.authorization ?? '');
    const expected = Buffer.from('Bearer ' + secret);
    if (req.method !== 'POST' || req.url !== '/native-racing-phase' || supplied.length !== expected.length ||
        !timingSafeEqual(supplied, expected)) {
      res.writeHead(403); res.end('{"PUBLIC_code":"DYNTEAM_RACING_PRIVATE_RPC_REFUSED"}'); return;
    }
    let size = 0; const chunks = [];
    try {
      for await (const chunk of req) {
        size += chunk.length; need(size <= 20 * 1024 * 1024, 'DYNTEAM_RACING_PRIVATE_REQUEST_BOUND');
        chunks.push(chunk);
      }
      const row = JSON.parse(Buffer.concat(chunks).toString('utf8'));
      need(row.schema === 'count14-private-native-racing-phase-v1' && row.role === port.route.role_slot,
        'DYNTEAM_RACING_PRIVATE_RPC_EXACT_ROLE');
      // After this admission, a client disconnect never cancels the real ACP
      // call. Its existing promise/custody completes naturally in this owner.
      const result = row.phase === 'prepare-zero-model' ? await port.prepareZeroModel() : await port.run(row.parts, row.phase, row.setup_resume ?? null);
      if (!res.destroyed) {
        res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(result));
      }
    } catch (error) {
      noteOwnedPhaseInfra(port, 'OTHER', error);
      if (!res.destroyed) {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ PUBLIC_code: error?.unadmitted === true ?
          'DYNTEAM_RACING_NATIVE_PHASE_HELD_UNADMITTED' : 'DYNTEAM_RACING_NATIVE_PHASE_RETAIN_NO_REPLAY' }));
      }
    }
  });
  // No request/response-body logs and no post-admission wall-clock cancellation.
  server.requestTimeout = 0; server.headersTimeout = 5000;
  await new Promise((ok, bad) => { server.once('error', bad); server.listen(socketPath, ok); });
  return server;
}
