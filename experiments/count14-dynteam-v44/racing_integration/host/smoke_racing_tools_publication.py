"""Scientific guest: normal tester-account Git + append-only public tests.

Only the original native UID10000 credential installed by configure_identity is
copied, before that original CLI's normal per-turn HOME cleanup. No root token,
identity-private.json, admin, MM, model, evaluator, retry, force-push or deletion.
Scientific cases/bodies never enter PUBLIC control stdout; only fixed counts.
"""
from pathlib import Path
from urllib.parse import urlsplit,unquote
import json,os,re,secrets,stat,subprocess
from nloop.judge import write_test_dir
from common import need

WORK=Path('/work/.count14-racing')
PUBLIC_PATH='/opt/count14-racing-public-tests'


def _new(path,raw,mode):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    try:
        os.fchmod(fd,mode)
        need(os.write(fd,raw)==len(raw),'DYNTEAM_RACING_PUBLICATION_DURABLE_FIXED_METADATA_WRITE')
        os.fsync(fd)
    finally:os.close(fd)


def _regular(path,*,uid,mode=None,maximum=8192):
    path=Path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_uid==uid and not a.st_mode&0o077 and
            (mode is None or stat.S_IMODE(a.st_mode)==mode) and 0<a.st_size<=maximum,
            'DYNTEAM_RACING_ONLY_NORMAL_UID_ORIGINAL_GIT_CREDENTIAL')
        raw=os.read(fd,maximum+1);b=os.fstat(fd)
        need(len(raw)==a.st_size and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)==
            (b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns) and path.resolve()==path,
            'DYNTEAM_RACING_STABLE_NORMAL_GIT_CREDENTIAL')
        return raw
    finally:os.close(fd)


def _directory(path,uid,*,create=False,mode=0o700):
    path=Path(path)
    if create:path.mkdir(mode=mode,exist_ok=True)
    value=path.lstat();need(path.resolve()==path and stat.S_ISDIR(value.st_mode) and value.st_uid==uid and
        not value.st_mode&0o022,'DYNTEAM_RACING_EXACT_OWN_WORKSPACE_DIRECTORY')
    return path


