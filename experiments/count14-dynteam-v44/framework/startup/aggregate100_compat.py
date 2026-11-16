"""Preserve the private16M-only branch builder after additive100M ABI changes.

No new source, candidate rule, prompt, RNG, branch budget or FINAL algorithm.
The ordinary FINAL builder still accepts only its authorized regular targets;
only this original private helper uses the sealed16M diagnostic source.
"""
import inspect,textwrap
from common import need
import v21_inputs as V

def original16_builder():
 source=textwrap.dedent(inspect.getsource(V.build))
 anchors=["d['target_tokens']in "+v for v in('(10000000,20000000)',
   '(10000000,20000000,50000000)','(10000000,20000000,50000000,100000000)')]
 matches=[a for a in anchors if source.count(a)==1]
 need(len(matches)==1,'EXP100_PRIVATE16_EXACT_ORIGINAL_SOURCE_ANCHOR')
 ns=dict(V.__dict__)
 exec(compile(source.replace(matches[0],"d['target_tokens']==16000000"),
              '<original-v21-sealed16M-base-only-authorized100m-ABI>','exec'),ns)
 return ns['build']

def install():
 import aggregate_final as A
 if getattr(A,'_expansion100_private16',False):return False
 need(A.original16_builder.__module__=='aggregate_final','EXP100_ORIGINAL_PRIVATE16_HELPER_ONLY')
 A.original16_builder=original16_builder;A._expansion100_private16=True
 return True
