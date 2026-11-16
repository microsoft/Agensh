"""Original source-only count14 bootstrap for a dynamic team's NEW root.

No deployment/key/model/task reformulation. A trusted runtime consumes the
original approved source/index/description; the developer never runs this on
real inputs. Build one immutable bare bootstrap repo, NO eager worker clones.
Native agent births will clone through their unchanged Gitea lifecycle.
"""
from pathlib import Path
from types import FunctionType
import ast
import copy
import hashlib
import inspect
import json
import textwrap
import os

import bootstrap as original
from common import need,digest,sha,strict

ORIGINAL_SOURCE_SHA='50ce77463e469e2720d81250be5bcb3c1fbd7bf01c9aaa8e4b7665eccfd0cf0f'
CONFIG_PIN='c9b359f812c4b2b2601312ec566dfb091fc070354c39d9c0e223d7e57688882e'


def compiled_source_only():
    path=Path(original.__file__).resolve();raw=path.read_bytes()
    need(hashlib.sha256(raw).hexdigest()==ORIGINAL_SOURCE_SHA,'DYNTEAM_ORIGINAL_SOURCE_BOOTSTRAP_PIN')
    text=textwrap.dedent(inspect.getsource(original.bootstrap));tree=ast.parse(text);before=copy.deepcopy(tree)
    # One new host-only selector: roles=[] means publish-source-only. Original
    # source extraction, immutable refs, modes/links/mtime, description copy,
    # Git sandbox and every pin remain unchanged. No old function/global edit.
    guards=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='need'
            and len(n.args)>1 and isinstance(n.args[1],ast.Constant) and n.args[1].value=='BOOTSTRAP_ROLES']
    need(len(guards)==1,'DYNTEAM_ONE_ORIGINAL_BOOTSTRAP_ROLE_GUARD')
    prior=copy.deepcopy(guards[0].args[0]);guards[0].args[0]=ast.parse('type(roles) is list and roles == []',mode='eval').body
    reverted=copy.deepcopy(tree)
    n=next(n for n in ast.walk(reverted) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='need'
        and len(n.args)>1 and isinstance(n.args[1],ast.Constant) and n.args[1].value=='BOOTSTRAP_ROLES')
    n.args[0]=prior
    need(ast.dump(reverted,include_attributes=False)==ast.dump(before,include_attributes=False),
         'DYNTEAM_SOURCE_ONLY_SELECTOR_NO_EXTRACTION_GIT_OR_INPUT_DELTA')
    scope=dict(original.bootstrap.__globals__);exec(compile(ast.fix_missing_locations(tree),__file__+':source_only','exec'),scope)
    return scope['bootstrap']


def prepare(binding,*,contract,row,destination,qualification_only=False):
    """Normal trusted runtime port. Binding is the fixed PUBLIC path projection.

    This function DOES read approved inputs when invoked by runtime. DEV tests
    supply ONLY OWN synthetic source/task/index; never call on real configs.
    Partial destinations are retained and cannot be automatically replayed.
    """
    need(type(qualification_only) is bool and type(binding) is dict and
         binding.get('schema')=='count14-dynteam-original-source-path-binding-v1' and
         binding.get('qualification_only') is qualification_only and
         row in contract['trajectories'] and row['trajectory_id'] in [r['trajectory_id'] for r in contract['trajectories']],
         'DYNTEAM_SOURCE_BINDING_EXACT_NEW_CONTRACT_ROW')
    root=Path(row['root']);destination=Path(destination)
    need(root.is_absolute() and root.resolve()==root and root.is_dir() and destination==root/'source-bootstrap' and
         not destination.exists() and not destination.is_symlink(),'DYNTEAM_NEW_SOURCE_DESTINATION_NO_REPLAY')
    source=binding['source'];need(set(source)=={'archive','description','index','index_sha256'},
                                'DYNTEAM_SOURCE_NO_CREDENTIAL_OR_CONFIG_OBJECT_IMPORT')
    for k in ('archive','description','index'):
        p=Path(source[k]);need(p.is_absolute() and p.resolve()==p and not p.is_symlink() and p.is_file(),
                              'DYNTEAM_ORIGINAL_SOURCE_INPUT_CANONICAL')
    if qualification_only:
        need(all(any(x.startswith('OWN-') for x in Path(p).parts) for p in
                 [root,source['archive'],source['description'],source['index']]),'DYNTEAM_SOURCE_OWN_INPUTS_ONLY')
    else:
        from new_scope_ledger import ROOTS
        need(os.geteuid()==0 and any(root.is_relative_to(p) for p in ROOTS) and
             contract.get('schema')=='count14-dynteam-two-arm-public-contract-v1' and
             binding.get('original_configuration_public_pin')==CONFIG_PIN and
             binding['protocol']=={k:contract['v2_baseline_reference_protocol'][k] for k in ('source_bundle','task_description')},
             'DYNTEAM_EXACT_ORIGINAL_COUNT14_SCIENCE_INPUT_PINS')
    index=strict(Path(source['index']).read_bytes())
    need(digest(index)==sha(source['index_sha256']) and
         index['source_sha256']==binding['protocol']['source_bundle'] and
         index['task_description_sha256']==binding['protocol']['task_description'],
         'DYNTEAM_SAME_SOURCE_AND_TASK_INDEX_BEFORE_EXTRACTION')
    before=original.bootstrap.__code__
    receipt=compiled_source_only()(Path(source['archive']),Path(source['description']),index,
                                   source['index_sha256'],destination,[])
    need(original.bootstrap.__code__ is before and receipt['roles']==[] and
         not (destination/'workers').exists() and receipt['task_bytes_unchanged'] is True,
         'DYNTEAM_SOURCE_ONLY_NOT_EAGER_TEAM_OR_REWRITTEN_PROMPT')
    return dict(schema='count14-dynteam-source-only-bootstrap-public-v1',trajectory=row['trajectory_id'],
        contract_sha256=digest(contract),source_sha256=receipt['source_sha256'],
        task_description_sha256=receipt['task_description_sha256'],
        approved_input_index_sha256=receipt['approved_input_index_sha256'],
        bootstrap_commit=receipt['bootstrap_commit'],bootstrap_tree=receipt['bootstrap_tree'],
        source_root=str(destination),native_workers_created=0,model_calls=0,
        original_gitea_publication_and_task_delivery_still_required=True,qualification_only=qualification_only)
