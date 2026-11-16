"""Cold-only exact SEARCH and EVAL declared-config links.

The original SEARCH proof body/code object is retained. EVAL reuses that
identical proof with only its three pre-registered infrastructure paths.
Other routes and qualification retain original guards; no config is changed.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH1 = _count14_os.environ.get('COUNT14_SCRATCH1_ROOT', '/srv/count14/scratch1')
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
from types import FunctionType, CodeType
import ast
import copy
import hashlib
import importlib.util
import inspect
import os
import stat
import textwrap

PROJECTION_SHA256 = '66ece9e044bdde4b0742941ae390a16c9eaaf18f38c61d342224007b86fbdf26'
SELECTED_SHA256 = 'dc136c2df6e39d27b4ccb5b0c770675e85d523013933f97962a0005f7c2891f2'
ROOT = Path((_C14_SCRATCH1 + '/cg-count14-search-block456-20261031/docker'))
CONFIG = ROOT / 'daemon.json'
SOCKET = ROOT / 'docker.sock'
CONTAINERD = ROOT / 'containerd.sock'
FIELDS = {'data-root': str(ROOT / 'data'), 'exec-root': str(ROOT / 'exec'),
          'containerd': str(CONTAINERD)}


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink,
            s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def flag(args, name):
    out = []
    for i, value in enumerate(args):
        if value == name:
            need(i+1 < len(args), 'PRIVATE_CONFIG_COMPLETE_CONTROL_FLAG')
            out.append(args[i+1])
        elif value.startswith(name+b'='):
            out.append(value[len(name)+1:])
    return out


def selected_reader(module):
    path = Path(module.__file__).resolve().parents[1] / 'original-v2-resource-observer-v1/selected_numeric.py'
    need(path.resolve() == path and not path.is_symlink()
         and hashlib.sha256(path.read_bytes()).hexdigest() == SELECTED_SHA256,
         'PRIVATE_CONFIG_FIXED_ORIGINAL_SELECTED_SCALAR_PARSER')
    spec = importlib.util.spec_from_file_location('_private_config_scalar_reader', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result.SelectedJSON


def declared_link(module, reader, docker, dockerd_birth, containerd_socket, containerd_birth):
    r = docker.route
    if r.qualification_only or r.socket_path != SOCKET or r.data_root != ROOT/'data' or Path(containerd_socket) != CONTAINERD:
        return None  # NO new exception for any other route
    need(type(dockerd_birth) is type(containerd_birth) is module.ProcessBirth
         and dockerd_birth.uid == dockerd_birth.gid == containerd_birth.uid == containerd_birth.gid == 0
         and module.process_birth(dockerd_birth.pid) == dockerd_birth
         and module.process_birth(containerd_birth.pid) == containerd_birth,
         'PRIVATE_CONFIG_EXACT_FRESH_ROOT_DAEMON_BIRTHS')
    cmd = Path('/proc', str(dockerd_birth.pid), 'cmdline').read_bytes()
    need(len(cmd) <= 65536, 'PRIVATE_CONFIG_BOUNDED_OWN_DOCKERD_CONTROL_ARGV')
    args = cmd.split(b'\0')
    need(flag(args, b'--config-file') == [os.fsencode(CONFIG)]
         and not flag(args, b'--containerd')
         and flag(args, b'--data-root') in ([], [os.fsencode(ROOT/'data')])
         and flag(args, b'--exec-root') in ([], [os.fsencode(ROOT/'exec')]),
         'PRIVATE_CONFIG_EXACT_DECLARED_FILE_NO_CONFLICTING_CONTROL_OVERRIDE')
    sockets = []
    for p, birth in ((SOCKET, dockerd_birth), (CONTAINERD, containerd_birth)):
        before = p.lstat()
        need(p.resolve() == p and not p.is_symlink() and stat.S_ISSOCK(before.st_mode)
             and before.st_uid == 0, 'PRIVATE_CONFIG_CANONICAL_ROOT_SOCKET')
        module._socket_peer(p, birth)
        need(identity(before) == identity(p.lstat()), 'PRIVATE_CONFIG_SOCKET_INODE_STABLE')
        sockets.append(identity(before))
    s = CONFIG.lstat()
    need(CONFIG.resolve() == CONFIG and not CONFIG.is_symlink() and stat.S_ISREG(s.st_mode)
         and s.st_uid == s.st_gid == 0 and not s.st_mode & 0o022 and s.st_nlink == 1
         and 0 < s.st_size <= 1024*1024, 'PRIVATE_CONFIG_EXACT_ROOT_READONLY_CONTROL_FILE')
    fd = os.open(CONFIG, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        need(identity(s) == identity(os.fstat(f.fileno())), 'PRIVATE_CONFIG_OPEN_FD_IDENTITY')
        raw = f.read(1024*1024+1)
        need(len(raw) == s.st_size and identity(s) == identity(os.fstat(f.fileno())),
             'PRIVATE_CONFIG_FD_STABLE_BOUNDED_READ')
    # Original parser skips, never JSON-decodes, all other config values.
    need(reader(raw.decode('utf-8', 'strict')).select(set(FIELDS)) == FIELDS,
         'PRIVATE_CONFIG_ONLY_THREE_EXACT_CONTROL_FIELDS')
    need(identity(s) == identity(CONFIG.lstat())
         and module.process_birth(dockerd_birth.pid) == dockerd_birth
         and module.process_birth(containerd_birth.pid) == containerd_birth,
         'PRIVATE_CONFIG_CONTROL_FD_AND_DAEMON_BIRTHS_STILL_SAME')
    for (p, birth), expected in zip(((SOCKET, dockerd_birth), (CONTAINERD, containerd_birth)), sockets):
        module._socket_peer(p, birth)
        need(identity(p.lstat()) == expected, 'PRIVATE_CONFIG_SAME_SOCKET_AFTER_CONTROL_READ')
    return (identity(s), tuple(sockets), dockerd_birth, containerd_birth, cmd)


_SEARCH_DECLARED_LINK = declared_link
EVAL_ROOT = Path((_C14_SCRATCH + '/count14-eval-docker-20261030'))
EVAL_CONFIG = EVAL_ROOT/'daemon.json'
EVAL_SOCKET = EVAL_ROOT/'docker.sock'
EVAL_CONTAINERD = EVAL_ROOT/'containerd.sock'
EVAL_FIELDS = {'data-root':str(EVAL_ROOT/'docker-data'),
               'exec-root':str(EVAL_ROOT/'docker-exec'),
               'containerd':str(EVAL_CONTAINERD)}


def declared_link(module, reader, docker, dockerd_birth, containerd_socket, containerd_birth):
    if docker.route.socket_path != EVAL_SOCKET:
        return _SEARCH_DECLARED_LINK(module, reader, docker, dockerd_birth,
                                     containerd_socket, containerd_birth)
    # No looser predicate: same code object, two exact EVAL directory names
    # substituted below in the original path comparisons/override checks.
    scope = dict(_SEARCH_DECLARED_LINK.__globals__,ROOT=EVAL_ROOT,CONFIG=EVAL_CONFIG,
                 SOCKET=EVAL_SOCKET,CONTAINERD=EVAL_CONTAINERD,FIELDS=EVAL_FIELDS)
    original = _SEARCH_DECLARED_LINK
    eval_code = original.__code__
    # Original SEARCH uses ROOT/'data' and ROOT/'exec'; only those two
    # literal directory components differ in the existing EVAL deployment.
    before = eval_code.co_consts
    need(before.count('data') == before.count('exec') == 1,
         'PRIVATE_CONFIG_EXACT_ORIGINAL_DATA_EXEC_CONTROL_CONSTANTS')
    changed = tuple('docker-data' if v == 'data' else 'docker-exec' if v == 'exec' else v for v in before)
    eval_code = eval_code.replace(co_consts=changed)
    need(eval_code.co_code == original.__code__.co_code and
         eval_code.replace(co_consts=before) == original.__code__,
         'PRIVATE_CONFIG_EVAL_TWO_DIRECTORY_CONSTANTS_INVERSE_ORIGINAL_CODE')
    fn = FunctionType(eval_code,scope,original.__name__,original.__defaults__,original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn(module,reader,docker,dockerd_birth,containerd_socket,containerd_birth)


def build_projection(module):
    path = Path(module.__file__)
    raw = path.read_bytes()
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink()
         and hashlib.sha256(raw).hexdigest() == PROJECTION_SHA256,
         'PRIVATE_CONFIG_ORIGINAL_EE36_PROJECTION_SOURCE_PIN')
    original = module.docker_projection
    need(original.__globals__ is vars(module), 'PRIVATE_CONFIG_ONLY_ORIGINAL_COLD_MODULE')
    expected = [c for c in compile(raw, str(path), 'exec').co_consts
                if isinstance(c, CodeType) and c.co_name == 'docker_projection']
    need(len(expected) == 1 and original.__code__ == expected[0],
         'PRIVATE_CONFIG_EXACT_ORIGINAL_FUNCTION_CODE_OBJECT_NOT_ALREADY_PATCHED')
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    prior = copy.deepcopy(tree)
    sites = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and
             isinstance(n.func, ast.Name) and n.func.id == 'need' and len(n.args) == 2
             and isinstance(n.args[1], ast.Constant)
             and n.args[1].value == 'DYNTEAM_RESOURCE_GENUINE_MANAGED_CONTAINERD_CHILD']
    need(len(sites) == 1, 'PRIVATE_CONFIG_ONE_ORIGINAL_MANAGED_CHILD_BRANCH')
    old = copy.deepcopy(sites[0].args[0])
    sites[0].args[0] = ast.BoolOp(op=ast.Or(), values=[old, ast.parse(
        '_exact_declared_link(docker, dockerd_birth, c, containerd_birth)', mode='eval').body])
    inverse = copy.deepcopy(tree)
    restored = [n for n in ast.walk(inverse) if isinstance(n, ast.Call) and
                isinstance(n.func, ast.Name) and n.func.id == 'need' and len(n.args) == 2
                and isinstance(n.args[1], ast.Constant)
                and n.args[1].value == 'DYNTEAM_RESOURCE_GENUINE_MANAGED_CONTAINERD_CHILD']
    restored[0].args[0] = old
    need(ast.dump(inverse, include_attributes=False) == ast.dump(prior, include_attributes=False),
         'PRIVATE_CONFIG_SINGLE_BRANCH_INVERSE_ORIGINAL_AST')
    scope = dict(original.__globals__)
    exec(compile(ast.fix_missing_locations(tree), str(path)+':exact_private_config_link', 'exec'), scope)
    template = scope['docker_projection']
    reader = selected_reader(module)

    def projection(docker, *, dockerd_birth, containerd_socket, containerd_birth, images):
        proofs = []

        def exact(d, db, c, cb):
            proof = declared_link(module, reader, d, db, c, cb)
            if proof is not None:
                proofs.append(proof)
                return True
            return False

        private_scope = dict(template.__globals__, _exact_declared_link=exact)
        fn = FunctionType(template.__code__, private_scope, template.__name__, template.__defaults__)
        fn.__kwdefaults__ = template.__kwdefaults__
        value = fn(docker, dockerd_birth=dockerd_birth, containerd_socket=containerd_socket,
                   containerd_birth=containerd_birth, images=images)
        if proofs:
            need(len(proofs) == 1 and declared_link(module, reader, docker, dockerd_birth,
                 containerd_socket, containerd_birth) == proofs[0],
                 'PRIVATE_CONFIG_FRESH_AFTER_ORIGINAL_ALL_IMAGE_AND_DAEMON_QUERIES')
            value.update(private_containerd_link='EXACT_DECLARED_PRIVATE_CONFIG',
                private_config_path=str(EVAL_CONFIG if docker.route.socket_path == EVAL_SOCKET else CONFIG), private_config_three_controls_and_FD_same=True,
                managed_child_claimed=False)
        return value

    projection._original_projection = original
    projection._single_branch_inverse_AST = True
    return projection


def install_new_cold_module(module):
    """Only a newly imported cold module before consumer from-imports; no hot use."""
    private = build_projection(module)
    module.docker_projection = private
    return private
