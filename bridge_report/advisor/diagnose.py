"""Deterministic diagnosis on top of the engine result: weak links, smallest margins, retrofit effect and next steps.
It only re-reads engine outcomes; it never changes a status or a number."""
import json
import re

from ..report.qa import retrofit_hints
from .measures import CODES, MEASURES, MODES, SEVERITY_LABEL, SEVERITY_ORDER

KIND_MODES = {
    'e1_capacity': 'e1_strength', 'shear': 'member_shear', 'hinge_shear': 'hinge_shear', 'ductility_displacement': 'ductility_disp',
    'ductility_reinforcement': 'confinement', 'bearing_displacement': 'bearing', 'bearing_sliding': 'bearing',
    'edge_distance': 'seat_length', 'pilecap': 'pilecap',
}
RESTRAINT_WORDS = ('限位', '挡块', '防落梁')


def mode_of(item):
    status, kind = item['status'], item['kind']
    if status == 'PLASTIC':
        return 'pier_plastic'
    if status == 'BLOCKED':
        return 'data_overstrength' if '超强' in (item.get('reason') or '') else 'data_missing'
    if status != 'FAIL':
        return None
    if kind == 'e2_moment':
        return 'pile_yield' if item.get('component_kind') == 'pile' else 'e1_strength'
    if kind == 'detailing':
        return 'restrainer' if any(w in (item.get('section_label') or '') for w in RESTRAINT_WORDS) else 'detailing'
    return KIND_MODES.get(kind, 'detailing')


def label(item):
    return ' '.join(x for x in (item.get('section_label'), item.get('direction_label'), item.get('kind_label')) if x)


def exceed_pct(ratio):
    """Demand above capacity in percent, from ratio = capacity / demand."""
    return round((1 / ratio - 1) * 100, 1) if ratio and ratio < 1 else None


def brief(item):
    return {'id': item['id'], 'label': label(item), 'demand': item.get('demand'), 'capacity': item.get('capacity'),
            'unit': item.get('unit'), 'ratio': item.get('ratio'), 'exceed_pct': exceed_pct(item.get('ratio')),
            'verdict': item.get('verdict'), 'reason': item.get('reason'), 'stage': item.get('stage')}


def retrofit_effect(items):
    rows = []
    for item in items:
        before = item.get('before')
        if item.get('stage') != 'retrofit' or not before:
            continue
        change = None
        if item.get('demand') and before.get('demand'):
            change = round((item['demand'] / before['demand'] - 1) * 100, 1)
        rows.append({'label': label(item), 'before': before.get('verdict'), 'after': item.get('verdict'),
                     'ratio_before': before.get('ratio'), 'ratio_after': item.get('ratio'), 'demand_change_pct': change,
                     'improved': before.get('status') != item['status'] and item['status'] == 'PASS'})
    return rows


def next_steps(result, modes, skipped, effect):
    steps = []

    def add(owner, action, why):
        steps.append({'order': len(steps) + 1, 'owner': owner, 'action': action, 'why': why.rstrip('。')})

    if not result.get('evaluated'):
        add('第三步', '按交接合同补正交接包后重新提交', '交接包未通过合同检查，本次未开展任何验算判定')
    for mode in modes:
        where = '、'.join(dict.fromkeys(i['label'] for i in mode['items']))
        if mode['severity'] == 'data':
            action = '提交超强弯矩体系传力复算结果' if mode['key'] == 'data_overstrength' else '补交缺失数值并说明来源'
            add('第三步', f'{action}：{where}', mode['meaning'])
        elif mode['severity'] in ('critical', 'major'):
            options = '、'.join(MEASURES[m]['title'] for m in mode['measures'][:2])
            add('设计', f'针对{where}比选加固方案（{options}），形成加固后模型交第三步复算', mode['meaning'])
    for hint in retrofit_hints(result):
        add('第三步', '复核加固后桩基能力保护', hint)
    rising = [r for r in effect if (r['demand_change_pct'] or 0) > 0]
    if rising and not retrofit_hints(result):
        worst = max(rising, key=lambda r: r['demand_change_pct'])
        add('复核', f"确认加固后地震需求变化：{worst['label']}需求增加 {worst['demand_change_pct']}%", '加固改变刚度后需求随之变化，需确认复算模型已更新')
    if skipped:
        add('第三步', f'解除流程停止条件后，补做 {skipped} 项未开展的验算', '停止点之后的验算未开展，不能视为通过')
    if result.get('provisional'):
        add('复核', '补充支座位移限值的规范依据', '当前暂按 0.0375 m 评定')
    add('复核', '由专业人员复核计算与报告后签发', 'engineering_release=false，报告与建议均不能直接用于施工')
    return steps


