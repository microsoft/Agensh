"""One registered PR1 provider rename, never a request replay or classifier.

Historical, hash-pinned logical model policy remains immutable. SEARCH maps
only at profile.upstream, BEFORE original UPSTREAM_PAYLOAD_PIN; AUX maps the
original verified provider options BEFORE native SENT/network construction.
No transport modifies a payload after its upstream hash. No model contents,
credentials, ledger, process, network or filesystem mutation on import.
"""
import os as _count14_os  # endpoints/keys come from environment; see CONFIGURATION.md
from pathlib import Path
from types import MethodType, CodeType
import copy
import hashlib
import json
import sys

OLD_MODEL = 'VLLM-GATEWAY-GLM-5.3-FP8'
NEW_MODEL = 'GLM-5.3-FP8'
OLD_BASE = _count14_os.environ.get('COUNT14_GLM_LEGACY_BASE_URL', 'https://glm-legacy-gateway.example.invalid/v1')
NEW_BASE = _count14_os.environ.get('COUNT14_GLM_BASE_URL', 'https://glm-gateway.example.invalid/v1')
APPROVALS = ('CARETAKER_USER_GLM_ENDPOINT_SWITCH_GATEWAY_PR1',
             'CARETAKER_APPROVE_PR1_MODEL_ID_ALIAS_GLM53FP8')
CONTRACTS = frozenset((
    'a009fcb9880fe694db540c6c9d8742d5e77ba1ce2314ee3b9018517f42f58e1e',
    '3902509c2b0daf9dea0d7421e26cf7dd29e878aebd6cdd4699615e31bd7fc937',
    '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'))
PROFILE_SHA = '3388e76335752ad2e76231a93f798dc418c6a88f8be5c2cb6d5d0541dea9976c'
RELAY_SHA = '8b50d9de9106d5dd1314dec305189691cbcb7e7a2269fa6b54821f7c860d4c1e'


def need(ok, code):
    if not ok:
        raise ValueError('MSG221_' + code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest()


def pinned_function(function, pin):
    path = Path(function.__code__.co_filename)
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
         hashlib.sha256(path.read_bytes()).hexdigest() == pin, 'ORIGINAL_SOURCE_PIN')
    def codes(code):
        return [code] + [v for c in code.co_consts if type(c) is CodeType for v in codes(c)]
    expected = compile(path.read_bytes(), str(path), 'exec', dont_inherit=True,
                       optimize=sys.flags.optimize)
    need(function.__code__ in codes(expected), 'ORIGINAL_COMPLETE_FUNCTION_CODETYPE')


def scope(contract):
    need(type(contract) is dict and digest(contract) in CONTRACTS and
         contract['schema'] == 'count14-dynteam-two-arm-public-contract-v1' and
         {a['arm'] for a in contract['arms']} == {'DYNTEAM', 'DYNTEAM_RACING'} and
         len(contract['trajectories']) == (2 if contract['mode'] == 'smoke' else 6),
         'ONLY_EXACT_REGISTERED_NEW_ARMS_NO_MOCK_OR_OTHER_ROOTS')
    return digest(contract)


def wire_model(model):
    # Keep LiteLLM's explicit provider prefix, never send it as a bare model ID.
    need(type(model) is str and model in (OLD_MODEL, 'openai/' + OLD_MODEL),
         'ONLY_APPROVED_OLD_MODEL_ALIAS_ONCE')
    return NEW_MODEL if model == OLD_MODEL else 'openai/' + NEW_MODEL


def alias_chat(chat):
    need(type(chat) is dict and chat.get('model') == OLD_MODEL, 'EXACT_LOGICAL_CHAT_MODEL')
    value = copy.deepcopy(chat)
    value['model'] = NEW_MODEL
    inverse = copy.deepcopy(value)
    inverse['model'] = OLD_MODEL
    need(inverse == chat, 'MODEL_ONLY_CHAT_INVERSE')
    return value


