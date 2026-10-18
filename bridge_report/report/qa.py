"""Report self-check: numbering, captions, references, table completeness, wording rules and data gaps."""
import os
from pathlib import Path

from .model import Equation, Figure, FigureRow, Heading, Para, Table, iter_runs

FONTS = {'宋体': 'simsun.ttc', '黑体': 'simhei.ttf', 'Times New Roman': 'times.ttf', 'Cambria Math': 'cambria.ttc'}
FORBIDDEN = {'抗弯不通过': 'E2 桥墩抗弯超限应表述为“进入塑性”，不得写“不通过”', '不通过': '验算结论措辞统一使用“不满足”'}


def _label_sequence_errors(labels, what):
    errors = []
    groups = {}
    for label in labels:
        scope, _, number = label.rpartition('-')
        groups.setdefault(scope, []).append(int(number))
    for scope, numbers in groups.items():
        if numbers != list(range(1, len(numbers) + 1)):
            errors.append(f'{what}编号不连续：{scope}-{numbers}')
    return errors


def _heading_errors(headings):
    errors = []
    expected = [0, 0, 0]
    for h in headings:
        parts = [int(x) for x in h.label.rstrip('.').split('.')]
        level = len(parts)
        expected[level - 1] += 1
        for i in range(level, 3):
            expected[i] = 0
        if parts != expected[:level]:
            errors.append(f'标题编号不连续：{h.label} {h.title}')
            expected[:level] = parts
    return errors


def check(doc, result):
    errors, warnings, hints = [], [], []
    headings = [b for b in doc.blocks if isinstance(b, Heading) and b.label]
    figures = [b for b in doc.blocks if isinstance(b, Figure)] + [f for b in doc.blocks if isinstance(b, FigureRow) for f in b.figures]
    tables = [b for b in doc.blocks if isinstance(b, Table) and b.caption]
    equations = [b for b in doc.blocks if isinstance(b, Equation) and b.numbered]

    errors += _heading_errors(headings)
    errors += _label_sequence_errors([f.label for f in figures], '图')
    errors += _label_sequence_errors([t.label for t in tables], '表')
    for item in figures + tables:
        if not (item.caption or '').strip():
            errors.append(f'{"图" if isinstance(item, Figure) else "表"}{item.label} 缺少题注')
    for run in iter_runs(doc):
        if run.ref is not None and not run.text:
            errors.append(f'交叉引用 {run.ref} 未解析')

    missing_images = sum(1 for f in figures for image, _ in f.images() if not image or not Path(image).is_file())
    if missing_images:
        warnings.append(f'{missing_images} 处图件缺失，已以“图件待补充”占位')

    for table in tables:
        if table.kind != 'check':
            continue
        for row in table.rows:
            for cell in row:
                text = ''.join(r.text for r in cell.runs)
                if not text and cell.vmerge != 'continue':
                    errors.append(f'表{table.label} 存在空单元格')
                    break
        dash = any(''.join(r.text for r in c.runs) == '—' for row in table.rows for c in row)
        if dash and not table.notes:
            warnings.append(f'表{table.label} 含“—”但无表注说明')

    text = '\n'.join(''.join(r.text for r in b.runs) for b in doc.blocks if isinstance(b, Para))
    text += '\n'.join(r.text for r in iter_runs(doc))
    for phrase, why in FORBIDDEN.items():
        if phrase in text:
            (errors if phrase == '抗弯不通过' else warnings).append(f'出现“{phrase}”：{why}')

    for item in result.get('items', []):
        if item['kind'] == 'e2_moment' and item['component_kind'] == 'pier' and item['verdict'] not in ('通过', '进入塑性', '待补正', '未开展', '不适用'):
            errors.append(f"{item['section_label']} E2 桥墩抗弯结论措辞错误：{item['verdict']}")

    for note in doc.meta.get('missing', []):
        (hints if note.startswith('承台') else warnings).append(f'资料缺项：{note}')
    if result.get('provisional'):
        warnings.append(f"{len(result['provisional'])} 项支座位移采用暂定限值，待补充规范依据")
    hints += retrofit_hints(result)
    if doc.meta.get('data_kind') != 'engineering_input':
        hints.append('交接数据为复现或演示数据，报告仅用于格式与流程验证')
    hints.append('engineering_release=false：工程签发前须由专业人员复核计算与报告')
    fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    if fonts.is_dir():
        for name, file in FONTS.items():
            if not (fonts / file).is_file():
                warnings.append(f'系统缺少字体 {name}，Word 渲染可能替换字体')

    return {
        'errors': errors, 'warnings': warnings, 'hints': hints,
        'counts': {'headings': len(headings), 'figures': len(figures), 'tables': len(tables), 'equations': len(equations),
                   'missing_images': missing_images},
        'status': 'error' if errors else 'warning' if warnings else 'ok',
    }


def retrofit_hints(result):
    hints = []
    retrofit = [i for i in result.get('items', []) if i['stage'] == 'retrofit']
    stronger = [i for i in retrofit if i['kind'] == 'e2_moment' and i['component_kind'] == 'pier' and i.get('before')
                and i['capacity'] is not None and i['before'].get('capacity') is not None and i['capacity'] > i['before']['capacity']]
    rechecked_piles = any(i['component_kind'] == 'pile' for i in retrofit)
    if stronger and not rechecked_piles:
        sections = '、'.join(i['section_label'] for i in stronger)
        hints.append(f'{sections}加固后等效屈服弯矩提高，超强弯矩随之增大；加固复核未包含桩基，建议按加固后能力保护要求复核桩基')
    return hints


def summary_line(qa):
    counts = qa['counts']
    return (f"错误 {len(qa['errors'])}，警告 {len(qa['warnings'])}，提示 {len(qa['hints'])}；"
            f"图 {counts['figures']}，表 {counts['tables']}，编号公式 {counts['equations']}")
