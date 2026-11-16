/** Metadata-only preload around the ORIGINAL native sendText callsite.
 *
 * Original scientific source is not edited. Prompt arguments/return values are
 * passed by reference, never read/hashed/logged by this hook. The actual ACP
 * sessionId (not a directory guess) is registered before original prompt().
 * A failed receipt does NOT call native close/cancel/newSession or retry.
 * Subsequent checker freshSession uses the original reconnect fallback only
 * after its old paid epoch has a durable, fresh physical-zero close permit.
 */
import { createHash, randomUUID } from 'node:crypto';
import { open, lstat } from 'node:fs/promises';
import { constants } from 'node:fs';
import { dirname, join } from 'node:path';
import http from 'node:http';

const COMMIT = '70e2ca54c078597e3314755064d2ef1a83344c8e';
const INSTALLED = Symbol.for('count14.dynteam70e2.session-control.v1');
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const SHA = /^[0-9a-f]{64}$/;
const ROLE = /^(worker-(?:[0-2][0-9]|3[01])|checker-00|tester-00|racing-background-00|racing-player-0[0-6])$/;
const NORMAL_RECONNECT_ROLE = /^(checker-00|racing-background-00|racing-player-0[0-6])$/;
const acceptedSessions = new WeakMap();
const reconnects = new WeakMap();
const busy = new WeakSet();
function need(ok, code) { if (!ok) throw new Error(code); }
function hash(value) { return createHash('sha256').update(JSON.stringify(value)).digest('hex'); }

async function boundedMetadata(path, timeoutMs) {
  const controller = new AbortController();
  let timer;
  try {
    return await Promise.race([
      (async () => {
        const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
        try {
          const before = await handle.stat();
          need(before.isFile() && before.size > 0 && before.size <= 4096,
            'DYNTEAM_EXACT_NATIVE_TURN_METADATA_FILE');
          const buffer = Buffer.alloc(4097);
          const { bytesRead } = await handle.read(buffer, 0, buffer.length, 0);
          const after = await handle.stat();
          const pathname = await lstat(path);
          need(bytesRead === before.size && bytesRead <= 4096 && !pathname.isSymbolicLink() &&
            before.dev === pathname.dev && before.ino === pathname.ino &&
            before.dev === after.dev && before.ino === after.ino && before.size === after.size &&
            before.mtimeMs === after.mtimeMs && before.ctimeMs === after.ctimeMs,
            'DYNTEAM_NATIVE_TURN_METADATA_CHANGED');
          const row = JSON.parse(buffer.subarray(0, bytesRead).toString('utf8'));
          need(typeof row.turn_id === 'string' && row.turn_id.length > 0 && row.turn_id.length <= 256 &&
            typeof row.username === 'string' && row.username.length > 0 && row.username.length <= 256,
            'DYNTEAM_NATIVE_TURN_CONTROL_FIELDS');
          return { turnId: row.turn_id, account: row.username };
        } finally { await handle.close(); }
      })(),
      new Promise((_, reject) => {
        timer = setTimeout(() => { controller.abort(); reject(new Error('DYNTEAM_METADATA_READ_TIMEOUT')); }, timeoutMs);
      }),
    ]);
  } catch (error) {
    // Error args, paths, raw metadata and science bodies never reach our log.
    if (error?.message === 'DYNTEAM_METADATA_READ_TIMEOUT') throw error;
    throw new Error('DYNTEAM_NATIVE_TURN_METADATA_UNAVAILABLE');
  } finally { clearTimeout(timer); }
}

function postControl(socketPath, path, schema, envelope, timeoutMs, resubmissionOrdinal = 0) {
  return new Promise((resolve, reject) => {
    const body = Buffer.from(JSON.stringify(envelope));
    let done = false;
    let timer;
    const finish = (error, value) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      if (error) reject(new Error(error)); else resolve(value);
    };
    const req = http.request({ socketPath, path, method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': body.length,
        ...(path === '/native-session-ready' && resubmissionOrdinal > 0
          ? { 'X-Count14-Control-Resubmission': String(resubmissionOrdinal) } : {}) },
    }, (res) => {
      let total = 0;
      const chunks = [];
      res.on('data', chunk => {
        total += chunk.length;
        if (total > 2048) { res.destroy(); finish('DYNTEAM_CONTROL_RESPONSE_BOUND'); }
        else chunks.push(chunk);
      });
      res.on('error', () => finish('DYNTEAM_CONTROL_RECEIPT_UNAVAILABLE'));
      res.on('end', () => {
        if (done) return;
        try {
          const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (path === '/native-session-ready' && res.statusCode === 503 &&
              value?.PUBLIC_code === 'DYNTEAM_SESSION_READY_UNSTARTED_EXPIRED_NO_EFFECT' &&
              value?.unstarted_no_effect === true) {
            finish('DYNTEAM_SESSION_READY_UNSTARTED_EXPIRED_NO_EFFECT'); return;
          }
          need(res.statusCode === 200 && value.schema === schema &&
            value.accepted === true && value.binding_sha256 === hash(envelope), 'DYNTEAM_CONTROL_EXACT_ACK');
          finish(null, value);
        } catch { finish('DYNTEAM_CONTROL_EXACT_ACK'); }
      });
    });
    req.on('error', () => finish('DYNTEAM_CONTROL_RECEIPT_UNAVAILABLE'));
    timer = setTimeout(() => { finish('DYNTEAM_CONTROL_TIMEOUT'); req.destroy(); }, timeoutMs);
    req.end(body);
  });
}