def install_search_profile(profile, *, contract):
    from scientific_profile import SearchProfile
    from scientific_relay import ScientificRelay
    pin = scope(contract)
    need(type(profile) is SearchProfile and
         getattr(profile, '_dynteam_contract_sha256', None) == pin and
         profile.policy['model'] == OLD_MODEL and
         not hasattr(profile, '_msg221_provider_alias'), 'ONE_NEW_ORIGINAL_PROFILE_EXACT_CONTRACT')
    original = profile.upstream
    need(type(original) is MethodType and original.__func__ is SearchProfile.upstream and
         original.__self__ is profile, 'ORIGINAL_UPSTREAM_METHOD_NOT_WRAPPED')
    pinned_function(original.__func__, PROFILE_SHA)
    pinned_function(ScientificRelay.__init__, RELAY_SHA)
    # The pinned original trusted_transport calls this method, THEN computes
    # canonical_chat_sha256, THEN calls the unchanged transport. Never post-pin.
    def upstream(this, chat, rng):
        need(this is profile and this.policy['model'] == OLD_MODEL and
             this._dynteam_contract_sha256 == pin, 'SAME_PROFILE_AT_REQUEST')
        return alias_chat(original(chat, rng))  # original seed policy executes first
    profile.upstream = MethodType(upstream, profile)
    # Msg226: a nonstream client must fail BEFORE budget reservation/SENT.
    # Native CLI already requests streaming. Do not silently change its wire
    # protocol or send a false request through a nonstream transport branch.
    original_normalize = profile.normalize
    need(type(original_normalize) is MethodType and
         original_normalize.__func__ is SearchProfile.normalize and
         original_normalize.__self__ is profile, 'ORIGINAL_NORMALIZE_METHOD')
    pinned_function(original_normalize.__func__, PROFILE_SHA)
    def normalize(this, request):
        need(this is profile and type(request) is dict and request.get('stream') is True,
             'GLM_STREAM_TRUE_REQUIRED_BEFORE_RESERVATION')
        return original_normalize(request)
    profile.normalize = MethodType(normalize, profile)
    proof = dict(schema='count14-msg221-original-profile-provider-alias-v1',
        contract_sha256=pin, logical_policy_model=OLD_MODEL, upstream_model=NEW_MODEL,
        mapping_before_original_UPSTREAM_PAYLOAD_PIN=True,
        original_normalize_bounds_rng_request_and_upstream_hash_guards_retained=True,
        transport_and_shared_profile_class_unchanged=True)
    profile._msg221_provider_alias = proof
    return dict(proof)


def alias_options(body, options):
    """Caller MUST execute original FinalBinding.seed_provider_options first."""
    need(type(body) is dict and body.get('model') == OLD_MODEL and
         type(options) is dict and options.get('base_url') in (OLD_BASE, NEW_BASE),
         'EXACT_ORIGINAL_VERIFIED_AUX_MODEL_AND_BASE')
    selected = dict(options)
    selected['model'] = wire_model(options.get('model'))
    selected['base_url'] = NEW_BASE
    inverse = dict(selected)
    inverse['model'] = options['model']
    inverse['base_url'] = options['base_url']
    need(inverse == options, 'ONLY_MODEL_AND_BASE_PROVIDER_OPTIONS_INVERSE')
    return selected


def configure_probe(module):
    # BODY was built at import time: changing MODEL alone does not change it.
    need(module.MODEL == OLD_MODEL and type(module.BODY) is dict and
         module.BODY.get('model') == OLD_MODEL and
         (module.PERIOD, module.DEADLINE, module.NORMAL_LATENCY, module.OUTPUT) == (600, 45, 30, 8),
         'ORIGINAL_FIXED_PROBE_BODY_AND_PARAMETERS')
    before = module.BODY
    selected = alias_chat(before)
    module.MODEL = NEW_MODEL
    module.BODY = selected
    need(before['model'] == OLD_MODEL and module.BODY['model'] == module.MODEL,
         'PRIVATE_PROBE_ALIAS_NOT_STALE_IMPORT_TIME_BODY')
    return dict(upstream_model=NEW_MODEL, original_fixed_probe_source_unchanged=True,
                only_private_MODEL_and_BODY_model_selected=True)
