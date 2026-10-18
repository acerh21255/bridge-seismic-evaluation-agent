"""Report pipeline shared by the Agent tools, CLI and tests: judge → compose → render → check → deliver."""
import hashlib
import json
from pathlib import Path

from .engine.gates import evaluate
from .report import qa
from .report.chapters import build_report
from .report.docx_writer import set_update_fields, write_docx
from .report.html_writer import write_html
from .report.office import render_pages, update_and_export

DELIVERABLES = ('report.docx', 'report.pdf', 'report.html', 'advice.md', 'diagnosis.json', 'result.json', 'qa.json', 'input.json', 'receipt.json')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(value, path):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def judge(package):
    return evaluate(package.data, package.base_dir)


def compose(package, result, out_dir):
    return build_report(package, result, Path(out_dir) / 'work')


def render(doc, out_dir, word=True, template_path=None):
    """Write DOCX and HTML; with Word refresh the TOC, export PDF and page previews."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    docx = write_docx(doc, out / 'report.docx', template_path=template_path)
    write_html(doc, out / 'report.html')
    if word:
        office = update_and_export(docx, out / 'report.pdf')
    else:
        office = {'ok': False, 'pages': None, 'pdf': None, 'message': '已按要求跳过 Word 处理：目录将在打开文档时提示更新'}
    pages = render_pages(office['pdf'], out / 'pages') if office.get('pdf') else []
    if not office.get('ok'):
        set_update_fields(docx)
    return {'word_ok': bool(office.get('ok')), 'message': office['message'], 'page_count': office.get('pages') or len(pages) or None,
            'pages': [p.name for p in pages], 'pdf': bool(office.get('pdf'))}


def check(doc, result):
    return qa.check(doc, result)


def deliver(out_dir, input_sha256, result, qa_report, rendering):
    out = Path(out_dir)
    files = [{'name': name, 'sha256': sha256(out / name), 'bytes': (out / name).stat().st_size}
             for name in DELIVERABLES if name != 'receipt.json' and (out / name).is_file()]
    receipt = {'status': result['status'], 'reason': result.get('reason'), 'engineering_release': False, 'input_sha256': input_sha256,
               'qa_status': qa_report['status'], 'page_count': rendering.get('page_count'), 'word_ok': rendering.get('word_ok'),
               'files': files}
    dump(receipt, out / 'receipt.json')
    return receipt


def run_all(package, out_dir, word=True):
    """Non-agent convenience runner (CLI, tests, tools)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dump(package.data, out / 'input.json')
    result = judge(package)
    dump(result, out / 'result.json')
    doc = compose(package, result, out)
    rendering = render(doc, out, word=word)
    qa_report = check(doc, result)
    dump(qa_report, out / 'qa.json')
    return {'result': result, 'doc': doc, 'rendering': rendering, 'qa': qa_report,
            'receipt': deliver(out, sha256(out / 'input.json'), result, qa_report, rendering)}