export function postSession(socketPath, envelope, timeoutMs, resubmissionOrdinal = 0) {
  return postControl(socketPath, '/native-session-ready',
    'count14-dynteam-native-session-ack-v1', envelope, timeoutMs, resubmissionOrdinal);
}

export function postReconnect(socketPath, envelope, timeoutMs) {
  return postControl(socketPath, '/native-session-reconnect',
    'count14-native-normal-session-reconnect-ack-v1', envelope, timeoutMs);
}

export function installSessionHook(Channel, route) {
  need(route.source_commit === COMMIT && typeof route.trajectory_id === 'string' &&
    route.trajectory_id.length > 0 && route.trajectory_id.length <= 512 &&
    Number.isInteger(route.block) && route.block >= 1 && route.block <= 3 && ROLE.test(route.role_slot) &&
    typeof route.control_socket === 'string' && route.control_socket.startsWith('/') &&
    typeof route.native_acp_socket === 'string' && route.native_acp_socket.startsWith('/'),
    'DYNTEAM_EXACT_PUBLIC_ROUTER_ROUTE');
  const timeoutMs = route.metadata_timeout_ms;
  need(Number.isInteger(timeoutMs) && timeoutMs >= 50 && timeoutMs <= 3000, 'DYNTEAM_BOUNDED_METADATA_TIMEOUT');
  // Only CONTROL preflight transport, not any model/SYSTEM deadline/cadence.
  // The actual owner may need multiple fresh Docker/kernel projections.
  const reconnectTimeoutMs = route.reconnect_timeout_ms ?? 32000;
  need(Number.isInteger(reconnectTimeoutMs) && reconnectTimeoutMs >= 50 && reconnectTimeoutMs <= 32000,
    'DYNTEAM_BOUNDED_NORMAL_RECONNECT_CONTROL_TIMEOUT');
  need(typeof Channel?.prototype?.sendText === 'function' && !Channel.prototype[INSTALLED],
    'DYNTEAM_ORIGINAL_NATIVE_SENDTEXT_SINGLE_PRELOAD');
  const original = Channel.prototype.sendText;
  const originalFresh = Channel.prototype.freshSession;
  const originalClose = Channel.prototype.close;
  need(!NORMAL_RECONNECT_ROLE.test(route.role_slot) ||
    (typeof originalFresh === 'function' && typeof originalClose === 'function'),
    'DYNTEAM_RECONNECT_ORIGINAL_SAME_ACCOUNT_LIFECYCLE_METHODS');
  const config = Object.freeze({ ...route });
  Channel.prototype.sendText = async function (...originalArguments) {
    need(!busy.has(this) && !reconnects.has(this), 'DYNTEAM_SESSION_CONTROL_PARTIAL_OR_CONCURRENT_RETAIN');
    busy.add(this);
    try {
      await registerCurrentNativeSession(this, config);
      // No originalArguments inspection, serialization, mutation or logging.
      return await original.apply(this, originalArguments);
    } finally { busy.delete(this); }
  };
  if (NORMAL_RECONNECT_ROLE.test(route.role_slot)) {
    Channel.prototype.freshSession = async function (...originalArguments) {
      need(!busy.has(this), 'DYNTEAM_RECONNECT_NO_CONCURRENT_PROMPT_OR_INIT');
      busy.add(this);
      try {
        const previous = acceptedSessions.get(this);
        // First startup still calls the original newSession. Only a previously
        // durably bound session can use the normal reconnect preflight.
        if (!previous) {
          need(!reconnects.has(this), 'DYNTEAM_RECONNECT_PARTIAL_RETAINED');
          return await originalFresh.apply(this, originalArguments);
        }
        if (!this.connection && !this.sessionId && !reconnects.has(this)) {
          // An already-disconnected original channel has no live-session
          // initializer to preflight or close. Preserve its original reconnect
          // path; original archived-END/new-direct-child guards still apply.
          const result = await originalFresh.apply(this, originalArguments);
          await registerCurrentNativeSession(this, config);
          return result;
        }
        need(this.connection === previous.connection && this.connection &&
          this.sessionId === previous.envelope.native_session_uuid &&
          this.turnId === previous.turn && !this.connecting,
          'DYNTEAM_RECONNECT_EXACT_OLD_CONNECTION_TURN_AND_SID');
        let intent = reconnects.get(this);
        if (!intent) {
          intent = { stage: 'PREFLIGHT', envelope: {
            ...previous.envelope, schema: 'count14-native-normal-session-reconnect-v1',
            reconnect_id: randomUUID(),
          }};
          reconnects.set(this, intent);
        }
        // Only a new upstream metadata attempt can retry the SAME unsent
        // preflight nonce. Never repeat close/newSession after a partial effect.
        need(intent.stage === 'PREFLIGHT', 'DYNTEAM_RECONNECT_NO_SECOND_CLOSE_OR_INIT');
        await postReconnect(config.control_socket, intent.envelope, reconnectTimeoutMs);
        need(this.connection === previous.connection &&
          this.sessionId === previous.envelope.native_session_uuid && this.turnId === previous.turn &&
          !this.connecting, 'DYNTEAM_RECONNECT_CHANNEL_UNCHANGED_AFTER_TRUE_ACK');
        intent.stage = 'ORIGINAL_CLOSE_CALLED';
        // Preserve opaque queued references; do not inspect, hash or log them.
        // Reconnecting must not erase a prefix/notice or alter the original
        // freshSession call's initial-prompt flag.
        const prefix = this.promptPrefix;
        const notice = this.pendingNotice;
        const fresh = this.freshContextPending;
        // Keep the existing racing INSTANCE close wrapper. It performs its
        // original physicalProof + tap.tools-zero guard before delegating to
        // this same original close. Calling the prototype directly bypasses
        // that guard and is forbidden, even with a prior owner permit.
        await this.close();
        need(!this.connection && !this.sessionId && !this.connecting,
          'DYNTEAM_RECONNECT_GUARDED_ORIGINAL_CLOSE_MUST_REALLY_DISCONNECT');
        intent.stage = 'ORIGINAL_FRESH_CALLED';
        const result = await originalFresh.apply(this, originalArguments);
        this.promptPrefix = prefix;
        this.pendingNotice = notice;
        this.freshContextPending = fresh;
        intent.stage = 'NEW_SESSION_BIND_PENDING';
        await registerCurrentNativeSession(this, config);
        reconnects.delete(this);
        return result;
      } finally { busy.delete(this); }
    };
  }
  if (/^worker-(?:[0-2][0-9]|3[01])$/.test(config.role_slot)) {
    need(!('count14RetiredRouterQuiescence' in Channel.prototype),
      'DYNTEAM_RETIRED_ROUTER_HOLD_SINGLE_PRELOAD');
    Object.defineProperty(Channel.prototype, 'count14RetiredRouterQuiescence', {
      value: async function (request) {
        // Called only AFTER original workerIdentity has durably returned
        // retired=true. No rotation, ACK, model, close/newSession or signal here.
        const previous = acceptedSessions.get(this);
        need(previous && !busy.has(this) && !reconnects.has(this) &&
          request && typeof request.id === 'string' &&
          ['retire', 'terminated', 'disconnect', 'shutdown', 'router_restart',
            'spawn_failed', 'startup_recovery'].includes(request.reason) &&
          (request.id === previous.turn ||
            (request.id.startsWith('recovery:' + previous.turn + ':') &&
             UUID.test(request.id.slice(('recovery:' + previous.turn + ':').length)))),
          'DYNTEAM_RETIRED_ROUTER_ONLY_ORIGINAL_BOUND_END_TURN');
        const metadataPath = config.native_turn_metadata ??
          join(dirname(config.native_acp_socket), 'current-turn.json');
        const control = await boundedMetadata(metadataPath, config.metadata_timeout_ms);
        need(control.turnId === previous.turn &&
          hash([COMMIT, config.trajectory_id, config.role_slot, control.account]) ===
            previous.envelope.logical_birth_sha256,
          'DYNTEAM_RETIRED_ROUTER_EXACT_CURRENT_TURN_AND_ACCOUNT');
        // Match beta's already-retired startup's inactive lifetime. Keep this
        // exact init/peer/cgroup for the original live-container census while
        // its original bridge completes END. The serialized dispatcher cannot
        // pass this await or prompt a retired account. Its original owner may
        // later stop this exact container normally; main's existing SIGTERM
        // handler remains the ONLY handler, and is not changed by this hook.
        await new Promise(() => {});
        throw new Error('DYNTEAM_RETIRED_ROUTER_QUIESCENCE_MUST_NOT_RETURN');
      },
    });
  }
  Object.defineProperty(Channel.prototype, INSTALLED, { value: original });
  return { originalSendText: original, originalFreshSession: originalFresh,
    originalClose, originalScientificModulesEdited: false };
}

