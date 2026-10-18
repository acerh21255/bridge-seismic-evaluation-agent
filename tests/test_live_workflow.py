"""Exercise the actual HTTP model adapter and Agent loop without a remote paid call."""
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from bridge_report.agent.models import create_model
from bridge_report.agent.runtime import build_agent
from bridge_report.agent.tools import ORDER
from tests.test_chapters import load


class LiveWorkflowTests(unittest.TestCase):
    def test_http_model_calls_every_tool_and_returns_explanation(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body)
                index = len(requests) - 1
                message = {'role': 'assistant', 'content': '按工具判定完成复核，工程签发仍需专业复核。'}
                finish = 'stop'
                if index < len(ORDER):
                    message.update(content=None, tool_calls=[{'id': f'call-{index}', 'type': 'function',
                        'function': {'name': ORDER[index], 'arguments': '{}'}}])
                    finish = 'tool_calls'
                data = json.dumps({'id': f'chat-{index}', 'object': 'chat.completion', 'created': 1,
                    'model': 'local-test', 'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
                    'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'BRIDGE_DISABLE_WORD': '1'}):
                model = create_model(dict(protocol='openai-chat', base_url=f'http://127.0.0.1:{server.server_port}',
                    model='local-test', api_key='test-only', max_tokens=512))
                graph, state = build_agent(model, load('elastic'), folder)
                task = '完成完整报告交付，并重点解释加固后复核结论。'
                result = graph.invoke({'messages': [{'role': 'user', 'content': task}]})
                self.assertEqual(state['done'], list(ORDER))
                self.assertIsNotNone(state['receipt'])
                self.assertEqual(len(requests), len(ORDER) + 1)
                self.assertIn(task, str(requests[0]['messages']))
                self.assertIn('专业复核', result['messages'][-1].content)
                self.assertTrue(any(m['role'] == 'tool' for m in requests[-1]['messages']))
        finally:
            server.shutdown()
            server.server_close()
