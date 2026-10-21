"""Exercise the standalone driver with real native ACP; only the model is a fixture."""
import datetime
import http.server
import json
import os
from pathlib import Path
import subprocess
import tarfile
import threading
import time
import unittest

SOURCE = Path(__file__).resolve().parents[1]
ROOT = SOURCE / 'out' / ('single-agent-test-' + str(time.time_ns()))
REQUESTS = []


class Model(http.server.BaseHTTPRequestHandler):
    tool_sent = False

    def log_message(self, *_):
        pass

    def do_GET(self):
        body = json.dumps({'object': 'list', 'data': [{'id': 'gpt-5.6-sol', 'object': 'model',
                                                     'owned_by': 'fixture'}]}).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        REQUESTS.append(body)
        rid = 'resume_fixture_' + str(time.time_ns())
        if not Model.tool_sent:
            self.assert_bash_available(body)
            Model.tool_sent = True
            command = (
                "printf 'real native tool ran\\n' > /workspace/resume-proof.txt; "
                "printf 'HOME persists\\n' > \"$HOME/resume-proof.txt\"; "
                "printf '#!/bin/sh\\nprintf executed\\n' > /workspace/compile.sh; "
                "chmod +x /workspace/compile.sh"
            )
            item = {'id': 'fc_' + rid, 'type': 'function_call', 'call_id': 'call_' + rid,
                    'name': 'bash', 'arguments': json.dumps({'command': command,
                    'description': 'Create native continuation and archive evidence'}), 'status': 'completed'}
        else:
            item = {'id': 'msg_' + rid, 'type': 'message', 'role': 'assistant', 'status': 'completed',
                    'content': [{'type': 'output_text', 'text': 'This prompt is complete.', 'annotations': []}]}
        response = {'id': 'resp_' + rid, 'object': 'response', 'created_at': int(time.time()),
                    'status': 'completed', 'model': body.get('model'), 'output': [item],
                    'usage': {'input_tokens': 10, 'output_tokens': 8, 'total_tokens': 18}}
        time.sleep(0.15)
        if body.get('stream'):
            events = [
                {'type': 'response.created', 'response': {**response, 'status': 'in_progress', 'output': []}},
                {'type': 'response.output_item.added', 'output_index': 0,
                 'item': {**item, 'status': 'in_progress', **({'arguments': ''} if item['type'] == 'function_call' else {'content': []})}},
            ]
            if item['type'] == 'function_call':
                events.extend([
                    {'type': 'response.function_call_arguments.delta', 'item_id': item['id'], 'output_index': 0,
                     'delta': item['arguments']},
                    {'type': 'response.function_call_arguments.done', 'item_id': item['id'], 'output_index': 0,
                     'arguments': item['arguments']},
                ])
            else:
                events.extend([
                    {'type': 'response.content_part.added', 'item_id': item['id'], 'output_index': 0,
                     'content_index': 0, 'part': {'type': 'output_text', 'text': '', 'annotations': []}},
                    {'type': 'response.output_text.delta', 'item_id': item['id'], 'output_index': 0,
                     'content_index': 0, 'delta': item['content'][0]['text']},
                    {'type': 'response.output_text.done', 'item_id': item['id'], 'output_index': 0,
                     'content_index': 0, 'text': item['content'][0]['text']},
                    {'type': 'response.content_part.done', 'item_id': item['id'], 'output_index': 0,
                     'content_index': 0, 'part': item['content'][0]},
                ])
            events.extend([{'type': 'response.output_item.done', 'output_index': 0, 'item': item},
                           {'type': 'response.completed', 'response': response}])
            data = ''.join(f"event: {event['type']}\ndata: {json.dumps({**event, 'sequence_number': i})}\n\n"
                           for i, event in enumerate(events)).encode()
            content_type = 'text/event-stream'
        else:
            data = json.dumps(response).encode()
            content_type = 'application/json'
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def assert_bash_available(self, body):
        assert 'bash' in [tool.get('name') for tool in body.get('tools', [])]