export async function registerCurrentNativeSession(channel, config) {
    const timeoutMs = config.metadata_timeout_ms;
    need(Number.isInteger(timeoutMs) && timeoutMs >= 50 && timeoutMs <= 3000,
      'DYNTEAM_BOUNDED_METADATA_FILE_READ_TIMEOUT');
    // Same typed session-ready receipt in both sendText and racing's direct
    // prepareZeroModel call. No model deadline or metadata-file bound changes.
    const receiptTimeoutMs = config.session_ready_timeout_ms ?? 32000;
    need(Number.isInteger(receiptTimeoutMs) && receiptTimeoutMs >= 50 && receiptTimeoutMs <= 32000,
      'DYNTEAM_BOUNDED_SESSION_READY_CONTROL_TIMEOUT');
    const nativeSession = channel.sessionId;
    const nativeTurn = channel.turnId;
    const nativeConnection = channel.connection;
    need(channel.opts.socketPath === config.native_acp_socket && UUID.test(nativeSession) &&
      typeof nativeTurn === 'string' && nativeTurn.length > 0,
      'DYNTEAM_ACTUAL_ORIGINAL_CHANNEL_SESSION_AND_SOCKET');
    const metadataPath = config.native_turn_metadata ?? join(dirname(channel.opts.socketPath), 'current-turn.json');
    need(typeof metadataPath === 'string' && metadataPath.startsWith('/') &&
      (!config.native_turn_metadata || metadataPath === join(dirname(config.native_agent_socket), 'current-turn.json')),
      'DYNTEAM_EXACT_ORIGINAL_NATIVE_TURN_METADATA_ROUTE');
    const control = await boundedMetadata(metadataPath, timeoutMs);
    need(control.turnId === nativeTurn, 'DYNTEAM_CHANNEL_NATIVE_TURN_EXACT');
    const envelope = {
      schema: 'count14-dynteam-native-session-ready-v1', source_commit: COMMIT,
      trajectory_id: config.trajectory_id, block: config.block, role_slot: config.role_slot,
      logical_birth_sha256: hash([COMMIT, config.trajectory_id, config.role_slot, control.account]),
      native_turn_sha256: hash([COMMIT, config.trajectory_id, config.role_slot, nativeTurn]),
      native_session_uuid: nativeSession,
    };
    need(SHA.test(envelope.logical_birth_sha256) && SHA.test(envelope.native_turn_sha256), 'DYNTEAM_CONTROL_DIGEST');
    // msg276/277: maximum THREE metadata resubmissions, common pre-prompt
    // path for zero-model preparation AND normal paid-arm sessions not SENT.
    // The original first send is ordinal0; no original timeout is extended.
    for (let resubmissionOrdinal = 0; ; resubmissionOrdinal += 1) {
      try {
        await postSession(config.control_socket, envelope, receiptTimeoutMs, resubmissionOrdinal);
        break;
      } catch (error) {
        if (error?.message !== 'DYNTEAM_SESSION_READY_UNSTARTED_EXPIRED_NO_EFFECT') throw error;
        need(resubmissionOrdinal < 3, 'DYNTEAM_SESSION_READY_UNSTARTED_RESUBMIT_EXHAUSTED_RETAIN');
        // Metadata-only resubmission after an exact no-effect outcome. Keep
        // the original prepare Promise, CLI/session/turn/connection/envelope;
        // no freshSession, prompt, helper/phase restart, or timeout extension.
        need(channel.sessionId === nativeSession && channel.turnId === nativeTurn &&
          channel.connection === nativeConnection,
          'DYNTEAM_SESSION_READY_SAME_IDENTITY_BEFORE_CONTROL_RESUBMIT');
      }
    }
    need(channel.sessionId === nativeSession && channel.turnId === nativeTurn &&
      channel.connection === nativeConnection,
      'DYNTEAM_CHANNEL_CHANGED_DURING_CONTROL_RECEIPT');
    acceptedSessions.set(channel, { envelope, turn: nativeTurn, connection: nativeConnection });
    return nativeSession;
}

export const SOURCE_COMMIT = COMMIT;
