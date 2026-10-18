"""Chapter 9: conclusions generated deterministically from the judged items (76K chapter 9 phrasing)."""
from .common import fmt

DIR_WORD = {'longitudinal': '纵桥向', 'transverse': '横桥向'}
CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩'
METHODS = {'response_spectrum': '反应谱法', 'nonlinear_time_history': '非线性时程分析法', 'linear_time_history': '线性时程分析法'}
GROUP_WORDS = {'level2': '二级抗震措施', 'level3': '三级抗震措施'}


def join(items):
    items = list(dict.fromkeys(i for i in items if i))
    return '、'.join(items)


def where(item):
    return f"{DIR_WORD[item['direction']]}{item['section_label']}" if item.get('direction') else item['section_label']


class _Numbered:
    def __init__(self):
        self.n = 0

    def next(self):
        self.n += 1
        return f'（{self.n}）'


def e1_text(b):
    items = [i for i in b.items(level='E1') if i['status'] != 'NA']
    fails = [i for i in items if i['status'] == 'FAIL']
    blocked = [i for i in items if i['status'] == 'BLOCKED']
    if fails or blocked:
        parts = []
        if fails:
            parts.append(f"{join(where(i) + i['kind_label'].replace('E1', '') for i in fails)}不满足要求（{fails[0]['verdict']}）")
        if blocked:
            parts.append(f"{join(where(i) + i['kind_label'].replace('E1', '') for i in blocked)}资料待补正")
        return '；'.join(parts) + '；根据本项目验算流程，E2地震作用下的验算未开展。'
    text = '桥墩、桩基截面承载力验算均通过，结构均处于弹性工作状态'
    displacement = [i for i in items if i['kind'] == 'bearing_displacement']
    if displacement:
        text += '；支座位移验算均满足要求' + ('（位移限值为暂定值）' if any(i.get('provisional') for i in displacement) else '')
    sliding = [i for i in items if i['kind'] == 'bearing_sliding']
    if sliding:
        text += '，支座抗滑移验算均满足要求'
    return text + '。'


def member_text(b):
    parts = []
    plastic = b.items(level='E2', kind='e2_moment', component_kind='pier', status='PLASTIC')
    if plastic:
        by_direction = {}
        for i in plastic:
            by_direction.setdefault(i['direction'], []).append(i['section_label'])
        parts.append('；'.join(f'{DIR_WORD[d]}E2地震作用下{join(s)}截面弯矩大于等效屈服弯矩，进入塑性状态' for d, s in by_direction.items())
                     + '，其余桥墩截面保持弹性')
    else:
        parts.append('桥墩截面弯矩均小于等效屈服弯矩，保持弹性')
    piles = b.items(level='E2', kind='e2_moment', component_kind='pile')
    pile_fail = [i for i in piles if i['status'] == 'FAIL']
    pile_blocked = [i for i in piles if i['status'] == 'BLOCKED' and '超强' in i['reason']]
    pile_missing = [i for i in piles if i['status'] == 'BLOCKED' and '超强' not in i['reason']]
    recomputed = [i for i in piles if i['status'] == 'PASS' and i.get('overstrength')]
    if pile_fail:
        parts.append(f'{join(where(i) for i in pile_fail)}桩基进入屈服，不满足能力保护要求')
    elif pile_blocked or pile_missing:
        if pile_blocked:
            parts.append(f'{join(where(i) for i in pile_blocked)}桩基弯矩超过等效屈服弯矩，待超强弯矩体系传力复算后判定')
        if pile_missing:
            parts.append(f'{join(where(i) for i in pile_missing)}桩基抗弯验算资料待补正')
    elif piles:
        text = '桩基截面弯矩均小于等效屈服弯矩，满足能力保护要求'
        if recomputed:
            text = f'桩基满足能力保护要求（其中{join(where(i) for i in recomputed)}按超强弯矩体系传力复算）'
        parts.append(text)
    shear = b.items(level='E2', kind='shear')
    shear_fail = [i for i in shear if i['status'] == 'FAIL']
    if shear_fail:
        parts.append(f'{join(where(i) for i in shear_fail)}剪切破坏，抗剪不满足要求')
    elif shear and all(i['status'] == 'PASS' for i in shear):
        parts.append('桥墩、桩基抗剪验算均满足要求')
    for stop in b.result.get('stops', []):
        if stop['stage'] == 'original' and stop['gate'] in ('e2_pile', 'shear'):
            parts.append('根据本项目验算流程，后续支座及延性验算未开展')
    hinge = b.items(kind='hinge_shear')
    for i in hinge:
        if i['status'] == 'FAIL':
            parts.append(f"对{where(i)}进行塑性铰区域抗剪验算，其能需比为{i['ratio']:.3f}＜1，不满足延性抗震设计要求")
        elif i['status'] == 'PASS':
            parts.append(f"{where(i)}塑性铰区域抗剪能需比为{i['ratio']:.3f}＞1，满足要求")
    for kind, word in (('ductility_displacement', '位移延性'), ('ductility_reinforcement', '延性构造配箍率')):
        judged = [i for i in b.items(kind=kind) if i['status'] in ('PASS', 'FAIL')]
        if judged:
            fails = [i for i in judged if i['status'] == 'FAIL']
            parts.append(f'{join(where(i) for i in fails)}{word}验算不满足要求' if fails else f'{word}验算满足要求')
    return '；'.join(parts) + '。'


