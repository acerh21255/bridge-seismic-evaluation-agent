"""Chapter 6: seismic checks — method, E1, E2, pile caps and detailing measures."""
from ...engine.terms import KIND_LABELS
from ..library import figure_path
from ..model import Figure, Table, Para
from .common import cell, fmt, ratio_text, ref, verdict_cell, rich

DIR_WORD = {'longitudinal': '纵桥向', 'transverse': '横桥向'}
DIR_SHORT = {'longitudinal': '纵向', 'transverse': '横向'}
INPUT_HEADINGS = {'longitudinal': '（1）纵向输入', 'transverse': '（2）横向输入'}
METHOD_WORDS = {'response_spectrum': '反应谱', 'nonlinear_time_history': '非线性时程结果', 'linear_time_history': '线性时程结果'}
CODE = '《公路桥梁抗震设计规范》（JTG/T 2231-01—2020）'

OVERVIEW = '根据设计图纸提供的配筋形式，对各关键截面性能、结构关键位移、装置变形等进行验算。'
EQUIVALENT = ('截面等效抗弯强度实质上是一个理论上的概念值，是将实际的截面弯矩－曲率曲线按能量等效的原则将其等效为一个弹塑性曲线。'
              '中间的等效抗弯强度M_{eq}计算规则如{fig}，由阴影部分面积相等求得。其中M_{y}为截面相应于最不利轴力时最外层钢筋首次屈服时对应的初始屈服弯矩；'
              'M_{eq}为相应于最不利轴力时截面等效抗弯屈服弯矩；M_{u}为截面极限弯矩。')
LEVELS = ('E1地震作用效应和自重荷载效应组合后，按现行的公路桥涵设计规范有关偏心受压/拉构件的规定进行验算；E2地震作用效应和自重荷载效应组合后，'
          '局部可发生可修复损伤，采用等效屈服弯矩进行验算。')
METHOD_INTRO = '根据前述对桥梁抗震性能的要求，采用如下方法对关键截面进行抗震性能验算，关键截面的具体验算方法及过程如下：'
FIBER = ('首先，将桥墩和桩基截面划分为纤维单元，在划分纤维单元时，混凝土和钢筋单元分别划分，钢筋和混凝土单元分别采用实际的钢筋和混凝土应力－应变关系。'
         '利用实际的钢筋和混凝土应力－应变关系，采用截面数值积分法进行弯矩－曲率分析（考虑相应轴力），得到{fig}所示弯矩－曲率曲线。{fig}中，'
         'M_{y}为截面最外层钢筋首次屈服时对应的初始屈服弯矩；M_{u}为截面极限弯矩；M_{eq}为截面等效抗弯屈服弯矩，即把实际弯矩－曲率曲线等效为图中所示'
         '弹塑性双线性恢复模型时的等效抗弯屈服弯矩。具体验算方法为：')
E1_RULE = ('（1）E1地震作用下，根据两水准抗震设防要求，在E1地震作用下要求结构保持弹性，基本无损伤，E1地震作用效应和自重荷载效应组合后，'
           '按现行的公路桥涵设计规范有关偏心受压构件的规定进行验算。')
E2_RULE = ('（2）E2地震作用下，关键截面要求其在地震作用下的截面弯矩应小于截面等效抗弯屈服弯矩M_{eq}（考虑轴力）。M_{eq}是把实际弯矩－曲率曲线'
           '等效为{fig}中所示理想弹塑性双线性模型时得到的等效抗弯屈服弯矩。从理想弹塑性双线性模型看，当地震反应小于等效抗弯屈服弯矩M_{eq}，'
           '结构整体反应还在弹性范围。实际上，在地震过程中，对应于等效抗弯屈服弯矩M_{eq}，截面上还是有部分钢筋进入了屈服，研究表明：'
           '截面的裂缝宽度可能会超过容许值，但混凝土保护层还是完好（对应保护层损伤的弯矩为截面极限弯矩M_{u}，M_{u}＞M_{eq}）。'
           '由于地震过程的持续时间比较短，地震后，由于结构自重，地震过程开展的裂缝一般可以闭合，不影响使用，满足E2水准下局部可发生可修复的损伤，'
           '地震发生后，基本不影响车辆通行的性能要求。')