def diagnose(result):
    items = [i for i in result.get('items', []) if i.get('final')]
    grouped = {}
    for item in items:
        key = mode_of(item)
        if key:
            grouped.setdefault(key, []).append(item)
    modes = []
    for key, members in grouped.items():
        spec = MODES[key]
        members.sort(key=lambda i: (i.get('ratio') is None, i.get('ratio') or 0))
        modes.append({'key': key, 'title': spec['title'], 'severity': spec['severity'], 'severity_label': SEVERITY_LABEL[spec['severity']],
                      'meaning': spec['meaning'], 'note': spec.get('note'), 'measures': spec['measures'],
                      'items': [brief(i) for i in members]})
    modes.sort(key=lambda m: (SEVERITY_ORDER[m['severity']], min((i['ratio'] or 9) for i in m['items'])))
    margins = sorted((i for i in items if i['status'] == 'PASS' and i.get('ratio')), key=lambda i: i['ratio'])[:5]
    skipped = sum(1 for i in items if i['status'] == 'SKIPPED')
    effect = retrofit_effect(result.get('items', []))
    used = list(dict.fromkeys(m for mode in modes for m in mode['measures']))
    counts = {s: sum(1 for m in modes if m['severity'] == s) for s in SEVERITY_ORDER}
    return {
        'status': result.get('status'), 'status_label': result.get('status_label'), 'reason': result.get('reason'),
        'evaluated': result.get('evaluated'), 'issues': result.get('issues', [])[:20], 'modes': modes, 'counts': counts,
        'margins': [dict(brief(i), margin_pct=round((i['ratio'] - 1) * 100, 1)) for i in margins],
        'skipped': skipped, 'stops': [s['reason'] for s in result.get('stops', [])], 'retrofit_effect': effect,
        'measures': {k: dict(MEASURES[k], code=CODES[MEASURES[k]['code']]) for k in used},
        'next_steps': next_steps(result, modes, skipped, effect), 'engineering_release': False,
    }


def summary(diag):
    c = diag['counts']
    return (f"控制性问题 {c['critical']} 类，需处理 {c['major']} 类，需关注 {c['watch']} 类，待补资料 {c['data']} 类；"
            f"候选措施 {len(diag['measures'])} 项，下一步工作 {len(diag['next_steps'])} 条")


def fmt(value):
    if value is None:
        return '—'
    return f'{value:g}' if isinstance(value, float) else str(value)


def draft_memo(diag, bridge=''):
    """Engine-drafted advisory memo (Markdown); used offline and whenever the model supplies no text of its own."""
    numerals = iter('一二三四五六')
    lines = [f'# {bridge}抗震加固与后续工作建议'.strip(), '',
             f"> 报告结论：**{diag['status_label']}**　{diag['reason']}", '']

    def section(title):
        lines.extend([f'## {next(numerals)}、{title}', ''])

    section('薄弱环节')
    if not diag['modes']:
        lines += ['各项验算均满足，未识别到需要加固的薄弱环节。', '']
    for mode in diag['modes']:
        lines.append(f"### {mode['title']}（{mode['severity_label']}）")
        lines.append(mode['meaning'])
        for item in mode['items'][:6]:
            numbers = ''
            if item['demand'] is not None and item['capacity'] is not None:
                unit = (item['unit'] or '').replace('kN*m', 'kN·m')
                numbers = f"：需求 {fmt(item['demand'])} {unit}，能力 {fmt(item['capacity'])} {unit}"
                if item['exceed_pct'] is not None:
                    numbers += f"，需求超出 {item['exceed_pct']}%"
            lines.append(f"- {item['label']} — {item['verdict']}{numbers}")
        if len(mode['items']) > 6:
            lines.append(f"- 另有 {len(mode['items']) - 6} 项同类结果，见验算明细")
        if mode['note']:
            lines.append(f"- 注意：{mode['note']}")
        lines.append('')
    if diag['margins']:
        section('裕度最小的已满足项')
        lines += [f"- {m['label']}：能力/需求 {fmt(m['ratio'])}，裕度 {m['margin_pct']}%" for m in diag['margins']]
        lines.append('')
    if diag['measures']:
        section('候选加固措施')
        for key, measure in diag['measures'].items():
            targets = '、'.join(m['title'] for m in diag['modes'] if key in m['measures'])
            lines += [f"### {measure['title']}", f"- 针对：{targets}", f"- 作用：{measure['effect']}",
                      f"- 注意：{measure['caution']}", f"- 依据：{measure['code']}", '']
    if diag['retrofit_effect']:
        section('现有加固方案效果')
        for row in diag['retrofit_effect']:
            change = f"，需求变化 {row['demand_change_pct']:+g}%" if row['demand_change_pct'] is not None else ''
            lines.append(f"- {row['label']}：{row['before']} → {row['after']}{change}")
        lines.append('')
    section('下一步工作')
    lines += [f"{s['order']}. 【{s['owner']}】{s['action']}。{s['why']}。" for s in diag['next_steps']]
    lines += ['', '---', '本建议由规则库根据确定性判定结果生成，属于方案比选的起点，不是验算结论；'
              '任何加固措施都须重新建模、由第三步复算并经专业人员复核（engineering_release=false）。']
    return '\n'.join(lines)


NUMBER = re.compile(r'(?<![\w.])\d+(?:\.\d+)?')


def grounding(text, *sources):
    """Numbers in the memo that appear nowhere in the engine data (tolerance 0.5 %, integers below 100 ignored)."""
    known = {float(n) for source in sources for n in NUMBER.findall(json.dumps(source, ensure_ascii=False, default=str))}
    missing = []
    for raw in NUMBER.findall(text):
        value = float(raw)
        if value < 100 and '.' not in raw:
            continue
        if any(abs(value - k) <= max(abs(k) * 0.005, 0.0006) for k in known):
            continue
        if raw not in missing:
            missing.append(raw)
    return missing
