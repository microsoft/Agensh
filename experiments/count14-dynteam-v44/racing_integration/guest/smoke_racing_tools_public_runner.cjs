#!/opt/agentrt/bin/node
/* Scientific runtime only. Input/output bodies never go to PUBLIC diagnostics.
 * Original unprivileged native-agent shell/cgroup boundary; no reference oracle,
 * model, Docker/socket access, timeout signal, cancellation or cleanup deletion.
 */
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const cp=require('node:child_process');
const MAX=8*1024*1024;
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
function need(v){if(!v)throw new Error('DYNTEAM_RACING_PUBLIC_EXEC_INVALID');}
function inside(root,p){return p!==root&&p.startsWith(root+'/');}
function safeRelative(p){return typeof p==='string'&&p.length>0&&p.length<1024&&!p.includes('\\')&&
 !path.isAbsolute(p)&&p.split('/').every(x=>x&&x!=='.'&&x!=='..');}
function capZero(){const rows=fs.readFileSync('/proc/self/status','utf8').split('\n');
 return ['CapEff:','CapPrm:','CapAmb:'].every(k=>{const line=rows.find(x=>x.startsWith(k));
 return line&&/^0+$/.test(line.split(/\s+/)[1]);});}
async function main(){
 const ownArg=process.argv[2];
 const own=typeof ownArg==='string'&&ownArg.startsWith('--own-fixture-root=');
 need(process.argv.length===(own?3:2));
 const ownRoot=own?ownArg.slice('--own-fixture-root='.length):null;
 if(own)need(/^\/tmp\/OWN-[A-Za-z0-9_-]+$/.test(ownRoot)&&fs.realpathSync(ownRoot)===ownRoot&&fs.statSync(ownRoot).uid===process.getuid());
 else need(process.getuid()===10000&&process.getgid()===10000&&capZero());
 let chunks=[],size=0;for await(const chunk of process.stdin){size+=chunk.length;need(size<=MAX);chunks.push(chunk);}
 const input=JSON.parse(Buffer.concat(chunks).toString('utf8'));
 need(input.schema===(own?'OWN-count14-racing-public-exec-case-v1':'count14-racing-public-exec-case-v1')&&/^[0-9a-f]{32}$/.test(input.nonce)&&
  Number.isInteger(input.task_slot)&&input.task_slot>=1&&input.task_slot<=14&&
  input.workspace===(own?ownRoot:'/work')&&typeof input.program==='string'&&/^\/[A-Za-z0-9_./+\-]+$/.test(input.program)&&
  typeof input.case==='object'&&typeof input.case.cmd==='string'&&input.case.cmd.length>0&&
  input.case.cmd.length<1024*1024&&typeof input.case.stdin==='string'&&Array.isArray(input.case.files));
 const workspace=fs.realpathSync(input.workspace),program=fs.realpathSync(input.program);
 need(workspace===(own?ownRoot:'/work')&&inside(workspace,program)&&fs.statSync(program).isFile());
 fs.accessSync(program,fs.constants.X_OK);
 const parent=own?path.join(workspace,'.count14-public-probes'):'/work/.count14-racing/public-probes';
 try{fs.mkdirSync(parent,{mode:0o700});}catch(e){if(e.code!=='EEXIST')throw e;}
 need(fs.realpathSync(parent)===parent&&fs.lstatSync(parent).isDirectory()&&!fs.lstatSync(parent).isSymbolicLink());
 const root=path.join(parent,input.nonce);fs.mkdirSync(root,{mode:0o700});
 const names=new Set();let total=0;
 for(const row of input.case.files){need(row&&safeRelative(row.path)&&!names.has(row.path)&&typeof row.content==='string');
  names.add(row.path);total+=Buffer.byteLength(row.content);need(total<=MAX);
  const target=path.join(root,row.path);fs.mkdirSync(path.dirname(target),{recursive:true,mode:0o700});
  fs.writeFileSync(target,row.content,{flag:'wx',mode:0o600});}
 const cmd=input.case.cmd.replace(/\bPROG\b/g,program);
 const child=cp.spawn('/bin/bash',['-c',cmd],{cwd:root,env:{...process.env},stdio:['pipe','pipe','pipe']});
 const out=crypto.createHash('sha256'),err=crypto.createHash('sha256');let outBytes=0,errBytes=0;
 child.stdout.on('data',x=>{out.update(x);outBytes+=x.length;});
 child.stderr.on('data',x=>{err.update(x);errBytes+=x.length;});
 child.stdin.on('error',()=>{});child.stdin.end(input.case.stdin);
 const terminal=await new Promise((resolve,reject)=>{child.once('error',reject);child.once('close',(code,signal)=>resolve({code,signal}));});
 const body={schema:'count14-racing-public-exec-result-v1',nonce:input.nonce,task_slot:input.task_slot,
  native_uid10000:!own,capabilities_zero:capZero(),official_verdict:false,command_dispatched_once:true,
  exit_code:terminal.code,signal:terminal.signal,stdout_sha256:out.digest('hex'),stderr_sha256:err.digest('hex'),
  stdout_bytes:outBytes,stderr_bytes:errBytes,shell_process_physically_exited:true,
  all_descendants_terminal_not_claimed:true,case_root_retained:true};
 if(own)body.qualification_only=true;
 process.stdout.write(JSON.stringify(body)+'\n');
}
main().catch(()=>{process.stderr.write('DYNTEAM_RACING_PUBLIC_EXEC_INVALID_RETAIN_NO_REPLAY\n');process.exitCode=125;});