AXIAL = '地震动引起的拉力效应抵消了一部分由恒载产生的压应力，验算时，取“最不利轴力＝恒载轴力－地震动轴力”，这种组合方式能够更真实地反映结构在地震作用下的受力状态。'
E1_TAIL = '根据前述设定的抗震性能目标，在E1地震作用下，结构构件应保持在弹性范围内工作。依据规范组合要求，通过恒载轴力与地震动轴力的叠加形成组合内力。'
E2_TAIL = '桥墩弯矩超过等效屈服弯矩时记为进入塑性，并开展延性验算；桩基作为能力保护构件不允许进入屈服。'
EDGE = ('参考' + CODE + '要求，简支梁桥和连续梁桥上部结构梁端至墩、台帽或盖梁边缘应有一定的距离，其最小值a(cm)应按下式计算，且不应小于60cm。')
EDGE_TERMS = ['L——一联上部结构总长度（m）；', 'H——支承一联上部结构桥墩的平均高度（m），桥台的高度取值为0；', 'L_{k}——一联上部结构的最大单孔跨径（m）。']
CHECK_WIDTHS = [1100, 1100, 1576, 1695, 1637, 1078, 1100]
BEARING_WIDTHS = [1591, 953, 1411, 2050, 1679, 1595]


def with_refs(template, key):
    """Split a text template on {fig} and interleave figure references."""
    parts = []
    for n, piece in enumerate(template.split('{fig}')):
        if n:
            parts.append(ref(key))
        parts.append(piece)
    return parts


def method_basis(b):
    b.h(2, '概述')
    b.p(OVERVIEW)
    b.p('钢筋混凝土截面的抗弯能力（强度）采用纤维单元进行弯矩－曲率（考虑相应轴力）分析获得，如', ref('fig-m-phi'), '所示。')
    b.figure('fig-m-phi', '等效屈服弯矩的计算图示', image=figure_path('m_phi'), width_cm=8.3)
    b.p(*with_refs(EQUIVALENT, 'fig-m-phi'))
    b.p(LEVELS)
    b.h(2, '验算方法')
    b.p(METHOD_INTRO)
    b.p(*with_refs(FIBER, 'fig-m-phi'))
    b.p(E1_RULE)
    b.p(*with_refs(E2_RULE, 'fig-m-phi'))
    figures = b.get('model.figures', {})
    row = []
    for key, asset_key, caption in (('fig-fiber-pile', 'fiber_pile', '桩基截面纤维模型'), ('fig-fiber-pier', 'fiber_pier', '桥墩截面纤维模型')):
        image, width, asset_caption = b.asset(figures.get(asset_key), caption)
        row.append(Figure(key, asset_caption or caption, image=image, width_cm=width or 7.3))
    b.figure_row(row)
    b.fragment('shear_formulas')


def member_table(b, level, kind, component_kind, direction):
    items = b.items(level=level, kind=kind, component_kind=component_kind, direction=direction)
    if not items:
        return None
    who = '桥墩各关键截面' if component_kind == 'pier' else '桩基截面'
    key = f'tab-{level}-{kind}-{component_kind}-{direction}'
    if kind == 'e1_capacity':
        moment = f'{DIR_SHORT[direction]}弯矩(kN·m)' if component_kind == 'pier' else '弯矩(kN·m)'
        return b.check_table(key, f'E1地震作用下{who}抗震验算结果({DIR_WORD[direction]})',
                             ['地震作用', '关键截面', '最不利轴力(kN)', moment, '截面承载力(kN)', '能力/需求', '验算结果'], items,
                             lambda i: [i['section_label'], fmt(i['axial_kN']), fmt(i['moment_kNm']), fmt(i['capacity']),
                                        ratio_text(i['ratio'])], widths=CHECK_WIDTHS)
    if kind == 'e2_moment':
        notes = []
        for i in items:
            strength = i.get('overstrength')
            if strength:
                notes.append(f"注：{i['section_label']}关联桥墩已进入塑性，表中弯矩为按超强弯矩（超强系数{fmt(strength['factor'])}）体系传力复算结果，"
                             f"直接分析弯矩为{fmt(i['direct_demand'])} kN·m。")
            elif i['status'] == 'BLOCKED' and '超强' in i['reason']:
                notes.append(f"注：{i['section_label']}桩基弯矩超过等效屈服弯矩且关联桥墩已进入塑性，待第三步提交超强弯矩体系传力复算结果后判定。")
        return b.check_table(key, f'E2地震作用下{who}抗震验算结果({DIR_WORD[direction]})',
                             ['地震作用', '关键截面', '最不利轴力(kN)', '弯矩(kN·m)', '等效屈服弯矩(kN·m)', '能力/需求', '验算结果'], items,
                             lambda i: [i['section_label'], fmt(i['axial_kN']), fmt(i['demand']), fmt(i['capacity']), ratio_text(i['ratio'])],
                             widths=[1100, 1100, 1589, 1371, 1974, 1052, 1100], notes=notes)
    notes = [f"注：{i['section_label']}剪力采用超强弯矩体系传力复算结果，直接分析剪力为{fmt(i['direct_demand'])} kN。"
             for i in items if i.get('overstrength')]
    return b.check_table(key, f'E2地震作用下{who}抗剪验算结果({DIR_WORD[direction]})',
                         ['地震作用', '关键截面', '轴力(kN)', '剪力(kN)', '抗剪能力(kN)', '能力/需求', '验算结果'], items,
                         lambda i: [i['section_label'], fmt(i['axial_kN']), fmt(i['demand']), fmt(i['capacity']), ratio_text(i['ratio'])],
                         widths=CHECK_WIDTHS, notes=notes)


