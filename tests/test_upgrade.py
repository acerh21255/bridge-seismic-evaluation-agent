import io
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from bridge_report.agent.models import create_model, validate_config, test_connection, public_config
from bridge_report.paths import TEMPLATE_DOCX
from bridge_report.server.assets import sap_geometry, template_validate
from bridge_report.server.app import App


class Case53ProvenanceTests(unittest.TestCase):
    def test_checks_match_original_rows_and_current_source(self):
        import hashlib
        from bridge_report.paths import ROOT
        folder = ROOT / 'examples/golden/53K271+730'
        data = json.loads((folder / 'handoff.json').read_text(encoding='utf-8'))
        mapping = json.loads((folder / 'extraction-map.json').read_text(encoding='utf-8'))
        source = next((ROOT / 'templates/reference').glob('*53K*.docx'))
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), mapping['source_sha256'])
        checks = {c['id']: c for c in data['checks']}
        self.assertEqual(len(checks), 62)
        for record in mapping['records']:
            check = checks[record['check_id']]
            row = record['source_row']
            self.assertEqual(check['demand'], float(row[record['demand_col']]))
            self.assertEqual(check['capacity'], float(row[record['capacity_col']]))
        self.assertEqual(data['model']['foundation']['method'], 'distributed_m')
        self.assertTrue(data['materials']['description'])
        self.assertTrue(data['materials']['rebar_intro'])


class ProtocolTests(unittest.TestCase):
    def test_relay_url_normalization(self):
        base = dict(protocol='openai-chat', model='fixture', api_key='secret')
        for protocol in ('openai-chat', 'openai-responses'):
            for url in ('https://api.example.com', 'https://api.example.com/', 'https://api.example.com/v1'):
                self.assertEqual(validate_config(base | {'protocol': protocol, 'base_url': url})['base_url'], 'https://api.example.com/v1')
        self.assertEqual(validate_config(base | {'base_url': 'https://relay.test/proxy/v2'})['base_url'], 'https://relay.test/proxy/v2')

    def test_saved_key_reuse_stays_on_original_endpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            app = App(folder)
            cfg = dict(protocol='openai-chat', model='fixture', api_key='fixture-secret', base_url='https://api.example.com')
            try:
                app.model_command(cfg)
                request = {k: v for k, v in cfg.items() if k != 'api_key'} | {'use_saved_key': True}
                with patch('bridge_report.server.app.test_connection', return_value={'ok': True}) as mock:
                    self.assertTrue(app.model_command(request, testing=True)['ok'])
                    self.assertEqual(mock.call_args.args[0]['api_key'], 'fixture-secret')
                    with self.assertRaisesRegex(ValueError, '重新填写'):
                        app.model_command(request | {'base_url': 'https://different.test'}, testing=True)
                    self.assertEqual(mock.call_count, 1)
                app.model_settings = None
                with patch('bridge_report.server.app.environment_config', return_value={}):
                    with self.assertRaises(ValueError):
                        app.model_command(request, testing=True)
            finally:
                app.pool.shutdown(wait=True)

    def test_real_adapters_use_correct_wire_protocol(self):
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                received.append((self.path,body,{k.lower():v for k,v in dict(self.headers).items()}))
                if self.path=='/v1/messages':
                    response={'id':'msg_fixture','type':'message','role':'assistant','model':'fixture-model',
                              'content':[{'type':'tool_use','id':'tool_1','name':'connection_ok','input':{}}],
                              'stop_reason':'tool_use','stop_sequence':None,'usage':{'input_tokens':10,'output_tokens':3}}
                elif self.path=='/v1/responses':
                    response={'id':'resp_fixture','object':'response','created_at':1,'status':'completed','model':'fixture-model',
                              'output':[{'type':'function_call','id':'fc_1','call_id':'call_1','name':'connection_ok','arguments':'{}','status':'completed'}],
                              'usage':{'input_tokens':10,'output_tokens':3,'total_tokens':13,'input_tokens_details':{'cached_tokens':0},'output_tokens_details':{'reasoning_tokens':0}}}
                else:
                    response={'id':'chat_fixture','object':'chat.completion','created':1,'model':'fixture-model',
                              'choices':[{'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':None,'tool_calls':[{'id':'call_1','type':'function','function':{'name':'connection_ok','arguments':'{}'}}]}}],
                              'usage':{'prompt_tokens':10,'completion_tokens':3,'total_tokens':13}}
                raw=json.dumps(response).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            cases = [('openai-chat','/v1/chat/completions'),('openai-responses','/v1/responses'),('anthropic-messages','/v1/messages')]
            for protocol,path in cases + cases[:2]:
                with self.subTest(protocol=protocol):
                    cfg={'protocol':protocol,'model':'fixture-model','api_key':'fixture-secret','base_url':f'http://127.0.0.1:{server.server_port}'+(path if len(received)<3 else ''),'max_tokens':512}
                    self.assertTrue(test_connection(cfg)['ok'])
                    self.assertEqual(received[-1][0],path)
                    self.assertIn('tools',received[-1][1])
                    self.assertNotIn('api_key',public_config(cfg))
                    body, headers = received[-1][1:]
                    self.assertEqual(body['model'], 'fixture-model')
                    if protocol == 'openai-responses':
                        self.assertIn('input', body)
                        self.assertEqual(body['max_output_tokens'], 512)
                    else:
                        self.assertIn('messages', body)
                    if protocol.startswith('openai'):
                        self.assertEqual(headers['authorization'], 'Bearer fixture-secret')
            self.assertEqual(len(received),5)
        finally:server.shutdown();server.server_close()

    def test_invalid_configs(self):
        good=dict(protocol='openai-chat',model='x',base_url='http://localhost:123/v1',api_key='secret')
        for update in ({'base_url':'https://user:secret@host/v1'},{'protocol':'unknown'},{'max_tokens':True},{'max_tokens':0},{'base_url':'https://host/v1?key=secret'}):
            with self.assertRaises(ValueError):validate_config(good|update)


