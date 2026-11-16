"""Host-owned per-native-session command context on the ORIGINAL receipt UDS.

This records only exact original invocation lineage. It neither revives COMPLETE
TOOLs nor authorizes retained/background Git or declares a writer terminated.
The cold launcher must mount visible_root read-only for exactly its role and
retain the original pre-exec kernel writer fence. No worker-writable alias.
"""
from pathlib import Path
import os,re,secrets,stat
from common import need,sha,private_dir,publish_readonly_metadata,sync_dir,hash_file,digest,stamp

MOUNT='/run/count14/shell-context'
HOOK='native-git-context-v1/native_git_bash_env.sh'

class NativeShellContexts:
    def __init__(self,receipts,root,identity,*,git_url):
        from native_cli_tool_receipt import NativeCliToolReceipts
        need(type(receipts)is NativeCliToolReceipts,'SHELL_CONTEXT_ORIGINAL_RECEIPTS')
        need(type(identity)is tuple and len(identity)==2,'SHELL_CONTEXT_HOST_IDENTITY')
        need(re.fullmatch(r'http://127\.0\.0\.1:[1-9][0-9]{0,4}/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+\.git/',git_url)is not None,
             'SHELL_CONTEXT_EXACT_ROLE_GIT_URL')
        need(0<int(git_url.split(':')[2].split('/')[0])<65536,'SHELL_CONTEXT_GIT_PORT')
        need(identity not in getattr(receipts,'shell_contexts',{}),'SHELL_CONTEXT_BIND_ONCE')
        self.receipts=receipts;self.ledger=receipts.ledger;self.identity=identity;self.git_url=git_url
        self.root=private_dir(root);self.visible_root=self.root/'visible'
        self.visible_root.mkdir(mode=0o700);self.dir_identity=(self.visible_root.stat().st_dev,self.visible_root.stat().st_ino)
        self.root_identity=(self.root.stat().st_dev,self.root.stat().st_ino)
        hook=Path(__file__).resolve().parent/HOOK
        publish_readonly_metadata(self.visible_root/'bash-env.sh',hook.read_bytes())
        self.visible_root.chmod(0o755)
        self.hook_pin=hash_file(self.visible_root/'bash-env.sh');self.sessions={}
        with receipts.condition,self.ledger.mutex:
            need(not receipts.closed and not self.ledger.admission_fault(identity[0]),'SHELL_CONTEXT_CLOSED_OR_FAULT')
            self.ledger._identity(*identity,self.ledger.frontier(identity[0])['generation'])
            need(self.ledger.account(identity[0])['state']=='RUNNING'
                 and self.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=?AND role=?',identity).fetchone()[0]==0,
                 'SHELL_CONTEXT_BIND_BEFORE_FIRST_MODEL')
            with self.ledger.tx():self.ledger.event(identity[0],'NATIVE_SHELL_CONTEXT_BOUND',
                {'role':identity[1],'hook':self.hook_pin,'git_url_sha256':digest(git_url),'worker_mount':MOUNT,'readonly_mount_required':True})
            receipts.shell_contexts[identity]=self
    def _control_file(self,path):
        st=path.lstat()
        need(stat.S_ISREG(st.st_mode)and st.st_uid==os.geteuid()and stat.S_IMODE(st.st_mode)==0o444
             and st.st_nlink==1,'SHELL_CONTEXT_EXACT_HOST_CONTROL_FILE')
        pin=hash_file(path);need(stamp(st)==stamp(path.lstat()),'SHELL_CONTEXT_HOST_CONTROL_CHANGED')
        return pin
    def _fresh(self):
        private_dir(self.root);need((self.root.stat().st_dev,self.root.stat().st_ino)==self.root_identity,'SHELL_CONTEXT_HOST_ROOT_CHANGED');s=self.visible_root.lstat()
        need(stat.S_ISDIR(s.st_mode)and (s.st_dev,s.st_ino)==self.dir_identity and s.st_uid==os.geteuid()
             and stat.S_IMODE(s.st_mode)==0o755,'SHELL_CONTEXT_HOST_DIRECTORY_CHANGED')
        need(self._control_file(self.visible_root/'bash-env.sh')==self.hook_pin,'SHELL_CONTEXT_HOOK_CHANGED')
    def handle(self,identity,value):
        need(identity==self.identity,'SHELL_CONTEXT_EXACT_ROLE')
        self._fresh();t,role=identity
        with self.ledger.mutex:
            f=self.ledger.frontier(t);self.ledger._identity(t,role,f['generation'])
            need(not self.ledger.admission_fault(t),'SHELL_CONTEXT_SHARED_FAULT')
            need(f['state']in('RUNNING','DRAINING'),'SHELL_CONTEXT_ORIGINAL_TOOL_STAGE')
            if value['phase']=='SHELL_ALLOCATE':
                need(set(value)=={'schema','phase'},'SHELL_CONTEXT_ALLOCATE_FIELDS')
                # Session allocation has no operation, command, credential or
                # permission to dispatch. A current exact callback is separately
                # mandatory immediately before EACH native command launch.
                token=secrets.token_hex(32);path=self.visible_root/(token+'.ctx')
                publish_readonly_metadata(path,b'# no original native command prepared\n')
                with self.ledger.tx():self.ledger.event(t,'NATIVE_SHELL_SESSION_ALLOCATED',
                    {'role':role,'session':token,'generation':f['generation']})
                self.sessions[token]={'generation':f['generation'],'sequence':0,'pin':hash_file(path)}
                return {'ok':True,'session':token,'context_file':MOUNT+'/'+token+'.ctx','bash_env':MOUNT+'/bash-env.sh'}
            need(value['phase']=='SHELL_PREPARE'and set(value)=={'schema','phase','session','ticket'},'SHELL_CONTEXT_PREPARE_FIELDS')
            token=sha(value['session']);ticket=sha(value['ticket'])
            need(token in self.sessions,'SHELL_CONTEXT_ORIGINAL_SESSION_REQUIRED')
            session=self.sessions[token];path=self.visible_root/(token+'.ctx')
            need(session['generation']<=f['generation']and self._control_file(path)==session['pin'],'SHELL_CONTEXT_POINTER_CHANGED')
            rows=self.ledger.db.execute('''SELECT s.operation_id FROM native_cli_tool_starts s
                JOIN operations o ON o.id=s.operation_id JOIN requests r ON r.id=s.request_id
                LEFT JOIN native_cli_tool_returns e ON e.ticket=s.ticket
                WHERE s.ticket=?AND s.trajectory=?AND s.role=?AND s.generation=?AND s.mode='CALLBACK'
                AND e.ticket IS NULL AND o.kind='TOOL'AND o.state='ACTIVE'AND o.parent=s.request_id
                AND o.trajectory=s.trajectory AND o.role=s.role AND o.generation=s.generation
                AND r.state='SETTLED'AND r.trajectory=s.trajectory AND r.role=s.role AND r.generation=s.generation''',
                (ticket,t,role,f['generation'])).fetchall()
            need(len(rows)==1,'SHELL_CONTEXT_EXACT_EXECUTING_ORIGINAL_REQUIRED')
            sequence=session['sequence']+1
            # Only host-validated hex, integer and fixed URL enter shell syntax.
            # Never source worker paths or serialize a command/argument/result.
            raw=("COUNT14_NATIVE_PARENT_TICKET='"+ticket+"'\nCOUNT14_NATIVE_GIT_URL='"+self.git_url+"'\n").encode()
            temporary=self.visible_root/('.context-'+secrets.token_hex(16))
            try:
                publish_readonly_metadata(temporary,raw);self._fresh()
                need(self._control_file(path)==session['pin'],'SHELL_CONTEXT_POINTER_CHANGED')
                os.replace(temporary,path);sync_dir(self.visible_root)
                pin=hash_file(path)
                with self.ledger.tx():self.ledger.event(t,'NATIVE_SHELL_COMMAND_CONTEXT_PREPARED',
                    {'role':role,'session':token,'sequence':sequence,'generation':f['generation'],
                     'ticket_sha256':digest(ticket),'operation_id':rows[0][0],'context':pin})
                session.update(sequence=sequence,pin=pin)
            finally:
                if temporary.exists():temporary.unlink();sync_dir(self.visible_root)
            return {'ok':True,'session':token,'sequence':sequence}
