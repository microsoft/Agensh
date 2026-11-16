/** Cold-only normal ACP load configuration and host ACK. No prompt/state reads.
 * This module consumes only a fixed host-owned restore control descriptor.
 * Opaque SDK state is consumed by the ordinary SDK loadSession, not this code.
 */
import {createHash} from 'node:crypto';
import {open,lstat} from 'node:fs/promises';
import {constants} from 'node:fs';
import http from 'node:http';
const SHA=/^[0-9a-f]{64}$/;
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const need=(ok,code)=>{if(!ok)throw Error(code)};
export const sidPin=sid=>createHash('sha256').update(sid,'utf8').digest('hex');

export async function coldCollaborationCounts(store,agent){
  // Original native queue metadata only; no message/payload body is read.
  const [rows]=await store.pool.query("SELECT state,COUNT(*) AS n FROM events WHERE agent=? AND state IN ('sending','retrying') GROUP BY state",[agent]);
  need(Array.isArray(rows)&&rows.every(r=>['sending','retrying'].includes(r.state)&&Number.isSafeInteger(Number(r.n))&&Number(r.n)>=0),'COLD_NATIVE_COLLABORATION_CONTROL_COUNTS');
  const counts={sending:0,retrying:0};for(const r of rows)counts[r.state]+=Number(r.n);return counts;
}

export async function readColdRestore(environment=process.env){
  const path=environment.COUNT14_COLD_SDK_RESTORE_FILE,pin=environment.COUNT14_COLD_SDK_RESTORE_SHA256;
  if(path===undefined&&pin===undefined)return undefined;
  need(path==='/run/count14-dynteam/cold-sdk-restore.json'&&SHA.test(pin), 'COLD_SDK_FIXED_RO_DESCRIPTOR_AND_PIN');
  const f=await open(path,constants.O_RDONLY|constants.O_NOFOLLOW);
  try{
    const before=await f.stat();need(before.isFile()&&before.uid===0&&(before.mode&0o222)===0&&before.nlink===1&&before.size<=16384,'COLD_SDK_HOST_CONTROL_CUSTODY');
    const raw=await f.readFile();const after=await f.stat(),p=await lstat(path);
    need(raw.length===before.size&&before.dev===after.dev&&before.ino===after.ino&&before.mtimeMs===after.mtimeMs&&before.ino===p.ino&&!p.isSymbolicLink()&&sidPin(raw)===pin,'COLD_SDK_DESCRIPTOR_CHANGED');
    const v=JSON.parse(raw.toString('utf8'));
    need(v.schema==='count14-formal-cold-sdk-load-control-v1'&&SHA.test(v.plan_sha256)&&SHA.test(v.snapshot_sha256)&&SHA.test(v.session_sha256)&&UUID.test(v.native_session_uuid)&&sidPin(v.native_session_uuid)===v.session_sha256&&typeof v.native_turn==='string'&&v.native_turn.length>0&&SHA.test(v.logical_birth_sha256)&&SHA.test(v.native_turn_sha256)&&typeof v.trajectory==='string'&&typeof v.role==='string'&&v.control_socket==='/run/count14-dynteam/native-control.sock'&&v.no_prompt===true&&v.no_fallback===true,'COLD_SDK_EXACT_ORIGINAL_LOAD_CONTROL');
    return Object.freeze(v);
  }finally{await f.close()}
}

export async function postColdAck(binding,route,envelope){
  need(route.control_socket===binding.control_socket&&route.trajectory_id===binding.trajectory&&route.role_slot===binding.role&&envelope.native_session_uuid===binding.native_session_uuid&&envelope.logical_birth_sha256===binding.logical_birth_sha256&&envelope.native_turn_sha256===binding.native_turn_sha256,'COLD_SDK_ACK_SAME_ORIGINAL_NATIVE_SESSION');
  const value={schema:'count14-formal-cold-sdk-loaded-ack-v1',plan_sha256:binding.plan_sha256,snapshot_sha256:binding.snapshot_sha256,session_sha256:binding.session_sha256,session:envelope,loaded_original:true,prompt_sent:false};
  return postMetadata(binding,'/native-sdk-restore-ack',value);
}

