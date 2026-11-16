"""Future NEW roots only: fix native error-id/team-id confusion before UP.

No existing script or current138/R6 deployment is changed. Original native
scientific sources, shell CLI/endpoints/payloads, prompts and fees stay intact.
Only one jq metadata predicate changes; the original executable-entry fix is
retained on the same freshly-created FD, without chmod of an existing node.
"""
from pathlib import Path
from types import FunctionType
import hashlib,importlib.util,os,stat
HERE=Path(__file__).resolve().parent
EXEC_LEAF='prospective-bootstrap-exec-cold-v1-msg237-prefix21-v1/bootstrap_exec_cold.py'
EXEC_SHA='b2a25562626112f18e33a6fdd413094936d77d78c0ddbb814e6189f4c388aadc'
TRUSTED_SCRIPT_SHA='7d1b165616f0119c5d86b7ed6ae1312292a5d79d508e68bdc05b811b0c457b65'
LOOKUP='''        team_id=$(curl -sS -H "Authorization: Bearer $mm_admin_token" \\
            "${MATTERMOST_HOST}/api/v4/teams/name/${MATTERMOST_TEAM_NAME}" | jq -r '.id // empty')'''
PREDICATE='''if .status_code == 404 then empty elif .status_code != null then error("COUNT14_NATIVE_TEAM_LOOKUP_UNKNOWN_REFUSED") elif (.id | type) == "string" and (.id | test("^[a-z0-9]{26}$")) then .id else error("COUNT14_NATIVE_TEAM_LOOKUP_ID_REFUSED") end'''
FIXED=LOOKUP.replace("'.id // empty'","'"+PREDICATE+"'")

def need(ok,code):
    if not ok:raise ValueError(code)
def patch_script(raw):
    need(type(raw)is bytes and hashlib.sha256(raw).hexdigest()==TRUSTED_SCRIPT_SHA,
         'FUTURE_TEAM_ONLY_ORIGINAL_PINNED_TRUSTED_BOOTSTRAP_SCRIPT')
    text=raw.decode();need(text.count(LOOKUP)==1,'FUTURE_TEAM_ONE_EXACT_ORIGINAL_TEAM_LOOKUP_METADATA_SITE')
    changed=text.replace(LOOKUP,FIXED)
    need(changed.replace(FIXED,LOOKUP)==text and changed.count(FIXED)==1,
         'FUTURE_TEAM_ALL_OTHER_BOOTSTRAP_BYTES_ENDPOINTS_PAYLOADS_AND_ROLES_UNCHANGED')
    return changed.encode()

def executable():
    p=HERE.parent/EXEC_LEAF;s=p.lstat()
    need(p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and
        not s.st_mode&0o022 and s.st_uid in(0,os.geteuid())and hashlib.sha256(p.read_bytes()).hexdigest()==EXEC_SHA,
        'FUTURE_TEAM_FROZEN_ORIGINAL_EXECUTABLE_ENTRY_COMPONENT')
    spec=importlib.util.spec_from_file_location('count14_future_team_original_exec_component',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def compiled_environment():
    e=executable();environment,proof=e.compiled_environment()
    overlay=environment.__globals__['_cold_executable_bootstrap_overlay']
    original=overlay.__globals__['scientific_bootstrap']
    def corrected(source):return patch_script(original(source))
    selected_overlay=FunctionType(overlay.__code__,dict(overlay.__globals__,scientific_bootstrap=corrected),
        overlay.__name__,overlay.__defaults__,overlay.__closure__)
    selected_overlay.__kwdefaults__=overlay.__kwdefaults__
    selected_environment=FunctionType(environment.__code__,dict(environment.__globals__,
        _cold_executable_bootstrap_overlay=selected_overlay),environment.__name__,environment.__defaults__,environment.__closure__)
    selected_environment.__kwdefaults__=environment.__kwdefaults__
    need(selected_overlay.__code__ is overlay.__code__ and selected_environment.__code__ is environment.__code__ and
        overlay.__globals__['scientific_bootstrap']is original and
        environment.__globals__['_cold_executable_bootstrap_overlay']is overlay,
        'FUTURE_TEAM_ONLY_NEW_PRIVATE_CALLABLE_GLOBALS_NOT_ORIGINAL_MODULE_OR_CLASS')
    return selected_environment,dict(original_executable_mode_compiler=proof,
        executable_555_same_FD_new_file_only=True,original_environment_and_overlay_CodeType_identical=True,
        bootstrap_generated_bytes_only_one_jq_metadata_predicate_changed=True,
        no_old_script_instance_module_or_class_mutation=True)

def prepare_new_owner(**kwargs):
    import native_cold_owner as n
    e=executable();e.pin(n,e.OWNER_SHA);fn=n.NativeColdOwner.prepare.__func__
    environment,_=compiled_environment();e.inspect.signature(fn).bind(n.NativeColdOwner,**kwargs)
    selected=FunctionType(fn.__code__,dict(fn.__globals__,prepare_environment=environment),fn.__name__,fn.__defaults__,fn.__closure__)
    selected.__kwdefaults__=fn.__kwdefaults__
    need(n.NativeColdOwner.prepare.__func__ is fn,'FUTURE_TEAM_ORIGINAL_NATIVE_CLASS_PREPARE_UNMODIFIED')
    return selected(n.NativeColdOwner,**kwargs)
