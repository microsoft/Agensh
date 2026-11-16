"""Real CAS-byte binding of native consistent backups to existing ACK/capture.

This host-only component does NOT implement or fake a database backup protocol,
CLI/tool quiescence or physical proof. The registered native backup port must
first produce consistent private backup directories and its same-cut evidence.
This component captures those REAL files, pins existing ACKs to those exact
archives/root metadata/census, and rechecks the actual snapshot pack BEFORE
reference publication. Five logical services are not five physical containers.
No private paths/content are written in the public event/control receipts.
"""
from pathlib import Path
import copy,json
from common import need,sha,digest,wire,strict,private_dir
from budget import SERVICES
from snapshot import SHARED,capture
def validate_graph(graph,expected_graph_sha256):
 # Shared startup + cut validation, so malformed backup coverage is refused
 # before first model release, not discovered only at the first10M boundary.
 need(type(graph)is dict and digest(graph)==sha(expected_graph_sha256)and set(graph)==SERVICES,'SERVICE_CUT_FROZEN_GRAPH')
 objects=set()
 for domain in graph.values():
  need(type(domain)is dict and set(domain)=={'instance_sha256','backup_protocol_sha256','objects'},'SERVICE_CUT_DOMAIN_FIELDS');sha(domain['instance_sha256']);sha(domain['backup_protocol_sha256'])
  names=domain['objects'];need(type(names)is list and names and len(set(names))==len(names)and set(names)<=SHARED,'SERVICE_CUT_DOMAIN_OBJECTS');objects.update(names)
 need(objects==SHARED,'SERVICE_CUT_ALL_SHARED_COVERED')
 return graph

