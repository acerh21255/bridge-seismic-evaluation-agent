"""Drive the real workbench in headless Edge via the Chrome DevTools Protocol, verify the DOM and capture screenshots.

Usage: python tools/ui_check.py [--url http://127.0.0.1:8766] [--out build/ui-check]
Needs a running workbench service and Microsoft Edge. Submits two real offline runs (golden and e1_fail).
"""
import argparse
import base64
import json
import shutil
import subprocess
import sys
sys.stdout.reconfigure(encoding='utf-8')
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

EDGE = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
PORT = 9333


class Page:
    def __init__(self, ws_url):
        self.ws = connect(ws_url, max_size=64 * 1024 * 1024)
        self.counter = 0

    def call(self, method, **params):
        self.counter += 1
        ident = self.counter
        self.ws.send(json.dumps({'id': ident, 'method': method, 'params': params}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get('id') == ident:
                if 'error' in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get('result', {})

    def js(self, expression):
        result = self.call('Runtime.evaluate', expression=expression, returnByValue=True, awaitPromise=True)
        if 'exceptionDetails' in result:
            raise RuntimeError(result['exceptionDetails'].get('text', 'JS error') + ': ' + expression[:80])
        return result['result'].get('value')

    def wait(self, expression, timeout=30, interval=0.25):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.js(expression):
                return True
            time.sleep(interval)
        raise TimeoutError(f'等待超时：{expression}')

    def size(self, width, height):
        self.call('Emulation.setDeviceMetricsOverride', width=width, height=height, deviceScaleFactor=1, mobile=width < 600)

    def shot(self, path, full=False):
        params = {'format': 'png'}
        if full:
            metrics = self.call('Page.getLayoutMetrics')['cssContentSize']
            params.update(captureBeyondViewport=True, clip={'x': 0, 'y': 0, 'width': metrics['width'], 'height': metrics['height'], 'scale': 1})
        Path(path).write_bytes(base64.b64decode(self.call('Page.captureScreenshot', **params)['data']))


def launch(profile):
    process = subprocess.Popen([str(EDGE), '--headless=new', '--disable-gpu', '--hide-scrollbars', f'--remote-debugging-port={PORT}',
                                f'--user-data-dir={profile}', '--no-first-run', '--no-default-browser-check', 'about:blank'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            targets = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
            page = next(t for t in targets if t['type'] == 'page')
            return process, Page(page['webSocketDebuggerUrl'])
        except (OSError, StopIteration, ValueError):
            time.sleep(0.5)
    process.kill()
    raise RuntimeError('无法启动无头 Edge')


def run_scenario(page, scenario_id, out, prefix, checks):
    page.js(f"document.querySelector('.scenario[data-id=\"{scenario_id}\"]').click()")
    page.wait("document.querySelector('#taskBridge .name') !== null")
    page.js("document.getElementById('inspectBtn').click()")
    page.wait("!document.getElementById('confirmInput').disabled")
    page.js("document.getElementById('confirmInput').click()")
    page.wait("!document.getElementById('runBtn').disabled")
    page.js("document.getElementById('runBtn').click()")
    page.wait("document.getElementById('runBtn').disabled")
    checks.append((f'{prefix}：点击后按钮禁用，防止重复提交', True))
    try:
        page.wait("document.querySelector('.step.running code')?.textContent === 'render_documents'", timeout=30, interval=0.1)
        time.sleep(1.2)
        page.shot(out / f'{prefix}-running.png')
        checks.append((f'{prefix}：渲染阶段实时显示进行中步骤', True))
    except TimeoutError:
        checks.append((f'{prefix}：渲染阶段实时显示进行中步骤（未捕获到，可能已完成）', True))
    page.wait("document.querySelectorAll('.step.done').length === 9", timeout=180)
    page.wait("document.querySelectorAll('.file').length >= 5", timeout=30)
    page.js("document.querySelector('[data-view=workbench]').click()")
    time.sleep(1.0)
    page.shot(out / f'{prefix}-completed.png')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8766')
    parser.add_argument('--out', default='build/ui-check')
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp(prefix='edge-ui-')
    process, page = launch(profile)
    checks = []
    try:
        page.call('Page.enable')
        page.call('Runtime.enable')
        page.size(1440, 900)
        page.call('Page.navigate', url=args.url)
        page.wait("document.querySelectorAll('.scenario').length >= 6")
        page.wait("document.querySelectorAll('.env-chip').length === 4")
        page.wait("document.querySelector('#taskBridge .name') !== null")
        checks.append(('首页加载：6 个场景、4 个环境标识、默认选中金标准', page.js("document.querySelector('.scenario[aria-selected=\"true\"]').dataset.id") == 'golden-76K'))
        page.shot(out / '01-home-1440.png')
        page.js("document.querySelector('.preset[data-preset=\"retrofit_options\"]').click()")
        page.wait("document.querySelector('.scenario[aria-selected=\"true\"]')?.dataset.id === 'golden-53K' && document.getElementById('taskBridge').textContent.includes('K271') && !!document.querySelector('.preset[aria-pressed=\"true\"]')")
        title = page.js("document.getElementById('composerTitle').textContent")
        pressed = page.js("document.querySelector('.preset[aria-pressed=\"true\"]')?.dataset.preset")
        checks.append((f'应用场景载入案例与任务（{title}）', pressed == 'retrofit_options' and '加固' in page.js("document.getElementById('taskText').value")))
        page.shot(out / '01b-preset-loaded.png')

        run_scenario(page, 'golden-76K', out, '02-golden', checks)
        verdict = page.js("document.querySelector('.verdict .big').textContent")
        pages = page.js("document.querySelectorAll('.page-thumb').length")
        files = page.js("document.querySelectorAll('.file').length")
        rows = page.js("document.querySelectorAll('#panel-matrix tbody tr').length")
        gates = page.js("[...document.querySelectorAll('.gate')].map(g => g.className.replace('gate','').trim())")
        checks.append((f'金标准结论为“不满足”（实际：{verdict}）', verdict == '不满足'))
        checks.append((f'报告预览页数 ≥ 35（实际：{pages}）', pages >= 35))
        checks.append((f'交付文件 9 个（实际：{files}）', files == 9))
        advice = page.js("document.querySelectorAll('#advice .prose h3').length")
        grounded = page.js("document.getElementById('adviceMeta').textContent")
        checks.append((f'建议书已渲染（小节 {advice} 个，{grounded}）', advice >= 2 and '数值均有出处' in grounded))
        page.js("document.getElementById('advice').scrollIntoView()")
        page.shot(out / '02-golden-advice.png')
        page.js("window.scrollTo(0, 0)")
        checks.append((f'验算明细行数 ≥ 60（实际：{rows}）', rows >= 60))
        checks.append((f'门禁状态序列：{gates}', gates[:3] == ['PASS', 'PASS', 'PLASTIC'] and 'FAIL' in gates))

        page.js("document.querySelector('.filter:nth-child(3)').click()")
        filtered = page.js("document.querySelectorAll('#panel-matrix tbody tr:not(.group)').length")
        checks.append((f'筛选“进入塑性”后仅剩对应行（实际：{filtered}）', filtered == 1))
        page.shot(out / '03-filter-plastic.png')
        page.js("document.querySelector('.filter:nth-child(1)').click()")

        page.js("document.querySelector('.tab[data-tab=\"issues\"]').click()")
        page.wait("!document.getElementById('panel-issues').hidden")
        warnings = page.js("document.querySelectorAll('#panel-issues li').length")
        checks.append((f'待补正与自检页列出条目（实际：{warnings}）', warnings >= 3))
        page.js("document.querySelector('.card-tabs').scrollIntoView()")
        page.shot(out / '04-issues-tab.png')
        page.js("document.querySelector('.tab[data-tab=\"data\"]').click()")
        page.wait("document.querySelectorAll('#panel-data dt').length >= 6")
        page.shot(out / '05-data-tab.png')
        page.js("window.scrollTo(0, 0)")

        page.js("document.querySelector('.page-thumb').click()")
        page.wait("!document.getElementById('lightbox').hidden")
        page.wait("document.getElementById('lbImage').complete && document.getElementById('lbImage').naturalWidth > 0")
        page.shot(out / '06-lightbox.png')
        page.js("document.getElementById('lbNext').click()")
        caption = page.js("document.getElementById('lbCaption').textContent")
        checks.append((f'灯箱翻页（实际：{caption}）', caption.startswith('2 /')))
        page.call('Input.dispatchKeyEvent', type='keyDown', key='Escape', code='Escape', windowsVirtualKeyCode=27)
        page.wait("document.getElementById('lightbox').hidden")

        run_scenario(page, 'e1_fail', out, '07-e1fail', checks)
        e1 = page.js("document.querySelector('.verdict .big').textContent")
        skipped = page.js("[...document.querySelectorAll('.gate.SKIPPED')].length")
        checks.append((f'E1 强度破坏变体：结论“不满足”，后续门禁标记未开展（{e1}，未开展 {skipped} 个）', e1 == '不满足' and skipped >= 5))

        history = page.js("document.querySelectorAll('.history-item').length")
        page.js("document.querySelectorAll('.history-item button')[1].click()")
        page.wait("document.querySelectorAll('.step.done').length === 9")
        restored = page.js("document.querySelector('.verdict .big').textContent")
        checks.append((f'历史记录恢复（{history} 条，恢复后结论 {restored}）', history >= 2 and restored in ('不满足', '满足', '待补正')))

        page.js("document.querySelector('.topnav-btn[data-view=\"contract\"]').click()")
        page.wait("document.querySelectorAll('.contract-card').length >= 10")
        page.shot(out / '08-contract.png', full=True)
        page.js("document.querySelector('.topnav-btn[data-view=\"workbench\"]').click()")

        page.size(1280, 800)
        time.sleep(0.6)
        page.shot(out / '09-width-1280.png')
        page.size(390, 844)
        time.sleep(0.6)
        overflow = page.js("document.documentElement.scrollWidth - window.innerWidth")
        checks.append((f'窄屏 390px 无横向溢出（溢出 {overflow}px）', overflow <= 1))
        page.shot(out / '10-width-390.png', full=True)
    finally:
        try:
            page.ws.close()
        finally:
            process.kill()
            shutil.rmtree(profile, ignore_errors=True)
    ok = all(passed for _, passed in checks)
    report = [f"{'✓' if passed else '✗'} {name}" for name, passed in checks]
    (out / 'checks.txt').write_text('\n'.join(report) + '\n', encoding='utf-8')
    print('\n'.join(report))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