async function postMetadata(binding,path,value){
  const raw=Buffer.from(JSON.stringify(value));
  return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{request.destroy();reject(Error('COLD_SDK_ACK_WAIT_NO_PROMPT'))},2500);
    const request=http.request({socketPath:binding.control_socket,path,method:'POST',headers:{'Content-Type':'application/json','Content-Length':raw.length}},response=>{
      let n=0;const chunks=[];
      response.on('data',b=>{n+=b.length;if(n>2048)request.destroy();else chunks.push(b)});
      response.on('end',()=>{clearTimeout(timer);try{const v=JSON.parse(Buffer.concat(chunks));need(response.statusCode===200&&v.accepted===true&&v.plan_sha256===binding.plan_sha256,'COLD_SDK_HOST_ACK_REFUSED');resolve(v)}catch{reject(Error('COLD_SDK_HOST_ACK_REFUSED'))}});
    });
    request.on('error',()=>{clearTimeout(timer);reject(Error('COLD_SDK_ACK_WAIT_NO_PROMPT'))});request.end(raw);
  });
}

export async function recoverColdCollaborationOnce(store,agent,binding,envelope){
  const before=await coldCollaborationCounts(store,agent);
  const base={schema:'count14-formal-cold-collaboration-recovery-v1',plan_sha256:binding.plan_sha256,snapshot_sha256:binding.snapshot_sha256,session:envelope};
  // Host persists the one-shot intent ONLY AFTER original model/HTTP/ledger
  // and same-SID guards. Missing/retained/expired intent never retries a call.
  const intent=await postMetadata(binding,'/native-sdk-collaboration-recovery',{...base,stage:'INTENT',before});
  need(SHA.test(intent.recovery_token),'COLD_COLLABORATION_ONCE_INTENT_REQUIRED');
  // This is the ORIGINAL native collaboration queue function, not the model
  // request ledger. It changes no model SENT/UNKNOWN or accepted request ID.
  const recovered=await store.recoverSendingToPending(agent);
  need(Number.isSafeInteger(recovered)&&recovered===before.sending,'COLD_COLLABORATION_PARTIAL_INTENT_RETAIN_NO_RETRY');
  const after=await coldCollaborationCounts(store,agent);
  need(after.sending===0&&after.retrying===before.retrying,'COLD_COLLABORATION_ONCE_RECOVERY_COUNT_CHANGED');
  await postMetadata(binding,'/native-sdk-collaboration-recovery',{...base,stage:'COMMITTED',before,after,recovered,recovery_token:intent.recovery_token});
  return recovered;
}

export async function finishColdLoad(channel,binding,route,registerCurrentNativeSession,store,agent){
  // registerCurrentNativeSession is the existing fixed host preload module,
  // not a scientific callback. Main imports it from its fixed pinned path.
  need(channel.sessionId===binding.native_session_uuid&&channel.turnId===binding.native_turn&&channel.opts.coldRestore===binding,'COLD_SDK_LOADED_CHANNEL_ORIGINAL_SID_TURN');
  await registerCurrentNativeSession(channel,route);
  const envelope={schema:'count14-dynteam-native-session-ready-v1',source_commit:'70e2ca54c078597e3314755064d2ef1a83344c8e',trajectory_id:route.trajectory_id,block:route.block,role_slot:route.role_slot,logical_birth_sha256:binding.logical_birth_sha256,native_turn_sha256:binding.native_turn_sha256,native_session_uuid:binding.native_session_uuid};
  await postColdAck(binding,route,envelope);
  await recoverColdCollaborationOnce(store,agent,binding,envelope);
  // No release/thaw/request occurs here. Original BudgetPauseClock and gate
  // continue to prohibit prompts until the original owner explicitly resumes.
}