class NativeServiceCut:
 def __init__(self,ledger,cas,trajectory,graph,expected_graph_sha256,*,writer_owner=None):
  validate_graph(graph,expected_graph_sha256)
  self.ledger,self.cas,self.t=ledger,cas,trajectory;self.graph=copy.deepcopy(graph);self.graph_sha=digest(graph);self.receipts={};self.sources={};self.packed={};self.binding=None;self.writer_fence=None;self._capture_roles=None;self.bridge_backup=None;self.gitea_backup=None;self._gitea_backup_original=None
  with ledger.mutex:
   f=ledger.frontier(trajectory);need(f['state']=='DRAINING'and not ledger.admission_fault(trajectory),'SERVICE_CUT_DRAINING_REQUIRED');need(f['unresolved']==f['reserved']==f['active_operations']==0,'SERVICE_CUT_FULL_DRAIN_REQUIRED')
   self.cut={'trajectory':trajectory,'generation':f['generation'],'manifest_sha256':f['manifest_sha256'],'target_tokens':f['target'],'admission_closed_sequence':self._barrier_sequence(f['generation'])}
  self.cut_sha=digest(self.cut)
  from native_cli_callback_custody import registered_custody
  self.callback_custody=None if getattr(ledger,'native_unmanaged_cli',False) else registered_custody(ledger,trajectory);self.writer_owner=writer_owner
  need(self.callback_custody is None or writer_owner is self.callback_custody.team,
       'SERVICE_CUT_CALLBACK_CUSTODY_ORIGINAL_OWNER_REQUIRED')
  if writer_owner is not None:
   need(writer_owner.ledger is ledger and writer_owner.t==trajectory and writer_owner.writer_fence is not None,'SERVICE_CUT_ORIGINAL_WRITER_OWNER_REQUIRED')
   self.bind_writer_fence(writer_owner.writer_fence)
   if getattr(writer_owner,'bridge_backup',None)is not None:self.bind_bridge_backup(writer_owner.bridge_backup)
 def bind_writer_fence(self,fence):
  from native_writer_fence import NativeWriterFence
  need(type(fence)is NativeWriterFence and fence.ledger is self.ledger and fence.t==self.t,'SERVICE_CUT_ORIGINAL_WRITER_FENCE')
  need(self.writer_fence is None or self.writer_fence is fence,'SERVICE_CUT_WRITER_FENCE_REBIND_REFUSED')
  self.writer_fence=fence
 def bind_bridge_backup(self,port):
  from native_bridge_backup import NativeBridgeBackup
  need(type(port)is NativeBridgeBackup and port.ledger is self.ledger and port.t==self.t
       and self.writer_fence is not None and port.owner is self.writer_fence.owner
       and self.graph['bridge']==port.graph_domain,'SERVICE_CUT_ORIGINAL_BRIDGE_BACKUP')
  need(self.bridge_backup is None or self.bridge_backup is port,'SERVICE_CUT_BRIDGE_BACKUP_REBIND_REFUSED')
  self.bridge_backup=port
 def bind_gitea_backup(self,port):
  from native_git_repository_backup import NativeGitRepositoryBackup
  need(type(port)is NativeGitRepositoryBackup and port.ledger is self.ledger and port.t==self.t
       and self.graph['gitea']==port.graph_domain,'SERVICE_CUT_ORIGINAL_GITEA_BACKUP')
  need(self.gitea_backup is None or self.gitea_backup is port,'SERVICE_CUT_GITEA_BACKUP_REBIND_REFUSED')
  self.gitea_backup=port;self._gitea_backup_original=port
 def _barrier_sequence(self,generation):
  rows=self.ledger.db.execute("SELECT seq,metadata FROM events WHERE trajectory=? AND kind='ADMISSION_CLOSED'ORDER BY seq DESC",(self.t,)).fetchall()
  for row in rows:
   value=strict(row['metadata'])
   if type(value.get('generation'))is int and value['generation']==generation:return row['seq']
  need(False,'SERVICE_CUT_ORIGINAL_BARRIER_MISSING')
 def current(self,states):
  with self.ledger.mutex:
   need(not self.ledger.admission_fault(self.t),'SERVICE_CUT_FAULT_NO_CAPTURE');f=self.ledger.frontier(self.t)
   current={'trajectory':self.t,'generation':f['generation'],'manifest_sha256':f['manifest_sha256'],'target_tokens':f['target'],'admission_closed_sequence':self._barrier_sequence(f['generation'])}
   need(f['state']in states and digest(current)==self.cut_sha,'SERVICE_CUT_CHANGED_OR_WRONG_STATE');need(f['unresolved']==f['reserved']==f['active_operations']==0,'SERVICE_CUT_FULL_DRAIN_REQUIRED');return f
 def record_native_backup(self,component,sources,native_evidence):
  """Trusted native port calls once AFTER its successful consistent backup.

  Native evidence SHA references the port's real custody/protocol receipt and
  exact cut. It is not worker JSON, a guessed success flag or a SQL hot-copy
  proof. This method then seals actual files into the same CAS used by capture.
  A failure never reexecutes the native backup or releases admission.
  """
  self.current({'DRAINING'});need(component in self.graph and component not in self.receipts,'SERVICE_CUT_COMPONENT_ONCE');domain=self.graph[component]
  need(type(sources)is dict and set(sources)==set(domain['objects']),'SERVICE_CUT_BACKUP_COVERAGE')
  need(type(native_evidence)is dict and set(native_evidence)=={'cut_sha256','instance_sha256','backup_protocol_sha256','receipt_sha256'},'SERVICE_CUT_NATIVE_EVIDENCE_FIELDS')
  for v in native_evidence.values():sha(v)
  need(native_evidence['cut_sha256']==self.cut_sha and native_evidence['instance_sha256']==domain['instance_sha256']and native_evidence['backup_protocol_sha256']==domain['backup_protocol_sha256'],'SERVICE_CUT_NATIVE_EVIDENCE_IDENTITY')
  sealed={}
  for name,path in sorted(sources.items()):
   source=private_dir(path);actual=self.cas.capture_tree(source)
   if name in self.packed:need(digest(self.packed[name])==digest(actual),'SERVICE_CUT_SHARED_BACKUP_CONFLICT')
   sealed[name]=actual
  self.current({'DRAINING'})
  receipt={'cut':self.cut,'graph_sha256':self.graph_sha,'component':component,'native_evidence':native_evidence,'objects':sealed};reference=self.cas.store_bytes(wire(receipt))
  # Store only hashes in the append-only ledger; exact source paths stay private.
  with self.ledger.tx():self.ledger.event(self.t,'NATIVE_SERVICE_BACKUP_SEALED',{'cut_sha256':self.cut_sha,'component':component,'receipt_sha256':reference['sha256'],'graph_sha256':self.graph_sha})
  self.ledger.ack(self.t,component,self.cut['generation'],reference['sha256']);self.receipts[component]=reference;self.sources.update({n:Path(p)for n,p in sources.items()});self.packed.update(sealed);return reference
 def guard(self,draft):
  from native_cli_callback_custody import registered_custody
  registered=None if getattr(self.ledger,'native_unmanaged_cli',False) else registered_custody(self.ledger,self.t)
  need(self.callback_custody is registered,'SERVICE_CUT_CALLBACK_CUSTODY_BINDING_CHANGED')
  if registered is not None:registered.verify_capture(self,self._capture_roles,draft['pins'])
  if self.writer_fence is not None:self.writer_fence.verify_capture(self,self._capture_roles)
  self.current({'CAPTURING'});need(set(self.receipts)==SERVICES and set(self.packed)==SHARED,'SERVICE_CUT_ALL_RECEIPTS_REQUIRED')
  need(draft['trajectory']==self.t and type(draft['generation'])is int and draft['generation']==self.cut['generation']and draft['pins']['manifest']==self.cut['manifest_sha256']and draft['target_tokens']==self.cut['target_tokens'],'SERVICE_CUT_SNAPSHOT_IDENTITY')
  with self.ledger.mutex:
   acks={r['component']:r['receipt_sha']for r in self.ledger.db.execute('SELECT component,receipt_sha FROM acks WHERE trajectory=?AND generation=?',(self.t,self.cut['generation']))if r['component']in SERVICES}
  need(acks=={n:ref['sha256']for n,ref in self.receipts.items()},'SERVICE_CUT_ACK_REFERENCE_MISMATCH')
  for component,reference in self.receipts.items():
   receipt=strict(self.cas.resolve(reference).read_bytes());need(digest(receipt['cut'])==self.cut_sha and receipt['graph_sha256']==self.graph_sha and receipt['component']==component,'SERVICE_CUT_STORED_RECEIPT_IDENTITY')
   for name,obj in receipt['objects'].items():
    self.cas.resolve(obj['archive']);need(digest(draft['shared'][name])==digest(obj),'SERVICE_CUT_ACK_PACK_BYTES_MISMATCH')
  registered=getattr(self.writer_fence.owner,'bridge_backup',None)if self.writer_fence is not None else None
  need(self.bridge_backup is registered,'SERVICE_CUT_REGISTERED_BRIDGE_BINDING_CHANGED')
  if registered is not None:registered.verify_capture(self,draft)
  need(self.gitea_backup is self._gitea_backup_original,'SERVICE_CUT_REGISTERED_GITEA_BINDING_CHANGED')
  if self._gitea_backup_original is not None:self._gitea_backup_original.verify_capture(self,draft)
  binding={'cut':self.cut,'graph_sha256':self.graph_sha,'receipts':self.receipts,'objects':self.packed,'capturing_ledger_frontier':draft['ledger_frontier']};reference=self.cas.store_bytes(wire(binding))
  # The CAPTURING ledger backup is earlier than this event/reference. It must
  # not contain its own future commit/ref; no circular SHA/sequence condition.
  with self.ledger.tx():self.ledger.event(self.t,'NATIVE_SERVICE_CUT_ARCHIVES_BOUND',{'cut_sha256':self.cut_sha,'binding_sha256':reference['sha256'],'graph_sha256':self.graph_sha})
  self.binding=reference
 def capture(self,*,roles,pins,parent=None):
  self.current({'DRAINING'});need(set(self.receipts)==SERVICES and set(self.sources)==SHARED,'SERVICE_CUT_ALL_RECEIPTS_REQUIRED')
  try:
   self._capture_roles=roles
   if self.writer_fence is not None:
    self.writer_fence.verify_capture(self,roles)
    need(pins.get('native_writer_fence')==self.writer_fence.receipt['sha256'],'SERVICE_CUT_WRITER_PROOF_PIN_REQUIRED')
   return capture(self.cas,self.ledger,self.t,roles=roles,shared=self.sources,pins=pins,parent=parent,publication_guard=self.guard)
  except Exception:
   self.ledger.latch_fault(self.t,'NATIVE_SERVICE_CUT_CAPTURE_INCOMPLETE_NO_RETRY');raise
