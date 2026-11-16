"""Private exact import-name relocation on already-qualified scoped functions.

Do NOT reparse inspect.getsource on a compiled formal function: that re-reads
its old file and silently loses earlier enum/roster/host selectors. Only exact
IMPORT_NAME entries change here; inverse code equality and unchanged bytecode
are checked. No module, original function/global/class or financial SQL mutates.
"""
import dis
from types import FunctionType
from common import need,digest

PROOFS=[]


def redirect(function,*,expected_imports,old='r16_natural_contract',new='formal_natural_abi'):
    code=function.__code__;instructions=list(dis.get_instructions(code))
    sites=[i for i in instructions if i.opname=='IMPORT_NAME' and i.argval==old]
    need(len(sites)==expected_imports and expected_imports>0,'FORMAL_NATURAL_EXACT_PRIVATE_IMPORT_SITES')
    indexes={i.arg for i in sites}
    need(all(i.opname=='IMPORT_NAME' for i in instructions if i.argval==old and i.opcode in dis.hasname),
         'FORMAL_NATURAL_RELOCATED_NAME_USED_ONLY_BY_IMPORT')
    names=tuple(new if n in indexes else value for n,value in enumerate(code.co_names))
    changed=code.replace(co_names=names)
    restored=changed.replace(co_names=code.co_names)
    need(changed.co_code==code.co_code and restored==code,
         'FORMAL_NATURAL_PRIVATE_IMPORT_INVERSE_CODE_EXACT')
    result=FunctionType(changed,dict(function.__globals__),function.__name__,function.__defaults__,function.__closure__)
    result.__kwdefaults__=function.__kwdefaults__
    proof=dict(function=function.__module__+'.'+function.__qualname__,import_sites=expected_imports,
               original_module=old,new_module=new,bytecode_identical=True,inverse_code_equal=True)
    result._natural_import_relocation_proof=proof;PROOFS.append(proof)
    return result


def counted_redirect(function,*,old='r16_natural_contract',new='formal_natural_abi'):
    count=sum(i.opname=='IMPORT_NAME' and i.argval==old for i in dis.get_instructions(function))
    return redirect(function,expected_imports=count,old=old,new=new)