class PublicAcceptedPublication:
    def __init__(self,*,round_ordinal,native_git,emit_public,qualification_only=False,own_root=None,own_remote=None):
        need(callable(emit_public) and type(round_ordinal) is int and round_ordinal>0,
            'DYNTEAM_RACING_PUBLICATION_FIXED_ROUND_AND_PUBLIC_COUNTER_PORT')
        need(qualification_only or own_root is own_remote is None,
            'DYNTEAM_RACING_PRODUCTION_NO_OWN_PUBLICATION_PORT')
        need(qualification_only or os.getuid()==os.getgid()==10000,
            'DYNTEAM_RACING_PUBLICATION_ORIGINAL_NATIVE_UID10000')
        self.uid=os.geteuid();self.root=WORK if own_root is None else Path(own_root)
        self.round=round_ordinal;self.emit=emit_public;self.in_round=0;self.qualification_only=qualification_only
        _directory(self.root,self.uid)
        self.public=_directory(self.root/'public-accepted-tests',self.uid,create=True,mode=0o755)
        self.private=_directory(self.root/'scientific-publication-private',self.uid,create=True)
        self.receipts=_directory(self.private/'public-receipts',self.uid,create=True)
        self.state=_directory(self.private/('round-'+str(round_ordinal)),self.uid) if (self.private/('round-'+str(round_ordinal))).exists() else None
        need(self.state is None,'DYNTEAM_RACING_PUBLICATION_ROUND_INTENT_RETAIN_NO_REPLAY')
        self.state=self.private/('round-'+str(round_ordinal));self.state.mkdir(mode=0o700)
        need(type(native_git) is dict and set(native_git)=={'host','account','credential_file'} and
             type(native_git['account']) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',native_git['account']),
             'DYNTEAM_RACING_EXACT_ORIGINAL_NATIVE_GIT_BINDING')
        self.account=native_git['account'];host=urlsplit(native_git['host'])
        need(host.scheme=='http' and host.netloc=='gitea:3000' and host.path in ('','/') and
             host.username is None and not host.query and not host.fragment,
             'DYNTEAM_RACING_ORIGINAL_NATIVE_GITEA_ORIGIN_ONLY')
        source=Path(native_git['credential_file'])
        need(qualification_only or source==Path('/opt/data/home/.git-credentials') and
             os.environ.get('AGENT_NAME')==self.account and os.environ.get('AGENT_ROLE')=='racing' and
             os.environ.get('GITEA_HOST')=='http://gitea:3000',
             'DYNTEAM_RACING_NORMAL_TESTER_ACCOUNT_ENV_AND_SOURCE_PATH')
        # Protected per-round copy survives original native per-turn HOME clean.
        raw=_regular(source,uid=self.uid);lines=raw.decode().splitlines()
        need(len(lines)==1,'DYNTEAM_RACING_ONE_NORMAL_ORIGINAL_GIT_CREDENTIAL')
        credential=urlsplit(lines[0]);need(credential.scheme==host.scheme and credential.netloc.split('@')[-1]==host.netloc and
             unquote(credential.username or '')==self.account and bool(credential.password) and credential.path in ('','/'),
             'DYNTEAM_RACING_CREDENTIAL_MATCHES_ONLY_REGISTERED_TESTER_ACCOUNT')
        self.home=self.state/'git-home';self.home.mkdir(mode=0o700)
        _new(self.home/'.git-credentials',raw,0o600)
        _new(self.home/'.gitconfig',('[credential]\n\thelper = store\n[user]\n\tname = '+self.account+
             '\n\temail = '+self.account+'@omcgitea.local\n').encode(),0o600)
        self.remote=native_git['host'].rstrip('/')+'/'+self.account+'/tests.git'
        if qualification_only:
            need(own_remote is not None and Path(own_remote).resolve()==Path(own_remote) and Path(own_remote).is_dir(),
                'DYNTEAM_RACING_OWN_BARE_REPO_EXPLICIT_ONLY')
            self.remote=str(own_remote)
        self.checkout=self.state/'original-tests-checkout';self._git('clone','--branch','main','--',self.remote,str(self.checkout))
        # Only own fixed PUBLIC receipts are enumerated, never old cases/logs.
        files=sorted(self.receipts.glob('PUBLISHED-*_PUBLIC.json'))
        need(len(files)<=100000,'DYNTEAM_RACING_PUBLIC_RECEIPT_COUNT_BOUND')
        for ordinal,path in enumerate(files,1):
            need(path.name=='PUBLISHED-'+f'{ordinal:08d}'+'_PUBLIC.json',
                 'DYNTEAM_RACING_PUBLIC_RECEIPT_ORDINAL_CONTIGUOUS')
        self.total=len(files)
        self.round_public=self.public/('round-'+f'{round_ordinal:06d}')
        self.round_public.mkdir(mode=0o755) # no overwrite/replay of a begun round
        _new(self.state/'INTENT_PUBLIC.json',json.dumps(dict(schema='count14-racing-normal-git-publication-intent-v1',
            round_ordinal=round_ordinal,original_tester_account_only=True,original_tests_repo_only=True,
            worker_acl_changed=False,official_feedback=False)).encode()+b'\n',0o400)

    def _git(self,*args,cwd=None,capture=False):
        env=dict(os.environ,HOME=str(self.home),GIT_CONFIG_NOSYSTEM='1',GIT_TERMINAL_PROMPT='0',
            GIT_ASKPASS='/bin/false',SSH_ASKPASS='/bin/false')
        for key in ('GIT_CONFIG_GLOBAL','GIT_CONFIG_COUNT','GIT_CONFIG_PARAMETERS','GIT_DIR','GIT_WORK_TREE',
                    'GIT_INDEX_FILE','GIT_COMMON_DIR'):env.pop(key,None)
        # Accepted normal Git writer: retain on wait; do not timeout-kill/replay.
        child=subprocess.Popen(['/usr/bin/git',*args],cwd=cwd,env=env,stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        out,_=child.communicate();need(child.returncode==0,'DYNTEAM_RACING_NORMAL_GIT_FAILED_RETAIN_NO_REPLAY')
        return out

    def publish(self,case_id,scientific_material):
        need(type(case_id) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',case_id),
            'DYNTEAM_RACING_PUBLIC_CASE_ORIGINAL_GAME_IDENTIFIER')
        need(type(scientific_material) is dict,'DYNTEAM_RACING_ORIGINAL_GAME_PUBLIC_CASE_MATERIAL')
        target=self.round_public/case_id
        need(not target.exists() and not target.is_symlink(),'DYNTEAM_RACING_EACH_ACCEPTED_PUBLIC_CASE_ONCE')
        pending=self.round_public/('.partial-'+case_id+'-'+secrets.token_hex(8))
        pending.mkdir(mode=0o700)
        # Original native public-case serializer; no evaluator or reference.
        write_test_dir(str(pending),'case',scientific_material)
        case=pending/'case';count=total=0
        for base,dirs,files in os.walk(case,followlinks=False):
            for name in (*dirs,*files):
                path=Path(base)/name;s=path.lstat();count+=1
                need(count<=4096 and not path.is_symlink() and path.resolve()==path and
                    (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode)),
                    'DYNTEAM_RACING_ONLY_FINITE_PUBLIC_CASE_TREE')
                if stat.S_ISREG(s.st_mode):total+=s.st_size
                need(total<=8*1024*1024,'DYNTEAM_RACING_PUBLIC_CASE_TREE_BOUND')
        # Append to the original tester-owned tests repo, not org/main and not
        # a privileged suite/reference tree. Git only ever sees public cases.
        import shutil
        rel=Path('racing-public')/self.round_public.name/case_id;repo_target=self.checkout/rel
        need(not repo_target.exists(),'DYNTEAM_RACING_NO_REPLACEMENT_OF_ORIGINAL_GIT_TREE')
        repo_target.parent.mkdir(parents=True,mode=0o755,exist_ok=True);shutil.copytree(case,repo_target,symlinks=False)
        self._git('add','--',str(rel),cwd=self.checkout)
        self._git('commit','-m','count14 racing public test '+self.round_public.name+'/'+case_id,cwd=self.checkout)
        local=self._git('rev-parse','HEAD',cwd=self.checkout,capture=True).decode().strip()
        self._git('push','origin','HEAD:refs/heads/main',cwd=self.checkout) # never force, never rewrite history
        remote=self._git('ls-remote','--heads','origin','refs/heads/main',cwd=self.checkout,capture=True).decode().split()
        need(len(remote)==2 and remote[0]==local and remote[1]=='refs/heads/main',
             'DYNTEAM_RACING_ORIGINAL_GIT_MAIN_PUBLISHED_AND_READONLY_VERIFIED')
        # Worker sees only this append-only public subtree through a RO bind.
        # Failed staged material is retained; no cleanup/delete is introduced.
        need(not target.exists(),'DYNTEAM_RACING_PUBLIC_CASE_STILL_NEW_BEFORE_PUBLIC_RENAME')
        case.rename(target);target.chmod(0o755)
        self.in_round+=1;self.total+=1
        row=dict(schema='count14-racing-public-test-published-v1',round_ordinal=self.round,
            publication_ordinal=self.total,public_tests_in_round=self.in_round,
            public_test_path=PUBLIC_PATH,normal_science_git_push=True,official_verdict=False)
        _new(self.receipts/('PUBLISHED-'+f'{self.total:08d}'+'_PUBLIC.json'),
             (json.dumps(row,sort_keys=True)+'\n').encode(),0o400)
        self.emit(row) # ONLY fixed public metadata/counts; never a case/body/SHA.
        return row
