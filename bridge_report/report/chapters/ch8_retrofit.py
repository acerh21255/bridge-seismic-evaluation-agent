"""Chapter 8: retrofit (resilience improvement) scheme and re-checks on the retrofitted model."""
from ...engine.terms import INPUT_LABELS, KIND_LABELS
from ..model import Para, Table
from .ch7_ductility import displacement_tables, phi_note, reinforcement_tables
from .common import cell, fmt, ratio_text, rich, verdict_cell

DIR_WORD = {'longitudinal': '纵桥向', 'transverse': '横桥向'}
DIR_SHORT = {'longitudinal': '纵向', 'transverse': '横向'}
COMPARE = {
    'e2_moment': ('桥墩各关键截面抗弯验算结果', '弯矩需求 (kN·m)', '等效屈服弯矩(kN·m)'),
    'hinge_shear': ('桥墩塑性铰区抗剪验算结果', '剪力需求 (kN)', '抗剪能力(kN)'),
    'shear': ('构件抗剪验算结果', '剪力需求 (kN)', '抗剪能力(kN)'),
    'e1_capacity': ('截面承载力验算结果', '轴力需求 (kN)', '截面承载力(kN)'),
    'bearing_displacement': ('支座位移验算结果', '位移需求 (m)', '规范限值(m)'),
    'bearing_sliding': ('支座抗滑移验算结果', '需求 (kN)', '抗力(kN)'),
}
DUCTILITY = ('hinge_shear', 'ductility_displacement', 'ductility_reinforcement')
HINGE_TEXT = ('加固后桥墩进入塑性，桥墩塑性铰区抗剪承载力按照《公路桥梁抗震性能评价细则》（JTG/T 2231-02—2021）中塑性铰区域内斜截面抗剪强度'
              '进行计算，计算结果如下所示：')


def compare_table(b, kind, level, direction, items):
    title, demand_label, capacity_label = COMPARE.get(kind, (KIND_LABELS[kind] + '验算结果', '需求', '能力'))
    header = [
        [cell('地震作用', bold=True, vmerge='restart'), cell('关键截面', bold=True, vmerge='restart'),
         cell(demand_label, bold=True, span=2), cell(capacity_label, bold=True, span=2),
         cell('加固后能力/需求', bold=True, vmerge='restart'), cell('验算结果', bold=True, vmerge='restart')],
        [cell('', vmerge='continue'), cell('', vmerge='continue')] + [cell(t, bold=True) for t in ('加固前', '加固后', '加固前', '加固后')]
        + [cell('', vmerge='continue'), cell('', vmerge='continue')],
    ]
    rows = []
    for item in items:
        before = item.get('before') or {}
        rows.append([cell(INPUT_LABELS[direction]), cell(item['section_label']), cell(fmt(before.get('demand'))), cell(fmt(item['demand'])),
                     cell(fmt(before.get('capacity'))), cell(fmt(item['capacity'])), cell(ratio_text(item['ratio'])),
                     verdict_cell(item['verdict'])])
    notes = phi_note(items) if kind == 'hinge_shear' else []
    b.add(Table(f'tab-retrofit-{kind}-{level}-{direction}', f'{level}地震作用下{title}({DIR_WORD[direction]})', header, rows,
                notes=[Para(rich(n), style='note') for n in notes], widths=[1111, 1134, 1105, 1105, 1105, 1105, 1179, 1206]))


def reason_text(items):
    reasons = []
    for item in items:
        before = item.get('before') or {}
        status = before.get('status')
        if status == 'PLASTIC':
            reasons.append(f"E2{DIR_SHORT[item['direction']]}地震下{item['section_label']}进入塑性")
        elif status == 'FAIL':
            reasons.append(f"{item['section_label']}{KIND_LABELS[item['kind']]}{before.get('verdict')}")
    return '，'.join(dict.fromkeys(reasons))


def build(b):
    retrofit = b.get('retrofit')
    if not retrofit:
        return
    b.h(1, '韧性提升方案', key='ch-retrofit')
    b.p(retrofit.get('description', ''))
    figure = retrofit.get('figure') or {}
    images, widths = [], []
    for asset_id in figure.get('assets', []):
        path, width, _ = b.asset(asset_id, '加固设计图')
        images.append(path)
        widths.append(width)
    b.figure('fig-retrofit', figure.get('caption') or '加固设计图', image=images or None, width_cm=widths or None)

    items = [i for i in b.items('retrofit') if i['status'] != 'NA']
    checks = [i for i in items if i['kind'] not in DUCTILITY]
    ductility = [i for i in items if i['kind'] in DUCTILITY]
    b.h(2, '韧性提升后抗震验算')
    reasons = reason_text(items)
    scope = retrofit.get('scope_note')
    b.p((f'由于本桥{reasons}，故进行韧性提升，' if reasons else '') + (f'{scope}，' if scope else '') + '加固后计算结果如下所示：')
    for kind in dict.fromkeys(i['kind'] for i in checks):
        for level in ('E1', 'E2'):
            for direction in DIR_WORD:
                rows = [i for i in checks if (i['kind'], i['level'], i['direction']) == (kind, level, direction)]
                if rows:
                    compare_table(b, kind, level, direction, rows)
    if not ductility:
        return
    b.h(2, '延性验算')
    hinge = [i for i in ductility if i['kind'] == 'hinge_shear']
    if hinge:
        b.h(3, '塑性铰区抗剪验算')
        b.p(HINGE_TEXT)
        for direction in DIR_WORD:
            rows = [i for i in hinge if i['direction'] == direction]
            if rows:
                compare_table(b, 'hinge_shear', 'E2', direction, rows)
    displacement = [i for i in ductility if i['kind'] == 'ductility_displacement']
    if displacement:
        b.h(3, '位移延性验算')
        b.fragment('displacement_ductility')
        displacement_tables(b, displacement, 'retrofit')
    reinforcement = [i for i in ductility if i['kind'] == 'ductility_reinforcement']
    if reinforcement:
        b.h(3, '延性构造配箍率验算')
        b.fragment('stirrup_ratio')
        reinforcement_tables(b, reinforcement, 'retrofit')
