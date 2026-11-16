"""Bounded tar metadata parser; non-ordinary entries are always inert.

No extraction, member-payload access, link lookup or OS special-file creation.
Unknown type bytes are counted as other, never interpreted as regular content.
This is shared reader plumbing, not scope/cap/queue authority.
"""
import tarfile
class Stop(Exception):pass

def need(ok,reason):
 if not ok:raise Stop(reason)

def empty_special_counts():return dict(fifo=0,socket=0,char=0,block=0,hardlink=0,other=0)

def special_kind(member):
 # Socket has no stdlib TarInfo constant: accept explicit s extension or a
 # declared SCHILY.filetype=socket. This is a classification convention, not
 # an assertion about the rejected byte from the preserved1092 actual run.
 pax=member.pax_headers
 if member.type==tarfile.GNUTYPE_SPARSE or any(k.startswith('GNU.sparse') for k in pax):return 'other'
 if pax.get('SCHILY.filetype')=='socket' or member.type==b's':return 'socket'
 kinds={tarfile.FIFOTYPE:'fifo',tarfile.CHRTYPE:'char',tarfile.BLKTYPE:'block',tarfile.LNKTYPE:'hardlink'}
 if member.type in kinds:return kinds[member.type]
 if member.type not in (tarfile.REGTYPE,tarfile.AREGTYPE,tarfile.DIRTYPE,tarfile.SYMTYPE):return 'other'
 return None

class Header(tarfile.TarInfo):
 zero=False;bounds={'extension_bytes':2**20}
 @classmethod
 def _fromtarfile(cls,archive,*,dircheck=True):
  buf=archive.fileobj.read(512);cls.zero=buf==bytes(512)
  parser=super()
  if hasattr(parser,'_frombuf'):item=parser._frombuf(buf,archive.encoding,archive.errors,dircheck=dircheck)
  else:item=parser.frombuf(buf,archive.encoding,archive.errors)
  need(item.size>=0,'NEGATIVE_MEMBER_SIZE')
  if item.type in (tarfile.XHDTYPE,tarfile.XGLTYPE,tarfile.SOLARIS_XHDTYPE,tarfile.GNUTYPE_LONGNAME,tarfile.GNUTYPE_LONGLINK):need(item.size<=cls.bounds['extension_bytes'],'HEADER_EXTENSION_BOUND')
  item.offset=archive.fileobj.tell()-512
  return item._proc_member(archive)
 @classmethod
 def fromtarfile(cls,archive):return cls._fromtarfile(archive)
 def _proc_builtin(self,archive):
  # All physical bytes are skipped as part of streaming decompression; no
  # entry body is opened/interpreted. For non-ordinary entries with a nonzero
  # size, skip exactly its stored length, rather than treating it as a file.
  self.offset_data=archive.fileobj.tell()
  self._apply_pax_info(archive.pax_headers,archive.encoding,archive.errors)
  need(self.size>=0,'NEGATIVE_MEMBER_SIZE')
  archive.offset=self.offset_data+self._block(self.size)
  if self.isdir():self.name=self.name.rstrip('/')
  return self
 def _apply_pax_info(self,headers,encoding,errors):
  # GNU logical sparse size is NOT the stored byte length. Count this member
  # as other and preserve its stored span; do not materialize holes or parse
  # an in-body sparse map. Normal PAX size/path/link metadata remains parsed.
  filtered={k:v for k,v in headers.items() if not k.startswith('GNU.sparse')}
  super()._apply_pax_info(filtered,encoding,errors)
  self.pax_headers=headers.copy()
 def _proc_pax(self,archive):
  member=super()._proc_pax(archive)
  need(member.size>=0,'NEGATIVE_MEMBER_SIZE')
  # stdlib recomputation normally assumes special entries have zero size.
  # Count-only handling must skip the stored span even for a PAX size on one.
  archive.offset=member.offset_data+member._block(member.size)
  return member
 def _proc_sparse(self,archive):
  # Old GNU sparse extension blocks are header metadata, not file payload.
  # Consume only their chained512B framing flags with the same fixed header
  # extension bound; never interpret offsets/map data or expand sparse data.
  _,extended,_=self._sparse_structs;used=0
  while extended:
   used+=512;need(used<=self.bounds['extension_bytes'],'HEADER_EXTENSION_BOUND')
   block=archive.fileobj.read(512);need(len(block)==512,'TRUNCATED_SPARSE_HEADER')
   extended=bool(block[504])
  return self._proc_builtin(archive)
 def _proc_gnusparse_00(self,next,*_):pass
 def _proc_gnusparse_01(self,next,*_):pass
 def _proc_gnusparse_10(self,next,*_):pass
