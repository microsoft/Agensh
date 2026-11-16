"""Initial formal6 provider URL+model selection over the full original emitter.

No owner/ledger/controller/model is constructed by emission or import. The
original gateway/bridge-UID/exact-metadata/no-reference/team/source chain is
selected first. The qualified provider hook wraps only the resulting NEW
unspent factory namespace. This is not a paid/mid-trajectory restore entry.
"""
import os as _count14_os  # endpoints/keys come from environment; see CONFIGURATION.md
from pathlib import Path
from types import FunctionType
import ast,copy,hashlib,importlib,importlib.util,inspect,os,stat,textwrap

HERE=Path(__file__).resolve().parent
PREVIOUS=('formal-newroot-exact-metadata-emit-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1-msg237-locatorsuffix-v1-msg237-prefix22-v1/formal_native_metadata_emit.py',
          '2d479c459c1cbd1bfbfa717a74f9f9a0fca1afdbb6cb71f510761aa3312ac164')
PROVIDER_DIRECTORY='provider-gateway-pr1-msg221-sources-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-indexsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1'
PROVIDER_SHA='14fc456846654ea5f47600fdf3f660efb1f1fd7f7c0513b641dc483eef4daf5d'
_PARENT=None


def need(ok,code):
    if not ok:raise ValueError('FORMAL_PR1_INITIAL_'+code)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen(path,pin):
    p=Path(path);s=p.lstat()
    need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode)and
         s.st_nlink==1 and s.st_uid in(0,os.geteuid())and not stat.S_IMODE(s.st_mode)&0o222 and
         sha(p)==pin,'EXACT_FROZEN_REGULAR_SOURCE_PIN')
    return p


def previous():
    global _PARENT
    p=frozen(HERE.parent/PREVIOUS[0],PREVIOUS[1])
    if _PARENT is None:
        spec=importlib.util.spec_from_file_location('count14_pr1_initial_original_metadata_emitter',p)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);_PARENT=module
    return _PARENT


def provider():
    p=frozen(HERE.parent/PROVIDER_DIRECTORY/'newarms_provider_sources.py',PROVIDER_SHA)
    module=importlib.import_module('newarms_provider_sources')
    need(Path(module.__file__).resolve()==p,'REGISTERED_PROVIDER_IMPORT_ROOT_NOT_MODULE_ALIAS')
    module.verify_children()
    return module


def select_new_formal_factory(factory):
    # This executes ONLY the original private-constructor SOURCE selectors.
    # The gateway, UID0 bridge, exact metadata, source and all old binders stay.
    selected=previous().gateway().select_new_formal_factory(factory)
    return provider().wrap_private_factory(selected)


def select_new_source_module(module,level=0):
    parent=previous().gateway()
    original=parent.select_new_source_module
    selected=FunctionType(original.__code__,dict(vars(parent),
        select_new_formal_factory=select_new_formal_factory,
        select_new_source_module=select_new_source_module),
        original.__name__,original.__defaults__,original.__closure__)
    selected.__kwdefaults__=original.__kwdefaults__
    need(selected.__code__ is original.__code__,'ORIGINAL_COMPLETE_SOURCE_LOADER_CODETYPE')
    return selected(module,level)


def insert_selection(original):
    parent=previous();selected=parent.insert_selection(original)
    code=selected.__code__;values=list(code.co_consts)
    sites=[(i,s)for i,s in enumerate(values)if type(s)is str and
           s.startswith('# Prospective formal SAME-owner factory: import never creates owner.\n')]
    need(len(sites)==1,'ONE_ORIGINAL_GENERATED_FACTORY_SOURCE')
    index,before=sites[0]
    old_path,new_path=str(Path(parent.__file__).resolve()),str(Path(__file__).resolve())
    old_pin,new_pin=PREVIOUS[1],sha(new_path)
    need(before.count(old_path)==before.count(old_pin)==1,'EXACT_PREVIOUS_SELECTION_PATH_PIN')
    after=before.replace(old_path,new_path,1).replace(old_pin,new_pin,1)
    need(after.replace(new_path,old_path,1).replace(new_pin,old_pin,1)==before,
         'ONLY_GENERATED_SELECTOR_PATH_PIN_BYTE_INVERSE')
    values[index]=after;updated=code.replace(co_consts=tuple(values))
    need(updated.co_code==code.co_code and updated.replace(co_consts=code.co_consts)==code,
         'ORIGINAL_EMITTER_EXECUTABLE_FIELDS_PRESERVED')
    result=FunctionType(updated,selected.__globals__,selected.__name__,selected.__defaults__,selected.__closure__)
    result.__kwdefaults__=selected.__kwdefaults__;return result


