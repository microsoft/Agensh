"""Frozen optional StopSignal adapter: accept exact already-nullsafe original.
Only a prospective empty NEW owner's private instance may need selection.
No live owner, original class/global/route/hash guard or explicit signal rule changes.
"""
from pathlib import Path
from types import FunctionType,MethodType
import hashlib
SOURCE_SHA='513db38eb3e30fe7e5d93ef09b698c8e75dca9a7054085bac74647f63320474f'
ALREADY_NULLSAFE_INSPECT_SHA='742e15ccf8ab77f46dd7214a672e10a2dca08769b9a55da0996458497e241433'
OLD='{{json .Config.StopSignal}}'
NEW='{{json (index .Config "StopSignal")}}'

def need(ok,code):
    if not ok:raise ValueError(code)

def select_private_inspect(docker):
    import native_docker_scope as module
    source=Path(module.__file__);original=module.ScopedDocker.inspect;before=module.INSPECT
    need(type(docker)is module.ScopedDocker and 'inspect'not in vars(docker)and source.resolve()==source and
        not source.is_symlink()and hashlib.sha256(source.read_bytes()).hexdigest()==SOURCE_SHA and
        original.__globals__['INSPECT']==before,
        'OPTIONAL_STOPSIGNAL_ONLY_NEW_EXACT_ORIGINAL_SCOPED_DOCKER_INSTANCE')
    already=(hashlib.sha256(before.encode()).hexdigest()==ALREADY_NULLSAFE_INSPECT_SHA and
             OLD not in before and before.count('StopSignal')==2 and before.count(NEW)==1)
    if already:
        # Exact frozen full formatter, including its nil-to-empty default StopSignal branch. Do not
        # re-transform it, bind a replacement method or mutate the module.
        selected=before;converted=0
    else:
        need(before.count(OLD)==1 and NEW not in before,
             'OPTIONAL_STOPSIGNAL_ONE_OLD_TOKEN_OR_EXACT_FROZEN_ALREADY_NULLSAFE')
        selected=before.replace(OLD,NEW,1);converted=1
        need(selected.replace(NEW,OLD,1)==before,'OPTIONAL_STOPSIGNAL_ONE_TEMPLATE_TOKEN_INVERSE')
        fn=FunctionType(original.__code__,dict(original.__globals__,INSPECT=selected),original.__name__,original.__defaults__,original.__closure__)
        fn.__kwdefaults__=original.__kwdefaults__;docker.inspect=MethodType(fn,docker)
        need(fn.__code__ is original.__code__,'OPTIONAL_STOPSIGNAL_ORIGINAL_INSPECT_CODE_OBJECT')
    need(type(docker)is module.ScopedDocker and module.INSPECT==before and module.ScopedDocker.inspect is original and
        (not already or 'inspect'not in vars(docker)),
        'OPTIONAL_STOPSIGNAL_ORIGINAL_CODE_CLASS_GLOBAL_AND_ROUTE_GUARDS_PRESERVED')
    return dict(schema='count14-optional-stopsignal-private-inspect-selection-v2',
        exact_one_optional_template_token=(converted==1),inverse_template_equal=True,original_inspect_code_object_same=True,
        exact_original_formatter_already_nullsafe=already,template_tokens_converted=converted,
        original_class_method_and_module_global_unchanged=True,missing_optional_value_preserves_original_projection=True,
        route_guard_label_image_field_and_other_inspect_guards_unchanged=True,
        active_owner_or_source_or_shared_config_modified=False,container_or_financial_or_model_actions=0)
