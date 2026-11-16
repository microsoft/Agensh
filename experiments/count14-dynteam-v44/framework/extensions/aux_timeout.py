"""AUX-only explicit transport kwargs; frozen science config stays unmodified."""
from pathlib import Path
import math,functools
from common import need,digest,hash_file,publish,wire
REVISION='a4-aux-timeout900-v1'
STREAM_SHA='842c5a97fdb5e38d095a54eed1629249098bd5d63f3306619a968fc9041b4509'
SUCCESS_FIRST_CHUNK_P99=89.5033777244389
TIMEOUT=max(900.0,3*SUCCESS_FIRST_CHUNK_P99)

def selected_timeout(p99):
 need(type(p99)in(int,float)and math.isfinite(p99)and p99>=0,'AUX_TIMEOUT_PUBLIC_P99')
 return max(900.0,3*p99)

def transport(original,seconds,config):
 need(type(seconds)in(int,float)and math.isfinite(seconds)and seconds>=900,'AUX_TIMEOUT_MINIMUM_900')
 @functools.wraps(original)
 def stream(completion,options,**kwargs):
  # Use original supported kwargs rather than broadening v4_config's <=600
  # startup validator or touching SEARCH. Budget/options/inputs unchanged.
  c=config();first=max(seconds,kwargs.get('first_byte')or c.first_byte_seconds)
  idle=max(seconds,kwargs.get('idle')or c.stream_idle_seconds)
  opts=dict(options)
  # Preserve original output/decode allowance and slack while replacing ONLY
  # its first-byte allowance. Otherwise a small-output total can defeat 900s.
  need(type(opts.get('timeout'))in(int,float)and math.isfinite(opts['timeout'])and opts['timeout']>0,'AUX_TIMEOUT_ORIGINAL_FINITE_DEADLINE')
  opts['timeout']+=max(0,first-c.first_byte_seconds)
  return original(completion,opts,**{**kwargs,'first_byte':first,'idle':idle})
 return stream

def install_port(port,original_wrap,original_stream,receipt_path):
 need(port.binding.identity['purpose']=='AUX_FINALIZATION','AUX_TIMEOUT_NO_SEARCH_RUNTIME')
 need(hash_file(port.code/'cc_streaming.py')['sha256']==STREAM_SHA,'AUX_TIMEOUT_ORIGINAL_TRANSPORT_SOURCE')
 import v4_config
 wrapped=original_wrap(port,transport(original_stream,TIMEOUT,v4_config.current))
 row={'schema':'agensh-aux-only-transport-timeout-overlay-v1','revision':REVISION,
  'purpose':'AUX_FINALIZATION','seconds':TIMEOUT,'first_byte_seconds':TIMEOUT,'stream_idle_seconds':TIMEOUT,
  'successful_first_chunk_p99_seconds':SUCCESS_FIRST_CHUNK_P99,'original_stream_source_sha256':STREAM_SHA,
  'overlay_source_pin':hash_file(Path(__file__)),'v21_logic_or_inputs_modified':False,
  'search_config_modified':False,'original_raw_usage_finish_done_validation_retained':True}
 publish(receipt_path,wire(row),mode=0o400)
 return wrapped