def provider_pin_paths():
    # Runtime PUBLIC child indices keep their independent exact-byte pins;
    # the original import registry covers CODE only, not opaque runtime data.
    home=HERE.parent/PROVIDER_DIRECTORY
    index=home/'SOURCE_CANDIDATE_PUBLIC.json'
    import json
    value=json.loads(index.read_bytes())
    paths=[Path(__file__).resolve()]
    for name,pin in value['files'].items():
        relative=Path(name)
        need(not relative.is_absolute()and '..'not in relative.parts,'EXACT_SOURCE_RELATIVE_PATH')
        p=frozen(home/relative,pin)
        if p.suffix in('.py','.js','.mjs'):paths.append(p)
    return tuple(paths)


def compiled_emit():
    parent=previous();original=parent._emit
    tree=ast.parse(textwrap.dedent(inspect.getsource(original)));before=copy.deepcopy(tree)
    sites=[n for n in ast.walk(tree)if isinstance(n,ast.Assign)and len(n.targets)==1 and
           isinstance(n.targets[0],ast.Name)and n.targets[0].id=='required']
    need(len(sites)==1 and isinstance(sites[0].value,ast.Tuple),'ONE_ORIGINAL_PIN_LIST_ASSIGNMENT')
    sites[0].value=ast.BinOp(left=sites[0].value,op=ast.Add(),
        right=ast.Call(func=ast.Name(id='_provider_pin_paths',ctx=ast.Load()),args=[],keywords=[]))
    inverse=copy.deepcopy(tree)
    site=next(n for n in ast.walk(inverse)if isinstance(n,ast.Assign)and len(n.targets)==1 and
              isinstance(n.targets[0],ast.Name)and n.targets[0].id=='required')
    site.value=site.value.left
    need(ast.dump(inverse,include_attributes=False)==ast.dump(before,include_attributes=False),
         'FULL_ORIGINAL_EMISSION_BODY_ONE_PIN_LIST_INVERSE')
    namespace=dict(original.__globals__,insert_selection=insert_selection,_provider_pin_paths=provider_pin_paths)
    exec(compile(ast.fix_missing_locations(tree),__file__+':original-emission-plus-provider-source-pins','exec'),namespace)
    return namespace[original.__name__]


def emit_template(bindings_path,bindings_sha256,**kwargs):
    from formal_public_factory import base_helper
    need(base_helper().public(bindings_path,bindings_sha256).get('template_only')is True,
         'TEMPLATE_NOT_REAL_HOST_BINDINGS_OR_AUTHORITY')
    provider_pin_paths()
    return compiled_emit()(bindings_path,bindings_sha256,**kwargs)


def emit_formal(bindings_path,bindings_sha256,*,ram_bindings_path,**kwargs):
    parent=previous();original=parent.emit_formal
    selected=FunctionType(original.__code__,dict(original.__globals__,_emit=compiled_emit()),
        original.__name__,original.__defaults__,original.__closure__)
    selected.__kwdefaults__=original.__kwdefaults__
    result=selected(bindings_path,bindings_sha256,ram_bindings_path=ram_bindings_path,**kwargs)
    return dict(result,provider_change_id='count14-two-new-arms-GLM53FP8-gateway-pr1-msg220221',
        new_upstream_base_url=_count14_os.environ.get('COUNT14_GLM_BASE_URL', 'https://glm-gateway.example.invalid/v1'),
        new_upstream_model='GLM-5.3-FP8',
        registered_provider_only_for_NEW_unspent_formal6=True,
        all_original_gateway_bridge_USER_metadata_source_and_ACTIVATE_guards_retained=True,
        actual_provider_cutover_SYSTEM200_validator_or_paid_restore_qualified=False,
        formal_DELIVERY=False)
