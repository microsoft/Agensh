#!/usr/bin/env python3
"""Launch the release single-agent baseline with immediate ACP continuation."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading

SOURCE = Path(__file__).resolve().parents[1]
PROMPT_SOURCE_COMMIT = '06e16c27eebad4c7f2843cc730398df2817bf788'
DOCKER = ['sudo', '-n', '-E', 'docker']


def invoke(command, **kwargs):
    return subprocess.run([str(part) for part in command], check=True, **kwargs)


def capture(command, **kwargs):
    return subprocess.check_output([str(part) for part in command], text=True, **kwargs).strip()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def run(config_path):
    config = json.loads(config_path.read_text())
    project = config['project']
    if not re.fullmatch(r'omcgitea-pbench-single-agent-[a-z0-9-]+', project):
        raise ValueError('A unique omcgitea-pbench-single-agent-* project is required')
    if not config['cleanroom_image'].endswith(':task_cleanroom_v6'):
        raise ValueError('Only task_cleanroom_v6 is supported')
    if config['model'] != 'gpt-5.6-sol' or config['reasoning_effort'] != 'high':
        raise ValueError('This comparison requires GPT-5.6-sol/high')
    run_dir = Path(config['run_dir']).absolute()
    if run_dir.exists():
        raise ValueError('Refusing to reuse existing experiment state: ' + str(run_dir))
    if capture(DOCKER + ['ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project]):
        raise ValueError('This Compose project already has containers')
    run_dir.mkdir(mode=0o700, parents=True)
    workspace = run_dir / 'workspace'
    reference = run_dir / 'reference/executable'
    data = run_dir / 'data'
    state = data / 'agents/single-agent'
    home = state / 'home'
    home.mkdir(mode=0o755, parents=True)
    snapshots = run_dir / 'snapshots'
    snapshots.mkdir()
    status = {'status': 'preparing', 'started_at': now(), 'project': project, 'config': config}
    write_json(run_dir / 'status.json', status)
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('COPILOT_', 'ANTHROPIC_', 'UPSTREAM_', 'PBENCH_'))}
    env.update(MODEL_ENV_FILE=config['model_env_file'], SINGLE_AGENT_IMAGE=config['agent_image'],
               WORKSPACE_DIR=str(workspace), REFERENCE_BIN=str(reference), STATE_DIR=str(state),
               HOME_DIR=str(home), SUBNET_DEFAULT=config['subnet_default'], SUBNET_EGRESS=config['subnet_egress'],
               PBENCH_DOCKER='sudo -n docker')
    compose = DOCKER + ['compose', '--project-name', project, '--file',
                        str(SOURCE / 'docker/docker-compose.single-agent.yml')]
    started = False
    driver = None
    stopped = threading.Event()
    snapshot_thread = None

    def scoped_compose(*arguments, **kwargs):
        return invoke(compose + list(arguments), env=env, **kwargs)

    def git(*arguments):
        return invoke(['sudo', '-n', 'git', '-c', 'safe.directory=' + str(workspace),
                       '-c', 'user.name=cc-agent', '-c', 'user.email=cc@pbench.local',
                       '-C', workspace, *arguments])

    def snapshot_loop(container):
        interval = config.get('snapshot_seconds', 1200)
        if interval <= 0:
            return
        sequence = 0
        while not stopped.wait(interval):
            sequence += 1
            name = snapshots / f'snapshot-{sequence:03d}.tar.gz'
            try:
                invoke(DOCKER + ['exec', '-u', '10000:10000', '-w', '/workspace', container, 'sh', '-c',
                       'git add -A && (git diff --cached --quiet || git commit -qm "pbench-single-agent: snapshot")'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                with name.open('wb') as output:
                    invoke(DOCKER + ['exec', '-u', '10000:10000', '-w', '/workspace', container,
                                     'git', 'archive', '--format=tar.gz', 'HEAD'], stdout=output, timeout=30)
                print(f'[single-agent] snapshot={name.name}', flush=True)
            except (subprocess.SubprocessError, OSError) as error:
                print(f'[single-agent] snapshot failed: {type(error).__name__}', flush=True)

    try:
        cleanroom_id = capture(DOCKER + ['image', 'inspect', config['cleanroom_image'], '--format', '{{.Id}}'])
        agent_id = capture(DOCKER + ['image', 'inspect', config['agent_image'], '--format', '{{.Id}}'])
        invoke([sys.executable, SOURCE / 'tools/pbench_submission.py', 'seed', '--image', cleanroom_id,
                '--into', workspace, '--bin-out', reference], env=env)
        if not reference.is_file():
            raise RuntimeError('The v6 reference was not extracted')
        reference_hash = capture(['sudo', '-n', sys.executable, '-c',
                                 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())',
                                 reference])
        invoke(['sudo', '-n', 'chown', '0:0', reference])
        invoke(['sudo', '-n', 'chmod', '0111', reference])
        ignore = workspace / '.gitignore'
        existing = ignore.read_text() if ignore.exists() else ''
        ignore.write_text(existing + ('\n' if existing and not existing.endswith('\n') else '') + 'executable\n')
        prompt_dir = home / '.pbench'
        prompt_dir.mkdir(mode=0o755)
        prompt_hashes = {}
        for name in ('brief', 'rules', 'resume'):
            raw = (SOURCE / 'prompts/single-agent' / (name + '.md')).read_text()
            text = raw.replace('${TASK}', config['task']).replace('${HOURS}', str(config.get('hours', 6)))
            if name == 'resume':
                # The original shell launcher's command substitution strips trailing newlines.
                text = text.rstrip('\n')
            (prompt_dir / (name + '.txt')).write_text(text)
            prompt_hashes[name] = hashlib.sha256(raw.encode()).hexdigest()
        invoke(['sudo', '-n', 'chown', '-R', '10000:10000', workspace, home])
        write_json(run_dir / 'provenance.json', {'cleanroom_id': cleanroom_id, 'agent_id': agent_id,
                   'reference_sha256': reference_hash, 'prompt_source_commit': PROMPT_SOURCE_COMMIT,
                   'driver_sha256': hashlib.sha256((SOURCE / 'scripts/acp_driver.py').read_bytes()).hexdigest(),
                   'prompt_sha256': prompt_hashes})
        started = True
        scoped_compose('up', '-d', '--wait', '--wait-timeout', '120')
        container = capture(compose + ['ps', '-q', 'cc-agent'], env=env)
        probe = """import json,os,socket
