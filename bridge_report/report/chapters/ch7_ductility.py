"""Chapter 7: ductility checks of piers that enter plasticity in the original state."""
from .common import fmt, ratio_text, ref

DIR_WORD = {'longitudinal': '纵桥向', 'transverse': '横桥向'}
DIRECTIONS = ('longitudinal', 'transverse')
HINGE_HEADERS = ['地震作用', '关键截面', '最不利轴力(kN)', '剪力(kN)', '抗剪能力(kN)', '能力/需求', '验算结果']


def phi_note(items):
    phis = sorted({i['phi'] for i in items if i.get('phi', 1.0) != 1.0})
    return [f"注：能力/需求按φV_{{n}}/V_{{0}}计算，强度折减系数φ={fmt(phis[0])}。"] if phis else []


def hinge_tables(b, stage='original'):
    for direction in DIRECTIONS:
        items = [i for i in b.items(stage, kind='hinge_shear', direction=direction) if i['status'] not in ('NA',)]
        if items:
            b.check_table(f'tab-{stage}-hinge-{direction}', f'E2地震作用下桥墩塑性铰区抗剪验算结果({DIR_WORD[direction]})', HINGE_HEADERS,
                          items, lambda i: [i['section_label'], fmt(i['axial_kN']), fmt(i['demand']), fmt(i['capacity']),
                                            ratio_text(i['ratio'])], notes=phi_note(items))


def displacement_tables(b, items, stage):
    for direction in DIRECTIONS:
        rows = [i for i in items if i['direction'] == direction]
        if rows:
            b.check_table(f'tab-{stage}-disp-{direction}', f'E2地震作用下已屈服桥墩的位移延性验算结果({DIR_WORD[direction]})',
                          ['地震作用', '关键截面', '位移需求(m)', '容许位移(m)', '验算结果'], rows,
                          lambda i: [i['section_label'], fmt(i['demand']), fmt(i['capacity'])], widths=[1478, 2514, 1905, 1905, 1477])


def reinforcement_tables(b, items, stage):
    for direction in DIRECTIONS:
        rows = [i for i in items if i['direction'] == direction]
        if rows:
            b.check_table(f'tab-{stage}-rho-{direction}', f'已屈服桥墩的配箍率验算结果({DIR_WORD[direction]})',
                          ['地震作用', '关键截面', '能力', '需求', '验算结果'], rows,
                          lambda i: [i['section_label'], fmt(i['capacity']), fmt(i['demand'])], widths=[1478, 2514, 1905, 1905, 1477])


def build(b):
    if not b.result.get('plastic'):
        return
    b.h(1, '延性抗震设计验算')
    b.h(2, '塑性铰区抗剪验算')
    b.fragment('hinge_shear_formulas')
    hinge_tables(b)
    judged = lambda kind: [i for i in b.items(kind=kind) if i['status'] not in ('SKIPPED', 'NA')]  # noqa: E731
    displacement, reinforcement = judged('ductility_displacement'), judged('ductility_reinforcement')
    if displacement:
        b.h(2, '位移延性验算')
        b.fragment('displacement_ductility')
        displacement_tables(b, displacement, 'original')
    if reinforcement:
        b.h(2, '延性构造配箍率验算')
        b.fragment('stirrup_ratio')
        reinforcement_tables(b, reinforcement, 'original')
    skipped = [i for i in b.items(kind='ductility_displacement') + b.items(kind='ductility_reinforcement') if i['status'] == 'SKIPPED']
    if skipped:
        failed = [i for i in b.items(kind='hinge_shear') if i['status'] == 'FAIL']
        sections = '、'.join(dict.fromkeys(f"{DIR_WORD[i['direction']]}{i['section_label']}" for i in failed)) or '相关截面'
        tail = ['，韧性提升方案及加固后延性验算见第', ref('ch-retrofit'), '章。'] if b.get('retrofit') else ['，需采取加强措施后重新验算。']
        b.p(f'由于{sections}塑性铰区抗剪不满足，根据本项目验算流程，该截面位移延性与延性构造配箍率验算未开展', *tail)
