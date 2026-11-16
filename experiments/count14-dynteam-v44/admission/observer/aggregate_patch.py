"""One AUX health SQL aggregation correction, ONLY in a new observer child.

An intermediate POSSIBLE_EXECUTION is not final UNKNOWN if the SAME permit
has an original, matching final TERMINAL proof. No source receipt/fee/state is
changed. Actual 5xx/UNKNOWN pause incidents remain a disjoint union, once.
"""
import types
OLD='COALESCE(SUM(t.bad OR e.rid IS NOT NULL),0)'
NEW="COALESCE(SUM((t.bad AND NOT(p.state='TERMINAL'AND p.terminal_sha IS NOT NULL AND EXISTS(SELECT 1 FROM events resolved WHERE resolved.kind IN('AUX_MODEL_NO_EXECUTION_TERMINAL','AUX_MODEL_PHYSICAL_TERMINAL')AND json_extract(resolved.metadata,'$.permit_id')=p.id AND json_extract(resolved.metadata,'$.proof_sha256')=p.terminal_sha)))OR e.rid IS NOT NULL),0)"

def install(observer):
 previous=observer.native
 if getattr(previous,'_count14_aux_terminal_disambiguation_v1',False):return previous
 constants=list(previous.__code__.co_consts);matches=0
 for i,value in enumerate(constants):
  if type(value)is str and "WITH t AS(SELECT json_extract(metadata,'$.permit_id')"in value:
   if value.count(OLD)!=1:raise RuntimeError('PUBLIC_AUX_AGGREGATE_SQL_ABI_REFUSED')
   constants[i]=value.replace(OLD,NEW);matches+=1
 if matches!=1:raise RuntimeError('PUBLIC_AUX_AGGREGATE_EXACT_ONE_SQL_LITERAL_REFUSED')
 fn=types.FunctionType(previous.__code__.replace(co_consts=tuple(constants)),previous.__globals__,'native',previous.__defaults__)
 fn.__kwdefaults__=previous.__kwdefaults__;fn._count14_aux_terminal_disambiguation_v1=True;fn._count14_previous_native=previous
 observer.native=fn;return fn
