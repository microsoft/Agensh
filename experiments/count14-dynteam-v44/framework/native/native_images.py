"""Independent new-manifest envelope around exact original29 image guards.

Only immutable ID/ordered layer metadata is inspected. Never image config/layer
bodies, task/evaluation data, daemon mutation, container launch or retagging.
"""
from pathlib import Path
import ast,hashlib,json,re,subprocess,copy
from common import need,sha,digest,hash_file,strict
ORIGINAL_INVENTORY='eaccda446dea4a4bd007745ccd7346d50a82ffd6a4a057c56af069616adcd4ae'
TOOLCHAIN='sha256:f03b0c8ba3720f14c3be4b8e845342966c754d4abd2f417a239e88662383aa9f'
class NativeImages:
    def __init__(self,native_directory,freeze,*,manifest_sha256,inspect=None):
        code=Path(native_directory);base=Path(__file__).resolve().parent;origin=strict((base/'NATIVE_FINAL_CODE_ORIGIN.json').read_bytes())
        need(hash_file(code/'pilot_images.py')['sha256']==origin['files']['pilot_images.py'],'NATIVE_IMAGE_GUARD_SOURCE')
        need(hash_file(code/'original-images-metadata.json')['sha256']==ORIGINAL_INVENTORY,'NATIVE_IMAGE_ORIGINAL29_INVENTORY')
        text=(code/'pilot_images.py').read_text();names={'image_id','compile_freeze','inspect_metadata','resolve_image'};nodes=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)and n.name in names];need(len(nodes)==4,'NATIVE_IMAGE_ORIGINAL_FUNCTIONS')
        namespace=dict(need=need,sha=lambda v:type(v)is str and re.fullmatch('[0-9a-f]{64}',v)is not None,json=json,subprocess=subprocess,MANIFEST_SHA256=sha(manifest_sha256),INVENTORY_SHA256=ORIGINAL_INVENTORY,TOOLCHAIN_CONFIG_ID=TOOLCHAIN)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(code/'pilot_images.py'),'exec'),namespace)
        need(type(freeze)is dict and set(freeze)=={'schema','manifest_sha256','docker_host','original_inventory_sha256','images'}and freeze['schema']=='count14-agensh-images-v1'and freeze['manifest_sha256']==manifest_sha256 and freeze['docker_host']=='unix:///var/run/docker.sock'and freeze['original_inventory_sha256']==ORIGINAL_INVENTORY,'NATIVE_IMAGE_NEW_DOMAIN_ENVELOPE')
        compiled=namespace['compile_freeze'](strict((code/'original-images-metadata.json').read_bytes()),freeze['images']);need(compiled['images']==freeze['images'],'NATIVE_IMAGE_CANONICAL_MAPPING')
        self.freeze=copy.deepcopy(freeze);self.native=namespace;self.inspect=inspect or namespace['inspect_metadata'];self.content_sha256=digest(self.freeze['images'])
    def verify_evaluator_image(self,original_id,original_tag):return self.native['resolve_image'](original_id,original_tag=original_tag,freeze=self.freeze,inspect=self.inspect)
