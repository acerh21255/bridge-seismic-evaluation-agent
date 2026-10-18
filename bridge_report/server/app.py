"""Local HTTP service: static workbench, scenario and contract API, package upload, runs, files and page previews."""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from ..agent.runtime import live_config
from ..agent.models import environment_config, validate_config, public_config, test_connection, safe_error
from .assets import AssetService, template_validate
from ..paths import TEMPLATE_DOCX
from ..contract.package import Package, PackageError, inside, load_file, load_zip, parse_json
from ..engine.gates import validate
from ..paths import CONTRACTS_DIR, EXAMPLES_DIR, SCENARIOS_DIR, STATIC_DIR, BUILD_DIR
from ..report.office import word_available
from .runner import FILE_TYPES, Runner, input_summary
from .store import Store, dump

APP_ID = 'bridge-report-agent'
VERSION = '3.3.0'


def source_revision():
    """Identify loaded backend code so the launcher never reuses stale handlers."""
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*.py')):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


SOURCE_REVISION = source_revision()
DEFAULT_PORT = 8766
MAX_JSON = 5 * 1024 * 1024
MAX_ZIP = 50 * 1024 * 1024
STATIC_TYPES = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.woff2': 'font/woff2'}
CONTRACT_FILES = ('handoff.template.json', 'handoff.schema.json')
RUN_PATH = re.compile(r'/api/runs/([a-f0-9]{32})(?:/(files|pages)/([A-Za-z0-9.\-]+))?')


class Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR would let a second instance bind the same port; keep the binding exclusive.
    allow_reuse_address = os.name != 'nt'
    daemon_threads = True