def bearing_tables(b, level, direction):
    displacement = b.items(level=level, kind='bearing_displacement', direction=direction)
    sliding = b.items(level=level, kind='bearing_sliding', direction=direction)
    shown_sliding = [i for i in sliding if i['status'] != 'NA']
    not_applicable = [i for i in sliding if i['status'] == 'NA']
    notes = []
    provisional = [i for i in displacement if i.get('provisional')]
    if provisional:
        notes.append(f"注：{provisional[0]['limit_basis']}。")
    if any(i['ratio'] is None and i['status'] == 'PASS' for i in displacement):
        notes.append('注：位移需求为 0 时不计算能力/需求比。')
    if not_applicable and not shown_sliding:
        labels = '、'.join(i['section_label'] for i in not_applicable)
        notes.append(f"注：{labels}支座抗滑移验算不适用（{not_applicable[0]['reason']}）。")
    shown = [i for i in displacement if i['status'] != 'NA']
    if shown:
        b.check_table(f'tab-{level}-bearing-disp-{direction}', f'{level}地震作用下支座位移抗震验算结果({DIR_WORD[direction]})',
                      ['地震作用', '位置', f'{DIR_SHORT[direction]}位移(m)', '规范限值(m)', '能力/需求', '验算结果'], shown,
                      lambda i: [i['section_label'], fmt(i['demand'], 3), fmt(i['capacity']), ratio_text(i['ratio'])],
                      widths=BEARING_WIDTHS, notes=notes if not shown_sliding else [n for n in notes if '抗滑移' not in n])
    if shown_sliding:
        b.check_table(f'tab-{level}-bearing-slide-{direction}', f'{level}地震作用下支座抗滑移验算结果({DIR_WORD[direction]})',
                      ['地震作用', '验算位置', '需求(kN)', '抗力(kN)', '能力/需求', '验算结果'], shown_sliding,
                      lambda i: [i['section_label'], fmt(i['demand']), fmt(i['capacity']), ratio_text(i['ratio'])], widths=BEARING_WIDTHS)


def special_tables(b, direction):
    items = [i for i in b.items(level='E2', direction=direction) if i['kind'] in ('measures', 'additional') and i['status'] != 'NA']
    if items:
        b.check_table(f'tab-E2-special-{direction}', f'E2地震作用下抗滑措施及专项构件验算结果({DIR_WORD[direction]})',
                      ['地震作用', '构件', '验算内容', '需求', '能力', '能力/需求', '验算结果'], items,
                      lambda i: [i['section_label'], i.get('title') or KIND_LABELS[i['kind']], f"{fmt(i['demand'])} {i['unit']}",
                                 f"{fmt(i['capacity'])} {i['unit']}", ratio_text(i['ratio'])])


def pilecap_tables(b):
    items = b.items(kind='pilecap')
    if not items:
        return
    checks = {c['id']: c for c in b.get('pilecap.checks', [])}
    keys = [f"tab-pilecap-{i['pilecap_id']}" for i in items]
    necessity = b.get('pilecap.necessity')
    if not necessity:
        b.missing.append('承台冲切验算必要性分析（报告采用通用表述）')
        necessity = '承台属于能力保护构件，E2地震作用下按能力保护原则对承台斜压杆承载力、拉杆承载力及冲切承载力进行验算。'
    b.p(necessity, '验算结果见', ref(keys[0]), *(['～', ref(keys[-1])] if len(keys) > 1 else []), '。')
    for item, key in zip(items, keys):
        check = checks[item['pilecap_id']]
        header = check.get('header') or [item['title'], '单位', '数值']
        factor = f"安全系数{item['ratio']:.2f}" if item['ratio'] is not None else '—'
        table = b.data_table(key, f"E2地震作用下{item['title']}（{DIR_WORD[item['direction']]}）",
                             {'header': header, 'rows': check['rows'] + [['是否满足规范要求', item['verdict'], factor]]}, merge_first=True)
        table.rows[-1][1] = verdict_cell(item['verdict'])