class ResumeIntegration(unittest.TestCase):
    def test_native_resume_export_and_archive(self):
        launcher = SOURCE / 'scripts/launch_single_agent.py'
        self.assertTrue(launcher.exists(), 'Dedicated standalone launcher has not been restored')
        (ROOT / 'config').mkdir(parents=True, mode=0o700)
        (ROOT / 'logs').mkdir()
        manifest = {
            'task': 'jgm__pandoc.5caad90', 'model': 'gpt-5.6-sol', 'reasoning_effort': 'high', 'hours': 6,
            'project': 'omcgitea-pbench-single-agent-test-' + str(time.time_ns()),
            'agent_image': os.environ.get('PBENCH_TEST_AGENT_IMAGE', 'omcgitea-agent-pandoc:pbench'),
            'cleanroom_image': 'programbench/jgm_1776_pandoc.5caad90:task_cleanroom_v6',
        }
        server = http.server.ThreadingHTTPServer((os.environ.get('PBENCH_TEST_GATEWAY', '172.17.0.1'), 0), Model)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        fixture_env = ROOT / 'config/fixture-model.env'
        fixture_env.write_text(f'UPSTREAM=http://{server.server_address[0]}:{server.server_port}\nUPSTREAM_AUTH_TOKEN=fixture-only\n')
        fixture_env.chmod(0o600)
        config = {**manifest, 'run_dir': str(ROOT / ('validation/native-resume-' + str(time.time_ns()))),
                  'project': manifest['project'] + '-test', 'model_env_file': str(fixture_env),
                  'deadline_seconds': 75,
                  'snapshot_seconds': 3, 'skip_eval': True, 'subnet_default': os.environ.get('PBENCH_TEST_SUBNET', '10.177.244.0/24'),
                  'subnet_egress': os.environ.get('PBENCH_TEST_EGRESS_SUBNET', '10.177.245.0/24')}
        config_path = ROOT / 'config/fixture.json'
        config_path.write_text(json.dumps(config, indent=2) + '\n')
        log = ROOT / 'logs/native-resume-test.log'
        try:
            with log.open('w') as output:
                result = subprocess.run(['python3', str(launcher), '--config', str(config_path)],
                                        stdout=output, stderr=subprocess.STDOUT, timeout=240)
            self.assertEqual(result.returncode, 0, log.read_text()[-6000:])
        finally:
            server.shutdown()
            server.server_close()
        run = Path(config['run_dir'])
        subprocess.run(['sudo', '-n', 'chown', '-R', f'{os.getuid()}:{os.getgid()}', str(run / 'data')], check=True)
        self.assertTrue((run / 'workspace/resume-proof.txt').exists(), 'Native bash was not executed')
        sessions = list((run / 'data/agents/single-agent/home/.copilot/session-state').glob('*/events.jsonl'))
        self.assertEqual(len(sessions), 1, 'Continuation must keep the same native session')
        events = [json.loads(line) for line in sessions[0].read_text().splitlines()]
        self.assertFalse([event for event in events if event.get('type') == 'session.error'])
        gaps, last_end, user_count = [], None, 0
        for event in events:
            stamp = datetime.datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
            if event['type'] == 'user.message':
                user_count += 1
                if last_end is not None:
                    gaps.append((stamp - last_end).total_seconds())
            elif event['type'] == 'assistant.turn_end':
                last_end = stamp
        self.assertGreaterEqual(user_count, 3, 'The immediate continuation loop did not repeat')
        self.assertLess(max(gaps), 3, 'Completed prompts must resume without a watchdog delay')
        self.assertTrue(REQUESTS)
        for request in REQUESTS:
            self.assertEqual(request['model'], 'gpt-5.6-sol')
            self.assertEqual(request.get('reasoning', {}).get('effort'), 'high')
            names = {tool.get('name') for tool in request.get('tools', [])}
            self.assertFalse(names.intersection({'task', 'list_agents'}))
            self.assertFalse([name for name in names if any(part in name.lower() for part in ('gitea', 'mattermost', 'board_'))])
        self.assertFalse((run / 'data/agents/single-agent/home/.claude').exists(), 'Unused Claude settings must not be installed')
        deployed_resume = (run / 'data/agents/single-agent/home/.pbench/resume.txt').read_text()
        self.assertEqual(deployed_resume, (SOURCE / 'prompts/single-agent/resume.md').read_text().rstrip('\n'))
        checks = json.loads((run / 'preflight.json').read_text())
        self.assertEqual(checks['uid'], 10000)
        self.assertFalse(checks['reference_readable'])
        self.assertTrue(checks['reference_executable'])
        self.assertFalse(checks['public_egress'])
        self.assertEqual(checks['output_threshold'], '1048576')
        manifests = list((run / 'data/agents/single-agent/shutdown').glob('*/manifest.json'))
        self.assertEqual(len(manifests), 1)
        self.assertEqual(json.loads(manifests[0].read_text())['status'], 'complete')
        with tarfile.open(manifests[0].parent / 'state.tar.gz') as bundle:
            self.assertEqual(bundle.extractfile('work/resume-proof.txt').read(), b'real native tool ran\n')
            self.assertEqual(bundle.extractfile('home/resume-proof.txt').read(), b'HOME persists\n')
        with tarfile.open(run / 'out' / manifest['task'] / 'submission.tar.gz') as bundle:
            self.assertIn('compile.sh', bundle.getnames())
            self.assertNotIn('executable', bundle.getnames())
        self.assertTrue(list((run / 'snapshots').glob('*.tar.gz')))
        remaining = subprocess.check_output(['sudo', '-n', 'docker', 'ps', '-aq', '--filter',
                                            'label=com.docker.compose.project=' + config['project']], text=True)
        self.assertEqual(remaining.strip(), '')
        result = {'native_acp': True, 'native_tool_executed': True, 'one_session': True,
                  'run_dir': str(run),
                  'incoming_prompts': user_count, 'max_resume_gap_seconds': max(gaps),
                  'model_requests': len(REQUESTS), 'delegation_excluded': True,
                  'archive_verified': True, 'submission_exported': True, 'snapshots_verified': True,
                  'isolated_resources_removed': True, 'preflight': checks}
        (ROOT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    unittest.main()