class AssetsTests(unittest.TestCase):
    def test_sap_units_and_connectivity(self):
        text='''TABLE:  "PROGRAM CONTROL"
 CurrUnits="Kip, in, F"
TABLE:  "JOINT COORDINATES"
 Joint=A CoordSys=GLOBAL CoordType=Cartesian XorR=0 Y=0 Z=0
 Joint=B CoordSys=GLOBAL CoordType=Cartesian XorR=100 Y=0 Z=0
TABLE:  "CONNECTIVITY - FRAME"
 Frame=1 JointI=A JointJ=B
'''
        geometry=sap_geometry(text)
        self.assertAlmostEqual(geometry['nodes']['B'][0],2.54)
        self.assertEqual(len(geometry['edges']),1)
        with self.assertRaises(ValueError):sap_geometry(text.replace('Kip, in, F','unknown'))
        with self.assertRaises(ValueError):sap_geometry(text.replace('XorR=100','XorR=NaN'))

    def test_template_accepts_master_rejects_arbitrary_document(self):
        from docx import Document
        template_validate(TEMPLATE_DOCX.read_bytes())
        raw=io.BytesIO();doc=Document();doc.add_paragraph('arbitrary');doc.save(raw)
        with self.assertRaises(ValueError):template_validate(raw.getvalue())

    def test_preflight_does_not_run_and_secrets_not_persisted(self):
        with tempfile.TemporaryDirectory() as folder:
            app=App(folder)
            try:
                result=app.inspect({'scenario_id':'golden-76K'})
                self.assertTrue(result['ready']);self.assertEqual(app.store.list(),[])
                cfg=app.model_command(dict(protocol='anthropic-messages',model='test',base_url='http://localhost:9999',api_key='do-not-save'))
                self.assertNotIn('do-not-save',json.dumps(cfg))
                for path in Path(folder).rglob('*'):
                    if path.is_file():self.assertNotIn(b'do-not-save',path.read_bytes())
            finally:app.pool.shutdown(wait=True)

    def test_both_real_case_visuals(self):
        from bridge_report.paths import EXAMPLES_DIR
        for ident in ('golden-76K','golden-53K'):
            data=json.loads((EXAMPLES_DIR/'visuals'/f'{ident}.json').read_text(encoding='utf-8'))
            self.assertEqual(data['geometry']['units'],'m')
            self.assertGreater(len(data['geometry']['nodes']),10)
            self.assertTrue((EXAMPLES_DIR/'visuals'/f'{ident}.jpg').is_file())