def bearing_text(b):
    items = [i for i in b.items(level='E2') if i['kind'] in ('bearing_displacement', 'bearing_sliding', 'measures', 'additional')
             and i['status'] not in ('NA', 'SKIPPED')]
    if not items:
        return None
    fails = [i for i in items if i['status'] == 'FAIL']
    blocked = [i for i in items if i['status'] == 'BLOCKED']
    if fails:
        text = f"{join(where(i) + i['kind_label'] for i in fails)}不满足要求"
    else:
        text = '支座位移' + ('及抗滑移' if any(i['kind'] == 'bearing_sliding' for i in items) else '') + '验算均满足要求'
        if any(i.get('provisional') for i in items):
            text += '（位移限值为暂定值）'
    if blocked:
        text += f"；{join(where(i) + i['kind_label'] for i in blocked)}资料待补正"
    return text + '。'


def pilecap_text(b):
    items = [i for i in b.items(kind='pilecap') if i['status'] != 'SKIPPED']
    if not items:
        return None
    titles = join(i['title'].replace('承台', '').replace('验算', '') for i in items)
    fails = [i for i in items if i['status'] == 'FAIL']
    if fails:
        return f"承台{join(i['title'].replace('承台', '').replace('验算', '') for i in fails)}验算不满足规范要求。"
    return f'承台{titles}验算均满足规范要求。'


def retrofit_text(b):
    items = [i for i in b.items('retrofit') if i['status'] not in ('NA',)]
    if not items:
        return None
    parts = []
    for i in items:
        if i['kind'] == 'hinge_shear':
            sign = '＞' if i['status'] == 'PASS' else '＜'
            parts.append(f"塑性铰区域抗剪能需比为{i['ratio']:.3f}{sign}1")
        elif i['kind'] == 'ductility_displacement':
            sign = '＜' if i['status'] == 'PASS' else '＞'
            parts.append(f"位移需求为{fmt(i['demand'])} m{sign}容许位移{fmt(i['capacity'])} m")
        elif i['kind'] == 'ductility_reinforcement':
            sign = '＞' if i['status'] == 'PASS' else '＜'
            parts.append(f"配箍率能力为{fmt(i['capacity'])}{sign}需求{fmt(i['demand'])}")
        elif i['status'] == 'FAIL':
            parts.append(f"{where(i)}{i['kind_label']}仍不满足要求")
    ductility = [i for i in items if i['kind'] in ('hinge_shear', 'ductility_displacement', 'ductility_reinforcement')]
    tail = ''
    if ductility:
        tail = '，均满足延性抗震设计要求' if all(i['status'] == 'PASS' for i in ductility) else '，延性抗震设计要求仍未全部满足'
    blocked = [i for i in items if i['status'] == 'BLOCKED']
    if blocked:
        tail += f"；{join(where(i) + i['kind_label'] for i in blocked)}加固后验算资料待补正"
    return '经韧性提升后，' + '，'.join(parts) + tail + '。'


def detailing_text(b):
    items = [i for i in b.items() if i['kind'] in ('edge_distance', 'detailing')]
    if not items:
        return None
    if any(i['id'].endswith('missing') for i in items):
        return '构造措施验算资料未提供，待补正。'
    segments = []
    edges = [i for i in items if i['kind'] == 'edge_distance']
    if edges:
        fails = [i for i in edges if i['status'] == 'FAIL']
        if fails:
            segments.append(f"{join(i['section_label'] for i in fails)}梁端边距不满足一级抗震措施要求")
        else:
            segments.append(f"{join(i['section_label'] for i in edges)}梁端边距均满足一级抗震措施要求")
    for group, word in GROUP_WORDS.items():
        rows = [i for i in items if i.get('group') == group]
        if not rows:
            continue
        passed = [i['section_label'] for i in rows if i['status'] == 'PASS']
        failed = [i for i in rows if i['status'] == 'FAIL']
        pending = [i['section_label'] for i in rows if i['status'] == 'BLOCKED']
        text = f'{word}中，'
        if passed and not failed:
            text += f'{join(passed)}均满足要求'
        elif passed:
            text += f'{join(passed)}满足要求，但'
        if failed:
            text += join(f"{i['section_label']}不满足要求（{i['row']['requirement'].rstrip('。')}）" for i in failed)
        if pending:
            text += f'；{join(pending)}满足情况待确认'
        segments.append(text)
    return '参考《公路桥梁抗震设计规范》（JTG/T 2231-01—2020）要求，' + '；'.join(segments) + '。'