s=socket.socket();s.settimeout(2)
try:
    s.connect(('1.1.1.1',443));egress=True
except OSError:
    egress=False
print(json.dumps({'uid':os.getuid(),'reference_readable':os.access('/opt/pbench/executable',os.R_OK),
'reference_executable':os.access('/opt/pbench/executable',os.X_OK),'public_egress':egress,
'output_threshold':os.environ['COPILOT_LARGE_OUTPUT_THRESHOLD_BYTES']}))
"""
        checks = json.loads(capture(DOCKER + ['exec', '-u', '10000:10000', container, 'python3', '-c', probe]))
        write_json(run_dir / 'preflight.json', checks)
        if checks != {'uid': 10000, 'reference_readable': False, 'reference_executable': True,
                      'public_egress': False, 'output_threshold': '1048576'}:
            raise RuntimeError('The real agent failed its isolation/reference preflight')
        invoke(DOCKER + ['exec', '-u', '10000:10000', '-w', '/workspace', container, 'sh', '-c',
               'git config --global user.name cc-agent && git config --global user.email cc@pbench.local '
               '&& git init -q && git add -A && git commit -qm "pbench-single-agent: seed cleanroom workspace"'])
        status.update(status='running', inference_started_at=now(), budget_seconds=config['deadline_seconds'])
        write_json(run_dir / 'status.json', status)
        print(f"[single-agent] running {project}; budget={config['deadline_seconds']}s; immediate continuation", flush=True)
        snapshot_thread = threading.Thread(target=snapshot_loop, args=(container,), daemon=True)
        snapshot_thread.start()
        with (run_dir / 'cc.log').open('w') as output:
            driver = subprocess.Popen([sys.executable, str(SOURCE / 'scripts/acp_driver.py'), '--container', container,
                     '--workspace-cwd', '/workspace', '--deadline-secs', str(config['deadline_seconds']),
                     '--brief', '/home/ccagent/.pbench/brief.txt', '--rules', '/home/ccagent/.pbench/rules.txt',
                     '--resume', '/home/ccagent/.pbench/resume.txt', '--docker', 'sudo -n docker',
                     '--session-state', str(run_dir / 'session_id.txt'),
                     '--child-stderr', str(run_dir / 'acp-child.stderr.log'), '--stuck-secs', '600'], stdout=output, stderr=subprocess.STDOUT, env=env)
            returncode = driver.wait()
        status.update(inference_finished_at=now(), driver_exit_code=returncode, status='archiving')
        write_json(run_dir / 'status.json', status)
        if returncode:
            raise RuntimeError(f'Native ACP driver failed with exit {returncode}')
    finally:
        stopped.set()
        if snapshot_thread:
            snapshot_thread.join(timeout=65)
        if driver is not None and driver.poll() is None:
            driver.terminate()
            try:
                driver.wait(timeout=10)
            except subprocess.TimeoutExpired:
                driver.kill()
                driver.wait()
        if started:
            scoped_compose('stop', '--timeout', '600', 'cc-agent')
            with (run_dir / 'compose.log').open('w') as output:
                scoped_compose('logs', '--no-color', stdout=output, stderr=subprocess.STDOUT)
            # Failed archives leave stopped containers and all data in place for recovery.
            invoke(['sudo', '-n', sys.executable, SOURCE / 'agent/archive.py', 'check', data])

    # Freeze source only after native work and detached tools have stopped.
    git('add', '-A')
    if subprocess.run(['sudo', '-n', 'git', '-c', 'safe.directory=' + str(workspace),
                       '-C', str(workspace), 'diff', '--cached', '--quiet']).returncode:
        git('commit', '-qm', 'pbench-single-agent: final snapshot')
    out = run_dir / 'out'
    invoke(['sudo', '-n', sys.executable, SOURCE / 'tools/pbench_submission.py', 'export', '--from-dir', workspace,
            '--task', config['task'], '--out-dir', out])
    invoke(['sudo', '-n', 'chown', '-R', f'{os.getuid()}:{os.getgid()}', out])
    submission = out / config['task'] / 'submission.tar.gz'
    status.update(status='exported', submission_sha256=hashlib.sha256(submission.read_bytes()).hexdigest(),
                  submitted_commit=capture(['sudo', '-n', 'git', '-c', 'safe.directory=' + str(workspace),
                                             '-C', workspace, 'rev-parse', 'HEAD']))
    write_json(run_dir / 'status.json', status)
    scoped_compose('down', '--timeout', '30')
    if not config.get('skip_eval'):
        status.update(status='evaluating', evaluation_started_at=now())
        write_json(run_dir / 'status.json', status)
        temporary = run_dir / 'evaltmp'
        temporary.mkdir()
        eval_env = env | {'PROGRAMBENCH_DOCKER_EXECUTABLE': str(SOURCE / 'scripts/pbench-docker-sudo.sh'),
                          'TMPDIR': str(temporary)}
        with (run_dir / 'eval.log').open('w') as output:
            invoke([str(Path.home() / '.local/bin/uv'), 'run', '--project', config['programbench_repo'],
                    'programbench', 'eval', out, '--filter', config['task'], '--image-tag', 'task_cleanroom_v6'],
                   env=eval_env, stdout=output, stderr=subprocess.STDOUT)
        result = out / config['task'] / (config['task'] + '.eval.json')
        if not result.is_file():
            raise RuntimeError('ProgramBench did not produce an evaluation record')
        status.update(evaluation_json=str(result), evaluation_finished_at=now())
    status.update(status='complete', finished_at=now())
    write_json(run_dir / 'status.json', status)
    print('[single-agent] complete; state=' + str(run_dir), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()

    def terminate(*_):
        raise KeyboardInterrupt('Standalone run received a termination signal')

    signal.signal(signal.SIGTERM, terminate)
    try:
        run(args.config.absolute())
    except BaseException as error:
        config = json.loads(args.config.read_text())
        status_path = Path(config['run_dir']) / 'status.json'
        if status_path.exists():
            status = json.loads(status_path.read_text())
            status.update(status='failed', failed_at=now(), error_type=type(error).__name__)
            write_json(status_path, status)
        raise
