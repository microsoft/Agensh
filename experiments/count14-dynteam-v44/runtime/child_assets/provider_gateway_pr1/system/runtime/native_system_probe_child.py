#!/usr/bin/env python3
"""One ORIGINAL fixed SYSTEM probe, never a scientific model dispatcher.

Standalone -I entry: exact new owner/job, new key and X-Session-ID; original
45s alarm/600s cadence/8output/parser/classifier. No response/error bodies are
written. A closed HTTP UNKNOWN remains upper-charged SYSTEM consumption; a
missing HTTP terminal is NOT a free physical slot. No request is retried.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import signal
import stat
import sys
import uuid
from urllib.parse import urlsplit

ORIGINAL_SHA='a4dcf4a2152d345dd61b2009e563710c36a1d731d19688ed9fc767fb74f14abf'
JOB_FIELDS={'schema','sequence','request_id','session_id','owner_pid','owner_start_ticks','owner_boot_id',
            'contract_sha256','key_path','qualification_only','OWN_endpoint'}


def need(ok):
    if not ok:raise ValueError('DYNTEAM_FIXED_SYSTEM_PROBE_CHILD_GUARD')


def OWN_endpoint_ok(value):
    if type(value) is not str:return False
    try:
        u=urlsplit(value);port=u.port
        return (u.scheme=='http' and u.hostname=='127.0.0.1' and type(port) is int and 0<port<65536 and
                u.netloc=='127.0.0.1:'+str(port) and u.path=='/v1' and not u.query and not u.fragment)
    except ValueError:return False


def read_control(path,limit=16384):
    path=Path(path);need(path.is_absolute() and path.resolve()==path and not path.is_symlink())
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_uid in (0,os.geteuid()) and
             not before.st_mode&0o077 and before.st_nlink==1 and before.st_size<=limit)
        raw=os.read(fd,limit+1);after=os.fstat(fd);current=path.lstat()
        ident=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(len(raw)==before.st_size and ident(before)==ident(after)==ident(current))
        return raw
    finally:os.close(fd)


def append(path,value):
    raw=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
    fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def original():
    path=Path(__file__).resolve().parents[1]/'original-v2-system-probe-v1/original_pilot_probe.py'
    need(path.resolve()==path and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==ORIGINAL_SHA)
    spec=importlib.util.spec_from_file_location('count14_original_system_probe',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    need(module.PERIOD==600 and module.DEADLINE==45 and module.OUTPUT==8)
    return module


def validate_job(job,directory):
    need(type(job) is dict and set(job)==JOB_FIELDS and job['schema']=='count14-dynteam-system-probe-intent-v1' and
         type(job['sequence']) is int and job['sequence']>0 and
         job['request_id']=='count14-dynteam-system-'+str(uuid.UUID(job['request_id'][23:])) and
         job['session_id']==str(uuid.UUID(job['session_id'])) and type(job['qualification_only']) is bool)
    need(type(job['contract_sha256']) is str and len(job['contract_sha256'])==64 and
         all(c in '0123456789abcdef' for c in job['contract_sha256']))
    root=Path(directory);need(root.resolve()==root and root.is_dir() and not root.is_symlink() and
        root.name==f"{job['sequence']:08d}-"+job['request_id'])
    if job['qualification_only']:
        need(any(p.startswith('OWN-') for p in root.parts) and
             OWN_endpoint_ok(job['OWN_endpoint']))
    else:
        need(job['OWN_endpoint'] is None and root.is_relative_to((_C14_SCRATCH)) and os.geteuid()==0)
    pid=job['owner_pid'];need(type(pid) is int and pid>0 and os.getppid()==pid)
    fields=Path('/proc',str(pid),'stat').read_bytes().rsplit(b') ',1)[1].split()
    need(int(fields[19])==job['owner_start_ticks'] and fields[0] not in (b'Z',b'X') and
         Path('/proc/sys/kernel/random/boot_id').read_text().strip()==job['owner_boot_id'])



def _msg221_alias():
    import importlib.util
    p=Path(__file__).resolve().parents[2]/'provider_model_alias.py'
    s=p.lstat()
    import stat
    if not (p.is_absolute() and p.resolve()==p and not p.is_symlink() and
            stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid in (0,os.geteuid()) and
            stat.S_IMODE(s.st_mode)==0o444 and
            hashlib.sha256(p.read_bytes()).hexdigest()=='5924a5b99af0ebc8f6cfedaa22ea40932300259049f97f513092ded21a54a981'):
        raise ValueError('MSG221_EXACT_FROZEN_PRIVATE_ALIAS_SOURCE')
    spec=importlib.util.spec_from_file_location('count14_msg221_private_provider_alias',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

class _SystemSSEProgress:
    """Anonymous observation of the ORIGINAL response's returned lines only.

    Not socket-byte progress, a substitute SSE parser, health/physical proof,
    usage/charge authority, a retry, or an extra request. No line/body/IDs or
    error messages are retained. JSON counters concern SINGLE data lines;
    multi-line SSE may be valid even when a single data line is not JSON.
    """
    def __init__(self,deadline_type):
        self.deadline_type=deadline_type
        self.failed=False
        self.counts={k:0 for k in (
            'opener_called','opener_returned','context_enter_called',
            'context_exit_returned','readline_called','readline_returned',
            'returned_bytes','EOF_lines','blank_lines','comment_lines',
            'data_lines','other_lines','single_data_line_JSON_objects',
            'single_data_line_not_JSON','DONE_data_lines','usage_object_lines',
            'finish_stop','finish_length','finish_tool_calls','finish_other')}
        self.seen={k:False for k in (
            'content_nonempty','reasoning_nonempty','tool_calls_nonempty',
            'weight_versions_present')}

    def note(self,kind,raw=None):
        try:
            self.counts[kind]+=1
            if kind!='readline_returned':return
            self.counts['returned_bytes']+=len(raw)
            if not raw:
                self.counts['EOF_lines']+=1
                return
            line=raw.rstrip(b'\r\n')
            if not line:
                self.counts['blank_lines']+=1
                return
            if line.startswith(b':'):
                self.counts['comment_lines']+=1
                return
            if not line.startswith(b'data:'):
                self.counts['other_lines']+=1
                return
            self.counts['data_lines']+=1
            data=line[5:]
            if data.startswith(b' '):data=data[1:]
            if data==b'[DONE]':
                self.counts['DONE_data_lines']+=1
                return
            try:value=json.loads(data.decode('utf-8','strict'))
            except (UnicodeDecodeError,ValueError,RecursionError):
                self.counts['single_data_line_not_JSON']+=1
                return
            if type(value)is not dict:return
            self.counts['single_data_line_JSON_objects']+=1
            self.seen['weight_versions_present']|='weight_versions' in value
            if type(value.get('usage'))is dict:self.counts['usage_object_lines']+=1
            choices=value.get('choices')
            if type(choices)is not list:return
            for choice in choices:
                if type(choice)is not dict:continue
                reason=choice.get('finish_reason')
                if reason is not None:
                    key='finish_'+reason if type(reason)is str and reason in (
                        'stop','length','tool_calls') else 'finish_other'
                    self.counts[key]+=1
                delta=choice.get('delta')
                if type(delta)is not dict:continue
                self.seen['content_nonempty']|=bool(delta.get('content'))
                self.seen['reasoning_nonempty']|=bool(
                    delta.get('reasoning') or delta.get('reasoning_content'))
                self.seen['tool_calls_nonempty']|=bool(delta.get('tool_calls'))
        except self.deadline_type:
            # SIGALRM's original ProbeDeadline MUST reach the original probe.
            # Never consume its one alarm in an observer-only Exception catch.
            raise
        except Exception:
            self.failed=True  # No observer-only error text or payload export.

    def public(self):
        return dict(schema='count14-original-SYSTEM-returned-line-progress-v1',
            counts=dict(self.counts),seen=dict(self.seen),observer_failed=self.failed,
            bytes_are_returned_readline_bytes_not_raw_socket_bytes=True,
            no_returned_line_does_not_prove_no_partial_bytes_received=True,
            JSON_and_terminal_counts_are_single_data_line_candidates_only=True,
            original_parser_classifier_usage_and_deadline_are_authoritative=True,
            not_health_physical_slot_charge_or_ACTIVATE_authority=True,
            no_body_text_hash_ID_or_credential_exported=True,
            extra_reads=0,extra_requests=0,retries=0)


class _SystemObservedResponse:
    """Delegate the same context and each original readline exactly once."""
    def __init__(self,response,progress):
        self.response=response
        self.active=response
        self.progress=progress

    def __enter__(self):
        self.progress.note('context_enter_called')
        self.active=self.response.__enter__()
        return self

    def __exit__(self,kind,value,traceback):
        # Always let the ORIGINAL context close before observing its return.
        result=self.response.__exit__(kind,value,traceback)
        self.progress.note('context_exit_returned')
        return result

    def __getattr__(self,name):
        return getattr(self.active,name)

    def readline(self,*args,**kw):
        self.progress.note('readline_called')
        raw=self.active.readline(*args,**kw)
        self.progress.note('readline_returned',raw)
        return raw  # Same object, no filtering/decoding/reframing of the result.


def run(job,directory):
    validate_job(job,directory);P=original()
    if job['qualification_only']:P.BASE=job['OWN_endpoint'] # explicit OWN loopback only; never production fallback
    else:P.BASE=_count14_os.environ.get('COUNT14_GLM_BASE_URL', 'https://glm-gateway.example.invalid/v1') # msg220, this new child only
    _msg221_alias().configure_probe(P) # msg221: private BODY model too, before original probe/hash
    key=read_control(job['key_path'],4096).decode('utf-8','strict').strip();need(key and '\n' not in key and '\r' not in key)
    # Original fixed probe's HTTP request is unchanged apart from its already
    # approved affinity header and explicitly isolated OWN test endpoint.
    progress=_SystemSSEProgress(P.ProbeDeadline)
    def opener(request,**kw):
        request.add_header('X-Session-ID',job['session_id'])
        # Do not let an ambient HTTP proxy redirect even an OWN qualification.
        progress.note('opener_called')
        if job['qualification_only']:
            response=P.urllib.request.build_opener(P.urllib.request.ProxyHandler({})).open(request,**kw)
        else:
            response=P.urllib.request.urlopen(request,**kw)
        progress.note('opener_returned')
        return _SystemObservedResponse(response,progress)
    def alarm(*_):raise P.ProbeDeadline('DYNTEAM_ORIGINAL_SYSTEM_PROBE_DEADLINE')
    old=signal.signal(signal.SIGALRM,alarm)
    try:
        signal.setitimer(signal.ITIMER_REAL,P.DEADLINE)
        result=P.probe(key,job['request_id'],opener=opener)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
    result.update(schema='count14-dynteam-system-probe-terminal-v1',sequence=job['sequence'],
                  session_id=job['session_id'],contract_sha256=job['contract_sha256'],
                  original_probe_source_sha256=ORIGINAL_SHA,system_cost_not_experiment=True,
                  original_financial_tables_written=0,request_replays=0)
    result['upstream_model_id']=P.MODEL # configuration metadata only
    result['upstream_base_url']=P.BASE # PUBLIC configuration, no response/body
    append(Path(directory)/'TERMINAL_PUBLIC.json',result)
    # Separate diagnostic, strictly AFTER the original unchanged TERMINAL.
    # Failure cannot turn original health/UNKNOWN/fees into another outcome.
    try:
        observed=progress.public()
        observed['sequence']=job['sequence']
        observed['original_terminal_sha256']=hashlib.sha256(
            (json.dumps(result,sort_keys=True,allow_nan=False)+'\n').encode()).hexdigest()
        append(Path(directory)/'SSE_PROGRESS_PUBLIC.json',observed)
    except P.ProbeDeadline:
        raise
    except Exception:
        pass  # Observation only; no retry/second file/terminal mutation.
    return 0


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--intent',required=True);p.add_argument('--intent-sha256',required=True)
    args=p.parse_args(argv);path=Path(args.intent);raw=read_control(path)
    need(path.name=='INTENT_PUBLIC.json' and hashlib.sha256(raw).hexdigest()==args.intent_sha256)
    return run(json.loads(raw),path.parent)


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        # No message/args/locals/body; an absent terminal leaves physical
        # custody with the parent, regardless of this control exit code.
        tb=error.__traceback__;frames=[]
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='DYNTEAM_SYSTEM_PROBE_CHILD_FAILED_RETAIN',exception_type=type(error).__name__,locations=frames)))
        raise SystemExit(2)
