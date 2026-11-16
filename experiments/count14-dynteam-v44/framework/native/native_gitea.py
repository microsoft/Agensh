"""Trusted same-input Gitea publication; never run in or selected by a worker.

Uses original native organization-repository and branch-protection API paths.
Only a new empty repository is accepted. Pushes the exact immutable approved
bootstrap commit to main and count14-bootstrap atomically, not the mutable HEAD.
No native ProgramBench README/CODEOWNERS/task/source rewrite is introduced.
Credentials only enter host-side HTTP headers or the private Git child env.
No retry/delete/recreate/cancel/signal path exists for accepted side effects.
"""
from dataclasses import dataclass
from pathlib import Path
import base64,hashlib,http.client,json,os,re,subprocess,threading,urllib.parse,uuid
from common import need,Refused,ident,sha,digest,wire,strict,hash_file,private_dir,publish,trajectory_id
from bridge import process_identity
CAP=2**20

@dataclass(frozen=True)
class GiteaBinding:
    trajectory:str
    generation:int
    service_instance_sha256:str
    base_url:str
    organization:str
    repository:str
    admin_username:str
    writers_team:str
    token:str

def binding_identity(binding):
    need(isinstance(binding,GiteaBinding),'GITEA_TRUSTED_BINDING_REQUIRED')
    trajectory_id(binding.trajectory)
    for name in(binding.organization,binding.repository,binding.admin_username,binding.writers_team):ident(name)
    need(type(binding.generation)is int and binding.generation==1,'GITEA_FIRSTSTART_GENERATION_ONLY');sha(binding.service_instance_sha256)
    parsed=urllib.parse.urlsplit(binding.base_url)
    need(parsed.scheme in('http','https')and parsed.hostname and parsed.username is None and parsed.password is None and not parsed.query and not parsed.fragment and parsed.path in('','/'),'GITEA_FIXED_ORIGIN')
    need(type(binding.token)is str and bool(binding.token)and not any(c in binding.token for c in '\r\n\x00'),'GITEA_PRIVATE_TOKEN')
    origin=urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,'','',''))
    return origin,digest({k:v for k,v in vars(binding).items()if k!='token'})

def branch_protection_matches(actual,expected):
    """One named wire omission, not generic truthy/default normalization.

    This Gitea response omits require_code_owner_review, which original native
    bootstrap sends as false. It is not a supported/echoed grant. Only its ABSENT
    representation is equivalent to requested false; true/null/0 still refuse.
    All actual native push/merge/approvals guards must still be present/exact.
    """
    if type(actual)is not dict:return False
    for key,wanted in expected.items():
        if key=='require_code_owner_review' and wanted is False:
            if key not in actual:continue
            if actual[key]is not False:return False
        elif key not in actual or type(actual[key])is not type(wanted)or actual[key]!=wanted:return False
    return True