def e1_section(b):
    b.h(3, 'E1地震作用下抗震验算')
    method = METHOD_WORDS.get(b.get('analysis.methods.E1'), '反应谱')
    b.p(f'在E1地震作用下，对纵桥向和横桥向采用{method}进行验算，' + AXIAL + E1_TAIL)
    for direction in ('longitudinal', 'transverse'):
        b.h(4, INPUT_HEADINGS[direction], numbered=False)
        member_table(b, 'E1', 'e1_capacity', 'pier', direction)
        member_table(b, 'E1', 'e1_capacity', 'pile', direction)
        bearing_tables(b, 'E1', direction)


def e2_section(b):
    b.h(3, 'E2地震作用下抗震验算')
    e1_gate = next((g for g in b.result['gates'] if g['id'] == 'e1'), {})
    if e1_gate.get('status') != 'PASS':
        word = '不满足项' if e1_gate.get('status') == 'FAIL' else '待补正项'
        b.p(f'由于E1地震作用下的验算存在{word}，根据本项目验算流程，E2地震作用下的抗震验算未开展，需在E1问题处理并重新交接后进行。')
        return
    method = METHOD_WORDS.get(b.get('analysis.methods.E2'), '非线性时程结果')
    b.p(f'在E2地震作用下，对纵桥向和横桥向采用{method}进行验算。' + AXIAL + E2_TAIL)
    for direction in ('longitudinal', 'transverse'):
        b.h(4, INPUT_HEADINGS[direction], numbered=False)
        member_table(b, 'E2', 'e2_moment', 'pier', direction)
        member_table(b, 'E2', 'shear', 'pier', direction)
        member_table(b, 'E2', 'e2_moment', 'pile', direction)
        member_table(b, 'E2', 'shear', 'pile', direction)
        bearing_tables(b, 'E2', direction)
        special_tables(b, direction)
    pilecap_tables(b)
    for stop in b.result.get('stops', []):
        if stop['stage'] == 'original' and stop['gate'] != 'e1':
            b.p(f"根据本项目验算流程，{stop['reason']}。")


def detailing_table(b, key, caption, headers, rows, widths):
    header = [[cell(h, bold=True) for h in headers]]
    body = [[cell(v) for v in row[:-1]] + [verdict_cell(row[-1])] for row in rows]
    notes = [Para(rich('表中 — 表示原始资料未提供，本项须补充证据后判定。'), style='note')] if any('—' in str(v) for row in rows for v in row) else []
    b.add(Table(key, caption, header, body, widths=widths, notes=notes))


def detailing_section(b):
    b.h(2, '构造措施验算')
    b.p('参考' + CODE + '要求，对桥梁构造措施进行验算。')
    if any(i['kind'] == 'detailing' and i['status'] == 'BLOCKED' and i['id'].endswith('missing') for i in b.items()):
        b.p('（构造措施验算资料未提供，待第三步补充。）')
        return
    b.h(3, '一级抗震措施')
    b.p(EDGE)
    b.picture(figure_path('beam_end_formula'), 5.5)
    for term in EDGE_TERMS:
        b.p(term)
    b.figure('fig-beam-end', '梁端至墩、台帽或盖梁边缘的最小距离a', image=figure_path('beam_end_distance'), width_cm=7.3)
    level1 = [i for i in b.items(kind='edge_distance')]
    detailing_table(b, 'tab-detailing-1', '构造措施验算', ['墩号', '设计值（cm）', '规范要求值（cm）', '验算结果'],
                    [[i['section_label'], fmt(i['capacity']), fmt(i['demand']), i['verdict']] for i in level1] or [['（资料未提供）', '', '', '待补正']],
                    [2200, 2200, 2400, 2200])
    for group, title, level in (('level2', '二级抗震措施', '二'), ('level3', '三级抗震措施', '三')):
        b.h(3, title)
        rows = [[i['row']['clause'], i['row']['requirement'], i['row']['design'], i['verdict']]
                for i in b.items(kind='detailing') if i.get('group') == group]
        detailing_table(b, f'tab-detailing-{group}', f'{level}级抗震措施验算表格', ['规范序号', '规范要求', '本桥设计', '是否满足'],
                        rows or [['—', '（资料未提供）', '—', '待补正']], [1100, 4200, 2500, 1200])


def build(b):
    b.h(1, '抗震验算')
    method_basis(b)
    b.h(2, '抗震验算')
    e1_section(b)
    e2_section(b)
    detailing_section(b)
