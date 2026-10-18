import io
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from bridge_report.agent.tools import ORDER
from bridge_report.server.app import App, handler_for
from bridge_report.server.store import Store
from tests.test_chapters import load


class ServerTests(unittest.TestCase):
    def test_word_template_download_is_valid_docx(self):
        from bridge_report.server.assets import template_validate
        status, headers, raw = self.get('/api/template')
        self.assertEqual(status, 200)
        self.assertIn('wordprocessingml.document', headers['Content-Type'])
        self.assertIn('lab_template.docx', headers['Content-Disposition'])
        template_validate(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertIn('word/document.xml', archive.namelist())

    def test_demo_downloads_can_be_imported_with_assets(self):
        for case in ('golden-76K', 'golden-53K'):
            status, headers, raw = self.get('/api/demo-packages/' + case)
            self.assertEqual(status, 200)
            self.assertEqual(headers['Content-Type'], 'application/zip')
            status, result = self.post('/api/packages', raw, 'application/zip')
            self.assertEqual(status, 201)
            self.assertGreater(result['assets'], 10)
            status, inspection = self.post('/api/inspect', {'package_id': result['package_id']})
            self.assertEqual(status, 200)
            self.assertTrue(inspection['ready'], inspection['issues'])

    @classmethod
    def setUpClass(cls):
        cls.env = patch.dict(os.environ, {'BRIDGE_DISABLE_WORD': '1'})
        cls.env.start()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = App(cls.tmp.name)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(cls.app))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.app.pool.shutdown(wait=True)
        cls.env.stop()
        cls.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as response:
            return response.status, response.headers, response.read()

    def get_json(self, path):
        return json.loads(self.get(path)[2])

    def post(self, path, body, ctype='application/json', headers=None):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
        request = urllib.request.Request(self.base + path, data=data, headers={'Content-Type': ctype, **(headers or {})})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def wait(self, ident, timeout=90):
        deadline = time.time() + timeout
        while time.time() < deadline:
            run = self.get_json(f'/api/runs/{ident}')
            if run['status'] not in ('queued', 'running'):
                return run
            time.sleep(0.3)
        self.fail('任务未在限定时间内完成')

    def test_config_and_static(self):
        config = self.get_json('/api/config')
        self.assertEqual((config['app_id'], config['default_mode'], config['word_available']), ('bridge-report-agent', 'offline', False))
        status, headers, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertIn('text/html', headers['Content-Type'])
        self.assertEqual(self.get('/static/css/app.css')[0], 200)
        for bad in ('/static/../bridge_report/paths.py', '/static/%2e%2e/README.md', '/static/index.txt'):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.get(bad)
            self.assertEqual(caught.exception.code, 404)
            caught.exception.close()

    def test_scenarios_and_contract(self):
        scenarios = self.get_json('/api/scenarios')
        self.assertEqual(scenarios[0]['id'], 'golden-76K')
        self.assertEqual(self.get_json('/api/scenarios/elastic')['contract_version'], '2.0')
        self.assertEqual(self.get_json('/api/contract')['version'], '2.0')
        status, headers, body = self.get('/api/contracts/handoff.schema.json')
        self.assertIn('attachment', headers['Content-Disposition'])
        self.assertEqual(json.loads(body)['title'], '第三步到第四步交接数据 2.0')

    def test_request_validation(self):
        self.assertEqual(self.post('/api/runs', {'scenario_id': 'elastic'}, headers={'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.post('/api/runs', b'{}', ctype='text/plain')[0], 415)
        self.assertEqual(self.post('/api/runs', b'{"a": NaN}')[0], 400)
        self.assertEqual(self.post('/api/runs', {'scenario_id': 'elastic', 'package_id': 'x'})[0], 400)
        self.assertEqual(self.post('/api/runs', {'scenario_id': 'nope'})[0], 404)
        with patch.dict(os.environ, {'BRIDGE_AGENT_MODEL': ''}):
            self.assertEqual(self.post('/api/runs', {'scenario_id': 'elastic', 'mode': 'live'})[0], 400)

    def test_zip_upload_rejects_traversal(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('handoff.json', '{}')
            archive.writestr('../evil.txt', 'x')
        status, body = self.post('/api/packages', buffer.getvalue(), ctype='application/zip')
        self.assertEqual(status, 400)
        self.assertIn('不安全路径', body['error'])

    def test_scenario_run_end_to_end(self):
        status, body = self.post('/api/runs', {'scenario_id': 'elastic', 'task': '生成报告'})
        self.assertEqual(status, 202)
        run = self.wait(body['id'])
        self.assertEqual(run['status'], 'completed', run.get('error'))
        self.assertEqual(run['events'][-1]['type'], 'completed')
        self.assertEqual(run['result']['status'], 'PASS')
        self.assertEqual(run['report_status'], 'PASS')
        results = [e for e in run['events'] if e['type'] == 'tool_result']
        self.assertEqual(len(results), len(ORDER))
        self.assertTrue(all('elapsed_ms' in e for e in results))
        self.assertTrue(run['items'] and run['qa']['errors'] == [])
        names = {f['name'] for f in run['files']}
        self.assertTrue({'report.docx', 'report.html', 'result.json', 'receipt.json'} <= names)
        self.assertEqual(self.get(f"/api/runs/{run['id']}/files/report.docx")[2][:2], b'PK')
        later = self.get_json(f"/api/runs/{run['id']}?after={run['events'][-1]['seq']}")
        self.assertEqual(later['events'], [])
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get(f"/api/runs/{run['id']}/files/..%2F..%2Fruns.sqlite")
        self.assertEqual(caught.exception.code, 404)
        caught.exception.close()
        self.assertTrue(any(r['id'] == run['id'] for r in self.get_json('/api/runs')))

    def test_zip_package_run_uses_assets(self):
        package = load('golden')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('handoff.json', json.dumps(package.data, ensure_ascii=False))
            for asset in package.data['assets']:
                archive.write(package.asset_path(asset['id']), asset['path'])
        status, body = self.post('/api/packages', buffer.getvalue(), ctype='application/zip')
        self.assertEqual(status, 201, body)
        self.assertEqual(body['assets'], len(package.data['assets']))
        status, submitted = self.post('/api/runs', {'package_id': body['package_id'], 'name': 'golden.zip'})
        run = self.wait(submitted['id'])
        self.assertEqual((run['status'], run['result']['status']), ('completed', 'FAIL'))
        self.assertFalse(any('图件缺失' in w for w in run['qa']['warnings']))

    def test_inline_json_run(self):
        status, body = self.post('/api/runs', {'package': load('missing').data, 'name': 'missing.json'})
        run = self.wait(body['id'])
        self.assertEqual(run['result']['status'], 'BLOCKED')
        self.assertEqual(run['source']['kind'], 'upload-json')

    def test_restart_marks_interrupted(self):
        store = Store(os.path.join(self.tmp.name, 'other.sqlite'))
        store.save({'id': 'a' * 32, 'status': 'running'})
        store.interrupt_stale()
        self.assertEqual(store.get('a' * 32)['status'], 'interrupted')


if __name__ == '__main__':
    unittest.main()