class NativeGitea:
    def __init__(self,binding,ledger,private_home,*,git_binary='/usr/bin/git'):
        self.origin,self.binding_sha=binding_identity(binding);self.binding=binding;self.ledger=ledger;self.home=private_dir(private_home,create=True)
        self.git=Path(git_binary);need(self.git.is_absolute()and self.git.is_file(),'GITEA_TRUSTED_GIT_BINARY');self.git_sha=hash_file(self.git)['sha256']
        self.scope=digest({'trajectory':binding.trajectory,'generation':binding.generation,'purpose':'same-input-native-gitea-publication'})
        self.repo_api='/api/v1/repos/'+binding.organization+'/'+binding.repository
        self.remote=self.origin+'/'+binding.organization+'/'+binding.repository+'.git'
        self.operation=None;self.child=None;self.retainers=[]
    def event(self,kind,metadata):
        with self.ledger.tx():self.ledger.event(self.binding.trajectory,kind,{'scope':self.scope,**metadata})
    def fail(self,code):
        self.ledger.latch_fault(self.binding.trajectory,code)
        with self.ledger.tx():
            self.ledger.db.execute("UPDATE accounts SET state='FAULT' WHERE trajectory=?",(self.binding.trajectory,))
            self.ledger.event(self.binding.trajectory,'GITEA_PUBLICATION_UNRESOLVED',{'scope':self.scope,'code':code,'operation_id':self.operation})
        raise Refused(code)
    def api(self,method,path,body=None):
        # Only this trusted owner constructs paths. No redirects, proxy env,
        # dynamic URL, or raw response/error payload reaches the metadata log.
        fixed={('GET',self.repo_api),('POST','/api/v1/orgs/'+self.binding.organization+'/repos'),('POST',self.repo_api+'/branch_protections'),('GET',self.repo_api+'/branch_protections/main')}
        need((method,path)in fixed,'GITEA_FIXED_API_ONLY')
        url=urllib.parse.urlsplit(self.origin);factory=http.client.HTTPSConnection if url.scheme=='https'else http.client.HTTPConnection
        connection=factory(url.hostname,url.port,timeout=30)
        try:
            raw=None if body is None else wire(body)
            connection.request(method,path,body=raw,headers={'Authorization':'token '+self.binding.token,'Content-Type':'application/json','Connection':'close'})
            response=connection.getresponse();payload=response.read(CAP+1)
            need(len(payload)<=CAP,'GITEA_RESPONSE_BOUND');need(not 300<=response.status<400,'GITEA_REDIRECT_FORBIDDEN')
            value={}if not payload else strict(payload);need(type(value)is dict,'GITEA_METADATA_OBJECT')
            return response.status,value
        finally:connection.close()
    def git_command(self,args,source,*,credential=False):
        need(hash_file(self.git)['sha256']==self.git_sha,'GITEA_GIT_EXECUTABLE_CHANGED')
        command=[str(self.git),'-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-c','credential.helper=','-c','http.followRedirects=false','-c','http.saveCookies=false','-c','protocol.allow=never','-c','protocol.http.allow=always','-c','protocol.https.allow=always',*args]
        env={'PATH':'/usr/bin:/bin','HOME':str(self.home),'LANG':'C','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_TERMINAL_PROMPT':'0','GIT_OPTIONAL_LOCKS':'0'}
        if credential:
            value=base64.b64encode((self.binding.admin_username+':'+self.binding.token).encode()).decode()
            env.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.'+self.origin+'/.extraHeader',GIT_CONFIG_VALUE_0='Authorization: Basic '+value)
        # stdout is metadata only for our fixed rev-parse/ls-remote commands.
        # No timeout that kills a possibly accepted push; actual wait owns child.
        metadata={'operation_id':self.operation,'credential_attached':credential,'fixed_arguments_sha256':digest(args),'git_executable_sha256':self.git_sha}
        self.event('GITEA_GIT_CHILD_ALLOCATING',metadata)
        child=subprocess.Popen(command,cwd=source,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL);self.child=child
        pid={'pid':child.pid}
        try:
            pid=process_identity(child.pid)
            self.event('GITEA_GIT_CHILD_STARTED',{**metadata,**pid})
            raw=bytearray();overflow=False
            while True:
                block=child.stdout.read(65536)
                if not block:break
                if len(raw)+len(block)>CAP:overflow=True
                if not overflow:raw.extend(block)
                # Continue draining the SAME possibly-writing child after a
                # bound breach. No kill, retry or unbounded payload buffering.
            code=child.wait();child.stdout.close()
            self.event('GITEA_GIT_CHILD_TERMINAL',{'operation_id':self.operation,**pid,'exit_code':code if code>=0 else None,'signal':-code if code<0 else None})
            need(not overflow,'GITEA_GIT_METADATA_BOUND');need(code==0,'GITEA_NATIVE_GIT_NONZERO_UNKNOWN');return bytes(raw)
        except BaseException:
            self.ledger.latch_fault(self.binding.trajectory,'GITEA_GIT_CHILD_CUSTODY_UNKNOWN')
            if not child.stdout.closed:
                # Keep independent custody even if metadata storage fails after
                # Popen. Retainer never completes the publication operation.
                def retain():
                    try:
                        for _ in iter(lambda:child.stdout.read(65536),b''):pass
                        code=child.wait()
                        try:self.event('GITEA_RETAINED_CHILD_TERMINAL',{'operation_id':self.operation,**pid,'exit_code':code if code>=0 else None,'signal':-code if code<0 else None})
                        except Exception:pass
                    finally:child.stdout.close()
                thread=threading.Thread(target=retain,name='native-gitea-child-custody',daemon=False);self.retainers.append(thread);thread.start()
            raise

    def check_repo(self,value,repo_id,*,empty):
        need(type(value.get('id'))is int and value['id']>0 and(repo_id is None or value['id']==repo_id),'GITEA_REPOSITORY_IDENTITY')
        need(value.get('full_name')==self.binding.organization+'/'+self.binding.repository and value.get('private')is True and value.get('default_branch')=='main'and type(value.get('empty'))is bool and(empty is None or value['empty']is empty),'GITEA_REPOSITORY_METADATA_CHANGED')
        return value['id']
    def publication(self,bootstrap_root,expected_receipt_pin):
        root=Path(bootstrap_root);need(root.is_absolute()and root.resolve()==root,'GITEA_BOOTSTRAP_ROOT')
        need(hash_file(root/'bootstrap-receipt.json')==expected_receipt_pin,'GITEA_APPROVED_BOOTSTRAP_RECEIPT_PIN')
        receipt=strict((root/'bootstrap-receipt.json').read_bytes());source=root/'source'
        need(source.is_dir()and source.resolve()==source and(source/'.git').is_dir()and not(source/'.git').is_symlink(),'GITEA_APPROVED_SOURCE_DIRECTORY')
        need(receipt.get('schema')=='count14-agensh-bootstrap-v1'and receipt.get('gitea_published')is False,'GITEA_ORIGINAL_BOOTSTRAP_RECEIPT')
        for name in('source_sha256','task_description_sha256','approved_input_index_sha256'):sha(receipt[name])
        need(hash_file(root/'task-description.bin')['sha256']==receipt['task_description_sha256'],'GITEA_APPROVED_TASK_CHANGED')
        commit=receipt['bootstrap_commit'];tree=receipt['bootstrap_tree'];need(all(type(v)is str and re.fullmatch('[0-9a-f]{40}',v)for v in(commit,tree)),'GITEA_BOOTSTRAP_GIT_OBJECTS')
        with self.ledger.tx():
            account=self.ledger._identity(self.binding.trajectory,'worker-00',self.binding.generation);need(account['state']=='RUNNING','GITEA_ACCOUNT_NOT_ADMITTING')
            need(receipt.get('roles')==json.loads(account['roles']),'GITEA_BOOTSTRAP_ROSTER_BINDING')
            rows=self.ledger.db.execute("SELECT metadata FROM events WHERE trajectory=? AND kind='GITEA_PUBLICATION_ALLOCATING'",(self.binding.trajectory,)).fetchall()
            need(all(strict(row[0]).get('scope')!=self.scope for row in rows),'GITEA_PUBLICATION_ALREADY_ATTEMPTED_NO_REPLAY')
            self.ledger.event(self.binding.trajectory,'GITEA_PUBLICATION_ALLOCATING',{'scope':self.scope,'binding_sha256':self.binding_sha,'bootstrap_receipt':expected_receipt_pin})
        op='gitea-'+uuid.uuid4().hex
        self.ledger.operation_start(self.binding.trajectory,'worker-00',self.binding.generation,op,'GIT_WRITE');self.operation=op
        try:
            need(self.git_command(['rev-parse','HEAD','HEAD^{tree}','refs/tags/count14-bootstrap'],source).decode().splitlines()==[commit,tree,commit],'GITEA_APPROVED_COMMIT_OR_TREE_CHANGED')
            status,_=self.api('GET',self.repo_api);need(status==404,'GITEA_FRESH_REPOSITORY_REQUIRED')
            self.event('GITEA_CREATE_DISPATCHING',{'operation_id':op})
            status,value=self.api('POST','/api/v1/orgs/'+self.binding.organization+'/repos',{'name':self.binding.repository,'private':True,'auto_init':False,'default_branch':'main','description':'count14 approved source; no task reformulation'})
            need(status==201,'GITEA_CREATE_NOT_CONFIRMED_UNKNOWN');repo_id=self.check_repo(value,None,empty=True)
            self.event('GITEA_CREATE_CONFIRMED',{'operation_id':op,'repository_id':repo_id})
            self.event('GITEA_PUSH_DISPATCHING',{'operation_id':op,'bootstrap_commit':commit,'bootstrap_tree':tree})
            self.git_command(['push','--atomic','--',self.remote,commit+':refs/heads/main',commit+':refs/tags/count14-bootstrap'],source,credential=True)
            raw=self.git_command(['ls-remote','--refs','--',self.remote,'refs/heads/main','refs/tags/count14-bootstrap'],source,credential=True)
            pairs=[line.split('\t')for line in raw.decode().splitlines()];need(all(len(x)==2 for x in pairs),'GITEA_REMOTE_REFS_SHAPE')
            expected={'refs/heads/main':commit,'refs/tags/count14-bootstrap':commit};need(len(pairs)==2 and {ref:oid for oid,ref in pairs}==expected,'GITEA_REMOTE_BOOTSTRAP_REFS_CHANGED')
            # Native atomic push + exact ls-remote above are the synchronous
            # content authority. Gitea's boolean empty cache may lag indefinitely;
            # it is NOT another fixed-point gate. Keep ID/name/private/main and
            # metadata shape guards, but do not poll, push or POST again for it.
            status,value=self.api('GET',self.repo_api);need(status==200,'GITEA_POSTPUSH_METADATA_UNKNOWN');self.check_repo(value,repo_id,empty=None)
            # Same native main-branch protection, installed after immutable seed.
            # We deliberately do not call native ensure_codeowners: it would add
            # files/commits to the approved input and change the source/task.
            protection={'branch_name':'main','enable_push':True,'enable_push_whitelist':True,'push_whitelist_usernames':[self.binding.admin_username],'push_whitelist_teams':[],'push_whitelist_deploy_keys':False,'required_approvals':0,'enable_approvals_whitelist':True,'approvals_whitelist_username':[],'approvals_whitelist_teams':[],'enable_merge_whitelist':True,'merge_whitelist_usernames':[],'merge_whitelist_teams':[self.binding.writers_team],'dismiss_stale_approvals':False,'block_on_rejected_reviews':False,'block_on_official_review_requests':False,'block_on_outdated_branch':False,'require_code_owner_review':False,'enable_status_check':False,'status_check_contexts':[]}
            self.event('GITEA_BRANCH_PROTECTION_DISPATCHING',{'operation_id':op,'policy_sha256':digest(protection)})
            status,value=self.api('POST',self.repo_api+'/branch_protections',protection);need(status==201,'GITEA_BRANCH_PROTECTION_UNKNOWN')
            status,value=self.api('GET',self.repo_api+'/branch_protections/main');need(status==200 and branch_protection_matches(value,protection),'GITEA_BRANCH_PROTECTION_NOT_CONFIRMED')
            # Verify source/task/receipt still identical; no worker is released
            # by this function. Their initial views stay independently copied.
            need(hash_file(root/'bootstrap-receipt.json')==expected_receipt_pin and hash_file(root/'task-description.bin')['sha256']==receipt['task_description_sha256'],'GITEA_APPROVED_INPUT_CHANGED')
            published={'schema':'count14-agensh-gitea-publication-v1','scope':self.scope,'binding_sha256':self.binding_sha,'bootstrap_receipt':expected_receipt_pin,'source_sha256':receipt['source_sha256'],'task_description_sha256':receipt['task_description_sha256'],'approved_input_index_sha256':receipt['approved_input_index_sha256'],'bootstrap_commit':commit,'bootstrap_tree':tree,'repository_id':repo_id,'native_remote_refs_sha256':digest(expected),'native_branch_protection_sha256':digest(protection),'gitea_published':True,'source_or_task_rewritten':False,'worker_access_released':False}
            publish(self.home/'gitea-publication.json',wire(published),mode=0o400)
            self.event('GITEA_PUBLICATION_VERIFIED',{'operation_id':op,'receipt_sha256':digest(published),'repository_id':repo_id});self.ledger.operation_end(op);return published
        except Refused as error:self.fail(error.code)
        except Exception:self.fail('GITEA_PUBLICATION_TRANSPORT_OR_PROCESS_UNKNOWN')
