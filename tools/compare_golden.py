"""Compare a generated report DOCX with the 76K reference report: headings, table captions and table numbers.

Usage: python tools/compare_golden.py build/golden-check/report.docx [--out build/golden-check/compare.md]
Intentional differences are whitelisted in EXPECTED (see examples/golden/76K278+308/DIFF.md).
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge_report.paths import REFERENCE_76K  # noqa: E402

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NUMBER = re.compile(r'-?\d+(?:\.\d+)?')
# Original caption → generated caption (fixes of copy-paste captions in the reference report).
CAPTION_ALIASES = {
    ('混凝土力学指标表', 2): '抗震设防标准和性能目标',
    ('E1地震作用下支座抗震验算结果(横桥向)', 1): 'E1地震作用下支座位移抗震验算结果(横桥向)',
    ('E2地震作用下桩基抗剪验算结果(纵桥向)', 1): 'E2地震作用下桩基截面抗剪验算结果(纵桥向)',
    ('E2地震作用下桥墩塑性抗剪验算结果(纵桥向)', 1): 'E2地震作用下桥墩塑性铰区抗剪验算结果(纵桥向)',
    ('E2地震作用下桥墩塑性抗剪验算结果(纵桥向)', 2): 'E2地震作用下桥墩塑性铰区抗剪验算结果(纵桥向)',
}
# Numbers that legitimately differ: (generated caption, occurrence) → reason.
EXPECTED = {
    ('E2地震作用下桥墩塑性铰区抗剪验算结果(纵桥向)', 2): '原表8-2 加固后能需比 2.189 未计入 φ=0.9，统一按式(7-1)为 1.970',
}
HEADING_RENAMES = {'抗剪验算': '塑性铰区抗剪验算', '大桥概况': '桥梁概况'}


def q(tag):
    return '{%s}%s' % (W, tag)


def text(element):
    return ''.join(t.text or '' for t in element.iter(q('t'))).strip()


def norm_caption(caption):
    caption = re.sub(r'^表\s*[\d.]+-\d+\s*', '', caption)
    return caption.replace('（', '(').replace('）', ')').replace(' ', '')


def norm_heading(title):
    title = re.sub(r'^[\d.．\s]+', '', title).strip()
    return HEADING_RENAMES.get(title, title)


def read(path):
    body = etree.fromstring(zipfile.ZipFile(path).read('word/document.xml')).find(q('body'))
    headings, tables, last = [], [], ''
    styles = etree.fromstring(zipfile.ZipFile(path).read('word/styles.xml'))
    names = {s.get(q('styleId')): s.find(q('name')).get(q('val')) for s in styles.findall(q('style')) if s.find(q('name')) is not None}
    for element in body:
        tag = etree.QName(element).localname
        if tag == 'p':
            style = element.find(q('pPr') + '/' + q('pStyle'))
            name = names.get(style.get(q('val'))) if style is not None else ''
            value = text(element)
            if name in ('heading 1', 'heading 2', 'heading 3') and value:
                headings.append(norm_heading(value))
            if value:
                last = value
        elif tag == 'tbl':
            if last.startswith('表'):
                rows = [[text(tc) for tc in tr.findall(q('tc'))] for tr in element.findall(q('tr'))]
                tables.append((norm_caption(last), rows))
            last = ''
    return headings, tables


def numbers(row):
    return [float(n) for n in NUMBER.findall(' '.join(row))]


def close(a, b):
    return abs(a - b) <= max(abs(a) * 0.0005, 0.006)


def compare(generated):
    ref_headings, ref_tables = read(REFERENCE_76K)
    gen_headings, gen_tables = read(generated)
    report = {'matched': [], 'number_diffs': [], 'expected_diffs': [], 'unmatched': [], 'heading_diff': []}
    seen_ref, seen_gen, used = {}, {}, set()
    for caption, rows in ref_tables:
        seen_ref[caption] = seen_ref.get(caption, 0) + 1
        target = CAPTION_ALIASES.get((caption, seen_ref[caption]), caption)
        match = next((i for i, (c, _) in enumerate(gen_tables) if c == target and i not in used), None)
        if match is None:
            report['unmatched'].append(caption)
            continue
        used.add(match)
        seen_gen[target] = seen_gen.get(target, 0) + 1
        occurrence = (target, seen_gen[target])
        problems = []
        for ref_row, gen_row in zip(rows, gen_tables[match][1]):
            wanted, got = numbers(ref_row), numbers(gen_row)
            missing = [n for n in wanted if not any(close(n, g) for g in got)]
            if missing:
                problems.append(f"原行 {' | '.join(ref_row)} → 生成行 {' | '.join(gen_row)}（未对应：{missing}）")
        if not problems:
            report['matched'].append(target)
        elif occurrence in EXPECTED:
            report['expected_diffs'].append((target, EXPECTED[occurrence], problems))
        else:
            report['number_diffs'].append((target, problems))
    ref_seq = [h for h in ref_headings]
    if ref_seq != gen_headings:
        report['heading_diff'] = [f'原：{" / ".join(ref_seq)}', f'新：{" / ".join(gen_headings)}']
    return report


def markdown(report):
    lines = ['# 金标准对照结果', '', f"- 表格数值一致：{len(report['matched'])} 张",
             f"- 有意差异（白名单）：{len(report['expected_diffs'])} 张", f"- 未解释的数值差异：{len(report['number_diffs'])} 张",
             f"- 未匹配的原表：{len(report['unmatched'])} 张", f"- 标题序列：{'一致' if not report['heading_diff'] else '存在差异'}", '']
    for caption, reason, problems in report['expected_diffs']:
        lines += [f'## 有意差异：{caption}', f'原因：{reason}', ''] + [f'- {p}' for p in problems] + ['']
    for caption, problems in report['number_diffs']:
        lines += [f'## 数值差异：{caption}', ''] + [f'- {p}' for p in problems] + ['']
    if report['unmatched']:
        lines += ['## 未匹配的原表', ''] + [f'- {c}' for c in report['unmatched']] + ['']
    if report['heading_diff']:
        lines += ['## 标题序列差异', ''] + [f'- {h}' for h in report['heading_diff']]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('docx')
    parser.add_argument('--out')
    args = parser.parse_args()
    report = compare(args.docx)
    text_report = markdown(report)
    if args.out:
        Path(args.out).write_text(text_report, encoding='utf-8')
    print(text_report)
    return 1 if report['number_diffs'] or report['unmatched'] or report['heading_diff'] else 0


if __name__ == '__main__':
    sys.exit(main())
