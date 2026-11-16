"""Independent bounded PUBLIC ledger scalar sampler; no SDK, tools or models."""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_HOSTNAME = _count14_os.environ.get('COUNT14_HOSTNAME', 'count14-host')
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
import datetime,json,os,re,stat,sys
MAX_PUBLIC_LEDGER_BYTES=32*2**20
NAMES=('actual_tokens','model_calls','unknown_requests','checkpoint_ceiling')
class Refused(Exception):pass

class SelectedJSON:
 def __init__(self,text):self.text=text;self.i=0;self.depth=0;self.decoder=json.JSONDecoder()
 def ws(self):
  while self.i<len(self.text)and self.text[self.i]in' \t\r\n':self.i+=1
 def char(self,c):
  self.ws()
  if self.i>=len(self.text)or self.text[self.i]!=c:raise Refused()
  self.i+=1
 def string_end(self):
  if self.i>=len(self.text)or self.text[self.i]!='"':raise Refused()
  self.i+=1
  while self.i<len(self.text):
   c=self.text[self.i];self.i+=1
   if c=='"':return
   if ord(c)<32:raise Refused()
   if c=='\\':
    if self.i>=len(self.text):raise Refused()
    c=self.text[self.i];self.i+=1
    if c=='u':
     if not re.fullmatch('[0-9a-fA-F]{4}',self.text[self.i:self.i+4]):raise Refused()
     self.i+=4
    elif c not in'"\\/bfnrt':raise Refused()
  raise Refused()
 def skip(self):
  self.ws()
  if self.i>=len(self.text):raise Refused()
  c=self.text[self.i]
  if c=='"':self.string_end();return
  if c in'{[':
   self.depth+=1
   if self.depth>64:raise Refused()
   close='}'if c=='{'else']';self.i+=1;self.ws()
   if self.i<len(self.text)and self.text[self.i]==close:self.i+=1;self.depth-=1;return
   while True:
    if c=='{':self.string_end();self.char(':')
    self.skip();self.ws()
    if self.i>=len(self.text):raise Refused()
    if self.text[self.i]==close:self.i+=1;self.depth-=1;return
    self.char(',');self.ws()
  start=self.i
  while self.i<len(self.text)and self.text[self.i]not in',]} \t\r\n':self.i+=1
  token=self.text[start:self.i]
  if token not in('true','false','null')and not re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?',token):raise Refused()
 def select(self,wanted):
  self.char('{');out={};seen=set();self.ws()
  if self.i<len(self.text)and self.text[self.i]=='}':self.i+=1
  else:
   while True:
    start=self.i;self.string_end();key=self.decoder.decode(self.text[start:self.i])
    if key in seen or len(seen)>256:raise Refused()
    seen.add(key);self.char(':');self.ws();start=self.i
    if key in wanted:
     if self.i>=len(self.text)or self.text[self.i]in'{[':raise Refused()
     self.skip();raw=self.text[start:self.i]
     if len(raw)>128:raise Refused()
     out[key]=self.decoder.decode(raw) # only explicit top-level allowed scalars
    else:self.skip() # no JSON-decoding/materialization of unselected values
    self.ws()
    if self.i>=len(self.text):raise Refused()
    if self.text[self.i]=='}':self.i+=1;break
    self.char(',');self.ws()
  self.ws()
  if self.i!=len(self.text)or set(out)!=set(wanted):raise Refused()
  return out

def selected_text(text,names):return SelectedJSON(text).select(set(names))
def numeric_from_text(text):
 v=selected_text(text,NAMES)
 if any(type(v[k])is not int or v[k]<0 for k in NAMES):raise Refused()
 if v['actual_tokens']>v['checkpoint_ceiling']or v['checkpoint_ceiling']>100_000_000:raise Refused()
 return v

def ledger_scalar_read(p):
 p=Path(p)
 if p.name!='ledger.json'or p.resolve()!=p:raise Refused()
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  before=os.fstat(fd)
  if not stat.S_ISREG(before.st_mode)or before.st_size>MAX_PUBLIC_LEDGER_BYTES:raise Refused()
  with os.fdopen(fd,'rb',closefd=False)as f:raw=f.read(MAX_PUBLIC_LEDGER_BYTES+1)
  after=os.fstat(fd)
  if len(raw)!=before.st_size or(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise Refused()
  return numeric_from_text(raw.decode('utf-8','strict'))
 finally:os.close(fd)

def public_control_read(p):
 p=Path(p)
 if p.resolve()!=p or not p.is_file()or p.is_symlink()or p.stat().st_size>2**20:raise Refused()
 return json.loads(p.read_bytes())

def actual():
 if os.geteuid()!=0 or os.uname().nodename!=(_C14_HOSTNAME):raise Refused()
 R=Path((_C14_SCRATCH + '/cg-count14-seeds-expand8-20261021/batches/batch1'))
 I=public_control_read(R/'frozen-inputs/PILOT_INSTALLATION_EXPAND8_BATCH1_V1.json')
 seeds={'seed-1855033666':4,'seed-0185023928':5,'seed-2806506801':6};rows=[]
 for r in I['trajectories']:
  if r['setting']!='moa16':continue
  setting=Path(r['root'])/'settings/moa16'
  seed=Path(r['root']).name
  if seed not in seeds or setting!=R/'trajectories/moa16'/seed/'settings/moa16':raise Refused()
  ptr=public_control_read(setting/'SCALE46_ACTIVE_FINANCIAL_EPOCH.json');epoch=Path(ptr['epoch'])
  if epoch.resolve()!=epoch or epoch.parent!=setting/'recovery-epochs':raise Refused()
  active=ledger_scalar_read(epoch/'ledger.json');canonical=ledger_scalar_read(setting/'ledger.json')
  rows.append(dict(block=seeds[seed],active=active,canonical=canonical,selected_numeric_frontiers_equal=active==canonical))
 if len(rows)!=3 or {r['block']for r in rows}!={4,5,6}:raise Refused()
 return dict(code='SCALE46_PUBLIC_NUMERIC_FRONTIER_SCAN_COMPLETE',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),rows=rows,unselected_json_values_semantically_decoded=False,SDK_or_model_or_tool_or_control_mutations=0,private_context_pickle_logs_reads_or_hashes=0,nonatomics=True)

if __name__=='__main__':
 try:
  print(json.dumps(actual()if sys.argv[1:]==['--actual-public-numeric']else dict(code='PUBLIC_NUMERIC_READER_NO_ACTION'),sort_keys=True),flush=True)
 except BaseException as e:
  frames=[];tb=e.__traceback__
  while tb:
   frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
  print(json.dumps(dict(code='PUBLIC_NUMERIC_READER_REFUSED',exception_type=type(e).__name__,frames=frames,messages_locals_omitted=True,observation_failure_not_scientific_terminal=True)),flush=True);raise SystemExit(1)