def pending_text(b):
    notes = []
    final = [i for i in b.result.get('items', []) if i.get('final')]
    provisional = [i for i in final if i.get('provisional')]
    if provisional:
        notes.append(f"支座位移验算：{provisional[0]['limit_basis']}")
    na = [i for i in final if i['status'] == 'NA' and i['kind'] == 'bearing_sliding']
    if na:
        notes.append(f"{join(i['section_label'] for i in na)}支座抗滑移验算不适用（{na[0]['reason']}）")
    blocked = [i for i in final if i['status'] == 'BLOCKED']
    if blocked:
        notes.append(f"{join(where(i) + i['kind_label'] for i in blocked)}资料待补正，补正后需重新判定")
    return '；'.join(notes) + '。' if notes else None


def summary_text(b):
    r = b.result
    segments = []
    e1 = next((g for g in r['gates'] if g['id'] == 'e1'), {})
    if e1.get('status') == 'PASS':
        segments.append('该桥梁在E1地震作用下结构均处于弹性工作状态')
    else:
        segments.append('该桥梁E1地震作用下的验算存在' + ('不满足项' if e1.get('status') == 'FAIL' else '待补正项') + '，E2地震作用下的验算未开展')
    if e1.get('status') == 'PASS':
        plastic = r.get('plastic', [])
        if plastic:
            segments.append('E2地震作用下' + join(f"{DIR_WORD[p['direction']]}{p['section_label']}" for p in plastic) + '截面进入塑性状态')
        else:
            segments.append('E2地震作用下桥墩、桩基均保持弹性')
        after = [i for i in b.items('retrofit') if i['kind'] in ('hinge_shear', 'ductility_displacement', 'ductility_reinforcement')]
        original = [i for i in b.items() if i['kind'] in ('hinge_shear', 'ductility_displacement', 'ductility_reinforcement')
                    and i['status'] != 'NA']
        if after and all(i['status'] == 'PASS' for i in after):
            segments.append('经韧性加固后该截面塑性铰区域抗剪、位移延性及延性构造配箍率验算均满足要求，可按延性抗震设计')
        elif original and all(i['status'] == 'PASS' for i in original):
            segments.append('塑性铰区域抗剪、位移延性及延性构造配箍率验算均满足要求，可按延性抗震设计')
        elif original:
            segments.append('延性验算未全部满足要求')
        caps = [i for i in b.items(kind='pilecap') if i['status'] in ('PASS', 'FAIL')]
        if caps:
            segments.append('承台相关验算' + ('满足规范要求' if all(i['status'] == 'PASS' for i in caps) else '存在不满足项'))
    for group, word in GROUP_WORDS.items():
        failed = [i['section_label'] for i in b.items(kind='detailing') if i.get('group') == group and i['status'] == 'FAIL']
        if failed:
            segments.append(f'{word}中{join(failed)}不满足要求')
    closing = {'PASS': '在声明范围内满足本流程抗震验算要求。',
               'FAIL': '需针对上述不满足项采取加强措施，并以新模型版本重新交接验算。',
               'BLOCKED': '待补正资料齐全后需重新判定。'}[r['status']]
    return '综上所述，' + '；'.join(segments) + '。' + closing


def build(b):
    b.h(1, '结论')
    project = b.get('project', {})
    methods = b.get('analysis.methods', {})
    method_words = join(METHODS.get(methods.get(level)) for level in ('E1', 'E2')).replace('、', '和') or '反应谱法'
    b.p(f"根据{project.get('route', '')}设计桩号为{project.get('stake', '')}桥梁的抗震验算分析，建立全桥空间动力计算模型，采用{method_words}"
        '进行地震反应分析，并依据现行抗震规范对结构在两水准设防地震作用（E1地震和E2地震）下的抗震性能进行验算，得出如下结论：')
    number = _Numbered()
    b.p(f'{number.next()}E1地震作用下：{e1_text(b)}')
    e1 = next((g for g in b.result['gates'] if g['id'] == 'e1'), {})
    if e1.get('status') == 'PASS':
        b.p(f'{number.next()}E2地震作用下：')
        circled = iter(CIRCLED)
        for text in (member_text(b), bearing_text(b), pilecap_text(b), retrofit_text(b)):
            if text:
                b.p(f'{next(circled)} {text}')
    elif retrofit_text(b):
        b.p(f'{number.next()}{retrofit_text(b)}')
    detailing = detailing_text(b)
    if detailing:
        b.p(f'{number.next()}{detailing}')
    pending = pending_text(b)
    if pending:
        b.p(f'{number.next()}需说明及待补正事项：{pending}')
    b.p(summary_text(b))