class RequestError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class App:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.store = Store(self.data_dir / 'runs.sqlite')
        self.store.interrupt_stale()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='report-agent')
        self.runner = Runner(self.store, self.data_dir, self.pool)
        self.lock = threading.Lock()
        self.model_settings = None
        self.assets = AssetService(self.data_dir)

    # -- queries -----------------------------------------------------------------------------------
    def config(self):
        cfg = self.model_settings or environment_config()
        live = all(cfg.get(k) for k in ('model', 'base_url', 'api_key'))
        return {'app_id': APP_ID, 'version': VERSION, 'source_revision': SOURCE_REVISION, 'contract_version': '2.0', 'default_mode': 'offline',
                'live_available': live, 'model': cfg['model'] if live else None, 'model_config': public_config(cfg),
                'word_available': word_available()}

    def scenarios(self):
        return json.loads((SCENARIOS_DIR / 'index.json').read_text(encoding='utf-8'))

    def scenario_package(self, ident):
        entry = next((s for s in self.scenarios() if s['id'] == ident), None)
        if entry is None:
            raise RequestError(404, '场景不存在')
        return entry, load_file(EXAMPLES_DIR / entry['file'], root_limit=EXAMPLES_DIR)

    # -- commands ----------------------------------------------------------------------------------
    def upload(self, raw):
        ident = uuid.uuid4().hex
        target = self.data_dir / 'packages' / ident
        try:
            package = load_zip(raw, target)
        except PackageError as exc:
            shutil.rmtree(target, ignore_errors=True)
            raise RequestError(400, str(exc)) from exc
        issues = validate(package.data, package.base_dir)
        return {'package_id': ident, 'summary': input_summary(package.data), 'issues': issues[:20], 'issues_count': len(issues),
                'assets': len(package.assets())}

    def submit(self, payload):
        if not isinstance(payload, dict):
            raise RequestError(400, '请求体必须是 JSON 对象')
        mode = payload.get('mode', 'offline')
        if mode not in ('offline', 'live'):
            raise RequestError(400, '运行模式无效')
        if mode == 'live' and not self.config()['live_available']:
            raise RequestError(400, '真实模型未配置，请使用离线模式')
        task = payload.get('task') or '检查交接资料，完成验算判定并生成工程报告。'
        if not isinstance(task, str) or len(task) > 2000:
            raise RequestError(400, '任务说明须为不超过 2000 字的文本')
        source, package = self.resolve_package(payload)
        intake_ids = payload.get('intake_ids') or []
        if not isinstance(intake_ids, list) or len(intake_ids) > 100:
            raise RequestError(400, '原始资料列表无效')
        source['attachments'] = []
        for ident in intake_ids:
            if not isinstance(ident, str):
                raise RequestError(400, '资料编号无效')
            path = self.assets.get(ident, 'record')
            if not path.is_file():
                raise RequestError(400, '原始资料不存在，请重新上传')
            record = json.loads(path.read_text(encoding='utf-8'))
            source['attachments'].append({k: record[k] for k in ('id', 'name', 'sha256', 'status')})
        template_id = payload.get('template_id')
        template_path = None
        if template_id:
            if not isinstance(template_id, str) or not re.fullmatch('[a-f0-9]{32}', template_id):
                raise RequestError(400, '模板编号无效')
            template_path = self.data_dir / 'templates' / (template_id + '.docx')
            if not template_path.is_file():
                raise RequestError(404, '模板不存在，请重新上传')
        with self.lock:
            active = sum(1 for r in self.store.list() if r['status'] in ('queued', 'running'))
            if active >= 6:
                raise RequestError(429, '排队任务较多，请等待当前任务完成')
            settings = dict(self.model_settings or environment_config()) if mode == 'live' else None
            run = self.runner.submit(package, source, task, mode, model_config=settings, template_path=template_path)
        return {'id': run['id'], 'status': run['status']}

    def resolve_package(self, payload):
        sources = [k for k in ('scenario_id', 'package', 'package_id') if payload.get(k) is not None]
        if len(sources) != 1:
            raise RequestError(400, '请在场景、上传 JSON、上传压缩包中选择一种输入')
        if 'scenario_id' in sources:
            entry, package = self.scenario_package(str(payload['scenario_id']))
            source = {'kind': 'scenario', 'id': entry['id'], 'name': entry['title']}
        elif 'package_id' in sources:
            ident = str(payload['package_id'])
            folder = self.data_dir / 'packages' / ident
            if not re.fullmatch(r'[a-f0-9]{32}', ident) or not (folder / 'handoff.json').is_file():
                raise RequestError(404, '上传的交接包不存在，请重新上传')
            package = load_file(folder / 'handoff.json', root_limit=folder)
            source = {'kind': 'upload-zip', 'id': ident, 'name': payload.get('name') or '上传压缩包'}
        else:
            if not isinstance(payload['package'], dict):
                raise RequestError(400, '交接包必须是 JSON 对象')
            package = Package(payload['package'])
            source = {'kind': 'upload-json', 'id': None, 'name': payload.get('name') or '上传 JSON'}
        return source, package

    def inspect(self, payload):
        if not isinstance(payload, dict):
            raise RequestError(400, '请求体必须是 JSON 对象')
        _, package = self.resolve_package(payload)
        issues = validate(package.data, package.base_dir)
        data = package.data
        return {'ready': not issues, 'issues': issues, 'notes': data.get('source_notes', []), 'summary': input_summary(data),
                'inventory': [
                    {'name': '桥梁信息与模型版本', 'count': 1 if data.get('model_revision') else 0},
                    {'name': '构件与典型截面', 'count': len(data.get('components') or [])},
                    {'name': '内力工况与组合', 'count': len(data.get('actions') or [])},
                    {'name': '需求与承载能力记录', 'count': len(data.get('checks') or [])},
                    {'name': '来源与证据定位', 'count': len(data.get('sources') or {})},
                    {'name': '报告图件', 'count': len(data.get('assets') or [])}],
                'message': '交接合同检查完成，可开展抗震验算。' if not issues else '资料存在缺项，仅可生成补正通知，不能开展后续验算。'}

    def model_command(self, payload, testing=False):
        if not isinstance(payload, dict):
            raise RequestError(400, '模型配置必须是 JSON 对象')
        if payload.get('clear') is True:
            self.model_settings = None
            return self.config()
        try:
            if payload.get('use_saved_key') is True and not payload.get('api_key'):
                saved = self.model_settings or environment_config()
                candidate = validate_config({**payload, 'api_key': saved.get('api_key', '')})
                current = validate_config(saved)
                if (candidate['protocol'], candidate['base_url']) != (current['protocol'], current['base_url']):
                    raise ValueError('接口地址或协议已改变，请重新填写该服务的 API Key。')
                payload = candidate
            cfg = validate_config(payload)
        except ValueError as exc:
            raise RequestError(400, str(exc)) from exc
        if testing:
            try:
                return test_connection(cfg)
            except Exception as exc:
                raise RequestError(400, safe_error(exc)) from exc
        with self.lock:
            self.model_settings = cfg
        return self.config()

    def template_upload(self, raw):
        try:
            template_validate(raw)
        except Exception as exc:
            raise RequestError(400, str(exc) if isinstance(exc, ValueError) else '模板文件无法读取') from exc
        ident = uuid.uuid4().hex
        folder = self.data_dir / 'templates'
        folder.mkdir(exist_ok=True)
        (folder / (ident + '.docx')).write_bytes(raw)
        return {'template_id': ident, 'message': '模板检查通过，将应用于下一次报告生成'}

    def run_file(self, ident, kind, name):
        if kind == 'files':
            if name not in FILE_TYPES:
                raise RequestError(404, '文件不存在')
            path = self.data_dir / 'runs' / ident / name
            return path, FILE_TYPES[name]
        if not name.isdigit():
            raise RequestError(404, '页面不存在')
        path = self.data_dir / 'runs' / ident / 'pages' / f'page-{int(name):03d}.jpg'
        return path, 'image/jpeg'


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'BridgeReportAgent/2.0'

        def log_message(self, fmt, *args):
            pass

        def send(self, status, body, ctype='application/json; charset=utf-8', download=None, cache=False):
            raw = body if isinstance(body, bytes) else dump(body).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'private, max-age=3600' if cache else 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            if download:
                self.send_header('Content-Disposition', f"attachment; filename*=UTF-8''{download}")
            self.end_headers()
            self.wfile.write(raw)

        def fail(self, status, message):
            self.send(status, {'error': message})

        def do_GET(self):
            try:
                self.route_get()
            except RequestError as exc:
                self.fail(exc.status, str(exc))
            except (PackageError, OSError, ValueError, KeyError):
                self.fail(500, '服务端读取数据失败')

        def route_get(self):
            url = urlparse(self.path)
            path = unquote(url.path)
            if path in ('/', '/index.html'):
                return self.send(200, (STATIC_DIR / 'index.html').read_bytes(), STATIC_TYPES['.html'])
            if path.startswith('/static/'):
                target = (STATIC_DIR / path[len('/static/'):]).resolve()
                if not inside(target, STATIC_DIR) or target.suffix not in STATIC_TYPES or not target.is_file():
                    raise RequestError(404, '资源不存在')
                return self.send(200, target.read_bytes(), STATIC_TYPES[target.suffix])
            if path == '/api/config':
                return self.send(200, app.config())
            if path == '/api/template':
                return self.send(200, TEMPLATE_DOCX.read_bytes(), FILE_TYPES['report.docx'], download='lab_template.docx')
            if path.startswith('/api/demo-packages/'):
                ident = path.rsplit('/', 1)[1]
                if ident not in ('golden-76K', 'golden-53K'):
                    raise RequestError(404, '案例不存在')
                _, package = app.scenario_package(ident)
                raw = io.BytesIO()
                with zipfile.ZipFile(raw, 'w', zipfile.ZIP_DEFLATED) as archive:
                    archive.write(package.base_dir / 'handoff.json', 'handoff.json')
                    for file in sorted((package.base_dir / 'assets').rglob('*')):
                        if file.is_file():
                            archive.write(file, file.relative_to(package.base_dir).as_posix())
                return self.send(200, raw.getvalue(), 'application/zip', download=ident + '-handoff.zip')
            if path.startswith('/api/intake/'):
                parts = path.split('/')
                if len(parts) != 5:
                    raise RequestError(404, '资料不存在')
                page_number = (parse_qs(url.query).get('page') or [None])[0]
                file = app.assets.pdf_page(parts[3], int(page_number)) if parts[4] == 'preview' and page_number else app.assets.get(parts[3], parts[4])
                if not file.is_file():
                    raise RequestError(404, '资料不存在')
                return self.send(200, file.read_bytes(), 'image/jpeg' if parts[4] == 'preview' else 'application/json')
            if path.startswith('/api/case-assets/'):
                ident = path.rsplit('/', 1)[1]
                if ident not in ('golden-76K', 'golden-53K'):
                    raise RequestError(404, '案例不存在')
                file = EXAMPLES_DIR / 'visuals' / (ident + '.json')
                return self.send(200, json.loads(file.read_text(encoding='utf-8')) if file.exists() else {})
            if path.startswith('/api/visuals/'):
                name = path.rsplit('/', 1)[1]
                if not re.fullmatch(r'(?:golden-76K|golden-53K)\.(?:jpg|json)', name):
                    raise RequestError(404, '资源不存在')
                file = EXAMPLES_DIR / 'visuals' / name
                return self.send(200, file.read_bytes(), 'image/jpeg' if name.endswith('.jpg') else 'application/json')
            if path == '/api/scenarios':
                return self.send(200, app.scenarios())
            if path.startswith('/api/scenarios/'):
                _, package = app.scenario_package(path.rsplit('/', 1)[1])
                return self.send(200, package.data)
            if path == '/api/contract':
                return self.send(200, json.loads((CONTRACTS_DIR / 'fields.json').read_text(encoding='utf-8')))
            if path.startswith('/api/contracts/'):
                name = path.rsplit('/', 1)[1]
                if name not in CONTRACT_FILES:
                    raise RequestError(404, '文件不存在')
                return self.send(200, (CONTRACTS_DIR / name).read_bytes(), 'application/json; charset=utf-8', download=name)
            if path == '/api/runs':
                return self.send(200, app.store.list())
            match = RUN_PATH.fullmatch(path)
            if match:
                ident, kind, name = match.groups()
                if not kind:
                    after = int((parse_qs(url.query).get('after') or ['0'])[0] or 0)
                    run = app.store.get(ident, after=after)
                    if run is None:
                        raise RequestError(404, '任务不存在')
                    return self.send(200, run)
                if app.store.get(ident) is None:
                    raise RequestError(404, '任务不存在')
                file, ctype = app.run_file(ident, kind, name)
                if not file.is_file():
                    raise RequestError(404, '文件尚未生成')
                download = name if kind == 'files' and name not in ('report.html', 'report.pdf') else None
                return self.send(200, file.read_bytes(), ctype, download=download, cache=kind == 'pages')
            raise RequestError(404, '地址不存在')

        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length') or 0)
                if not 0 <= length <= MAX_ZIP:
                    raise RequestError(413, '请求体超出允许范围')
                raw = self.rfile.read(length)
                self.check_origin()
                path = urlparse(self.path).path
                ctype = (self.headers.get('Content-Type') or '').split(';')[0].strip()
                if path in ('/api/intake', '/api/template'):
                    if not 0 < length <= MAX_ZIP:
                        raise RequestError(413, '文件不能为空且不超过 50 MB')
                    result = app.template_upload(raw) if path == '/api/template' else app.assets.upload(raw, unquote(self.headers.get('X-Filename', '')))
                    return self.send(201, result)
                if path == '/api/packages':
                    if ctype not in ('application/zip', 'application/x-zip-compressed', 'application/octet-stream'):
                        raise RequestError(415, '请上传 zip 格式的交接包')
                    if not 0 < length <= MAX_ZIP:
                        raise RequestError(413, '压缩包不能为空且不超过 50 MB')
                    return self.send(201, app.upload(raw))
                if path in ('/api/runs', '/api/inspect', '/api/model', '/api/model/test', '/api/intake/recognize'):
                    if ctype != 'application/json':
                        raise RequestError(415, '请使用 JSON 提交任务')
                    if not 0 < length <= MAX_JSON:
                        raise RequestError(413, '请求体不能为空且不超过 5 MB')
                    try:
                        payload = parse_json(raw.decode('utf-8'))
                    except (PackageError, UnicodeDecodeError) as exc:
                        raise RequestError(400, str(exc) or '请求体不是合法 JSON') from exc
                    if path == '/api/runs':
                        return self.send(202, app.submit(payload))
                    if path == '/api/inspect':
                        return self.send(200, app.inspect(payload))
                    if path == '/api/intake/recognize':
                        if not isinstance(payload, dict):
                            raise RequestError(400, '请求体须为 JSON 对象')
                        return self.send(200, app.assets.pdf_page(payload.get('id', ''), payload.get('page'), recognize=True))
                    return self.send(200, app.model_command(payload, testing=path.endswith('/test')))
                raise RequestError(404, '地址不存在')
            except RequestError as exc:
                self.fail(exc.status, str(exc))
            except ValueError:
                self.fail(400, '请求无效')
            except Exception:
                self.fail(500, '文件处理失败，请检查文件格式及本机识别组件后重试。')

        def check_origin(self):
            port = self.server.server_port
            allowed = {f'127.0.0.1:{port}', f'localhost:{port}'}
            origin = self.headers.get('Origin')
            if self.headers.get('Host', '') not in allowed or (origin and origin not in {f'http://{h}' for h in allowed}):
                raise RequestError(403, '仅允许本机页面提交任务')

    return Handler


def main():
    parser = argparse.ArgumentParser(description='桥梁抗震工程报告撰写 Agent 工作台服务')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--data-dir', default=str(BUILD_DIR / 'workbench'))
    args = parser.parse_args()
    app = App(args.data_dir)
    server = Server(('127.0.0.1', args.port), handler_for(app))
    print(f'Bridge report agent: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        app.pool.shutdown(wait=True)


if __name__ == '__main__':
    main()
