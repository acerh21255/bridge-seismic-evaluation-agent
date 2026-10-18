"""Microsoft Word automation (Windows) for TOC/field refresh and PDF export; page previews via pypdfium2."""
import json
import os
import subprocess
import threading
from pathlib import Path

SCRIPT = Path(__file__).with_name('word_update.ps1')
TIMEOUT_S = 240
PREVIEW_WIDTH = 1000
_LOCK = threading.Lock()
_AVAILABLE = None


def word_available():
    """True when Word can be automated. Set BRIDGE_DISABLE_WORD=1 to force the fallback path."""
    global _AVAILABLE
    if os.environ.get('BRIDGE_DISABLE_WORD') == '1' or os.name != 'nt':
        return False
    if _AVAILABLE is None:
        try:
            probe = subprocess.run(['reg', 'query', r'HKEY_CLASSES_ROOT\Word.Application\CurVer'], capture_output=True, timeout=15)
            _AVAILABLE = probe.returncode == 0
        except (OSError, subprocess.SubprocessError):
            _AVAILABLE = False
    return _AVAILABLE


def update_and_export(docx, pdf=None):
    """Refresh fields/TOC in place and export PDF. Returns {'ok', 'pages', 'pdf', 'message'}; never raises."""
    if not word_available():
        return {'ok': False, 'pages': None, 'pdf': None,
                'message': '未检测到可自动化的 Microsoft Word：目录将在打开文档时提示更新，未生成 PDF 预览'}
    command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(SCRIPT),
               '-Docx', str(Path(docx).resolve()), '-Pdf', str(Path(pdf).resolve()) if pdf else '']
    with _LOCK:
        try:
            run = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return {'ok': False, 'pages': None, 'pdf': None, 'message': f'Word 处理超时（{TIMEOUT_S} s），已保留未刷新目录的 DOCX'}
        except OSError as exc:
            return {'ok': False, 'pages': None, 'pdf': None, 'message': f'无法启动 PowerShell：{type(exc).__name__}'}
    payload = next((line for line in reversed(run.stdout.strip().splitlines()) if line.startswith('{')), '')
    try:
        info = json.loads(payload)
    except json.JSONDecodeError:
        info = {'ok': False, 'message': 'Word 自动化未返回结果'}
    if not info.get('ok'):
        return {'ok': False, 'pages': None, 'pdf': None, 'message': 'Word 处理失败：' + str(info.get('message', ''))[:200]}
    pdf_path = Path(pdf) if pdf and Path(pdf).is_file() else None
    return {'ok': True, 'pages': info.get('pages'), 'pdf': pdf_path, 'message': '已刷新目录与页码' + ('并导出 PDF' if pdf_path else '')}


def render_pages(pdf, out_dir, width=PREVIEW_WIDTH):
    """Render every PDF page to JPEG (page-001.jpg …); returns the list of written paths."""
    import pypdfium2 as pdfium
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    document = pdfium.PdfDocument(str(pdf))
    written = []
    try:
        for index in range(len(document)):
            page = document[index]
            scale = width / page.get_width()
            image = page.render(scale=scale).to_pil().convert('RGB')
            target = out_dir / f'page-{index + 1:03d}.jpg'
            image.save(target, quality=82, optimize=True)
            written.append(target)
            page.close()
    finally:
        document.close()
    return written
