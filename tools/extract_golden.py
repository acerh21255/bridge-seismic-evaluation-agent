"""Extract the 76K278+308 reference report into a v2 handoff package (golden reference).

Reads templates/reference/G8511 76K278+308 ….docx (read-only) and writes
examples/golden/76K278+308/{handoff.json, assets/}. Element indexes refer to the body children of the
reference document; values are copied from the original tables. Intentional differences are listed in
examples/golden/76K278+308/DIFF.md and in the `notes` printed at the end.
"""
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge_report.contract.evidence import file_hash  # noqa: E402
from bridge_report.paths import GOLDEN_DIR, REFERENCE_76K  # noqa: E402
from bridge_report.report.charts import wave_spectra_png  # noqa: E402

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
WP = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
C = 'http://schemas.openxmlformats.org/drawingml/2006/chart'
REVISION = '76K278+308-原状-2026.03'
RETROFIT_REVISION = '76K278+308-ECC加固-2026.03'
SOURCE = 'orig-76K'
HINGE_PHI = 0.9  # 原报告式(7-1) φVn ≥ V0 的强度折减系数；原表8-2未计入，统一后见 DIFF.md


def q(tag, ns=W):
    return '{%s}%s' % (ns, tag)


def clean(text):
    return re.sub(r'\s+', ' ', text.replace('　', ' ')).strip()


def run_text(element, markup=True):
    parts = []
    for run in element.iter(q('r')):
        text = ''.join(t.text or '' for t in run.iter(q('t')))
        if not text:
            continue
        align = run.find(q('rPr') + '/' + q('vertAlign'))
        value = align.get(q('val')) if align is not None else ''
        if markup and value == 'subscript':
            parts.append('_{' + text + '}')
        elif markup and value == 'superscript':
            parts.append('^{' + text + '}')
        else:
            parts.append(text)
    return clean(''.join(parts).replace('}_{', '').replace('}^{', ''))


class Reference:
    def __init__(self, path):
        self.zip = zipfile.ZipFile(path)
        self.body = etree.fromstring(self.zip.read('word/document.xml')).find(q('body'))
        self.kids = list(self.body)
        rels = etree.fromstring(self.zip.read('word/_rels/document.xml.rels'))
        self.rels = {r.get('Id'): r.get('Target') for r in rels}

    def text(self, index, markup=False):
        return run_text(self.kids[index], markup)

    def table(self, index):
        rows = []
        for tr in self.kids[index].findall(q('tr')):
            rows.append([run_text(tc).replace('KN', 'kN') for tc in tr.findall(q('tc'))])
        return rows

    def images(self, index):
        found = []
        for drawing in self.kids[index].iter(q('drawing')):
            blip = next(drawing.iter(q('blip', A)), None)
            extent = next(drawing.iter(q('extent', WP)), None)
            if blip is None:
                continue
            target = self.rels[blip.get(q('embed', R))]
            found.append((self.zip.read('word/' + target), Path(target).suffix, round(int(extent.get('cx')) / 360000, 2)))
        return found

    def chart_series(self, name):
        root = etree.fromstring(self.zip.read(name))
        series = []
        for ser in root.iter(q('ser', C)):
            title = ''.join(v.text or '' for v in ser.find(q('tx', C)).iter(q('v', C)))
            xs = [float(p.find(q('v', C)).text) for p in ser.find(q('xVal', C)).iter(q('pt', C))]
            ys = [float(p.find(q('v', C)).text) for p in ser.find(q('yVal', C)).iter(q('pt', C))]
            series.append((title, xs, ys))
        return series


def num(text):
    return float(text.replace(',', '').strip())


class Golden:
    def __init__(self, reference, out_dir):
        self.ref = reference
        self.out = out_dir
        self.assets = []
        self.checks = []
        self.actions = []
        self.na = []

    # -- assets ---------------------------------------------------------------------------------------
    def asset(self, asset_id, index, caption, nth=0):
        blob, suffix, width = self.ref.images(index)[nth]
        return self.add_asset(asset_id, blob, suffix, caption, width)

    def add_asset(self, asset_id, blob, suffix, caption, width):
        path = self.out / 'assets' / f'{asset_id}{suffix}'
        path.write_bytes(blob)
        self.assets.append({'id': asset_id, 'path': f'assets/{path.name}', 'caption': caption, 'width_cm': width,
                            'sha256': hashlib.sha256(blob).hexdigest()})
        return asset_id

    def wave_spectra(self):
        series = self.ref.chart_series('word/charts/chart3.xml')
        waves = [s for s in series if s[0].startswith('地震波') or s[0] == '平均值']
        target = next(s for s in series if s[0] == 'E2反应谱')
        path = self.out / 'assets' / 'fig-wave-spectra.png'
        wave_spectra_png(waves, path, target=('E2反应谱', target[1], target[2]))
        self.assets.append({'id': 'fig-wave-spectra', 'path': 'assets/fig-wave-spectra.png',
                            'caption': '各条地震波的加速度反应谱与规范对比', 'width_cm': 16.0, 'sha256': file_hash(path),
                            'note': '据原报告内嵌图表数据（chart3）以 matplotlib 重绘'})

    # -- checks ---------------------------------------------------------------------------------------
    @staticmethod
    def member(section):
        digit = re.search(r'(\d+)#', section).group(1)
        return ('F' if '桩' in section else 'P') + digit

    def add_check(self, component, direction, level, kind, demand, capacity, unit, section, locator, **extra):
        record = {'component': component, 'section_label': section.replace(' ', ''), 'direction': direction, 'level': level,
                  'kind': kind, 'unit': unit, 'demand': demand, 'capacity': capacity,
                  'combination': extra.pop('combination', f"恒载+{level}{'纵向' if direction == 'longitudinal' else '横向'}"),
                  'model_revision': extra.pop('revision', REVISION), 'evidence': SOURCE, 'locator': locator}
        record.update(extra)
        return record

    def e1_members(self, index, direction, locator):
        for row in self.ref.table(index)[1:]:
            section, n, m, nu = row[1], num(row[2]), num(row[3]), num(row[4])
            component = self.member(section)
            action_id = f"E1-{component}-{'L' if direction == 'longitudinal' else 'T'}"
            combination = f"恒载+E1{'纵向' if direction == 'longitudinal' else '横向'}（最不利轴力=恒载轴力−地震轴力）"
            self.actions.append({'id': action_id, 'component': component, 'direction': direction, 'level': 'E1',
                                 'combination': combination, 'station': section, 'N_kN': n, 'M_kNm': m})
            self.checks.append(self.add_check(component, direction, 'E1', 'e1_capacity', n, nu, 'kN', section, locator,
                                              combination=combination, action_id=action_id, paired_N_M={'N_kN': n, 'M_kNm': m},
                                              method='constant_eccentricity'))

    def e2_members(self, index, direction, kind, locator):
        unit = 'kN*m' if kind == 'e2_moment' else 'kN'
        for row in self.ref.table(index)[1:]:
            section, n, demand, capacity = row[1], num(row[2]), num(row[3]), num(row[4])
            self.checks.append(self.add_check(self.member(section), direction, 'E2', kind, demand, capacity, unit, section,
                                              locator, axial_kN=n))

    def bearings(self, index, direction, level, locator):
        for row in self.ref.table(index)[1:]:
            location = row[1].replace(' ', '')
            component = 'B' + re.search(r'(\d+)#', location).group(1)
            self.checks.append(self.add_check(component, direction, level, 'bearing_displacement', num(row[2]), None, 'm',
                                              location, locator, limit_status='not_provided'))
            self.na.append({'component': component, 'direction': direction, 'level': level, 'kind': 'bearing_sliding',
                            'reason': '盆式橡胶支座（GPZ），原报告未列支座抗滑移验算，暂列为不适用，待补充依据',
                            'evidence': SOURCE})


def pilecap(reference, index, check_id, title, demand_row, capacity_row):
    rows = reference.table(index)
    header, body = rows[0], rows[1:-1]
    lookup = {r[0]: r for r in body}
    return {'id': check_id, 'title': title, 'direction': 'transverse', 'header': header, 'rows': body,
            'demand': num(lookup[demand_row][2]), 'capacity': num(lookup[capacity_row][2]), 'evidence': SOURCE}


def build():
    ref = Reference(REFERENCE_76K)
    out = GOLDEN_DIR
    if (out / 'assets').exists():
        shutil.rmtree(out / 'assets')
    (out / 'assets').mkdir(parents=True)
    g = Golden(ref, out)

    figures = {
        'elevation': g.asset('fig-elevation', 65, 'K278+308桥梁立面图（单位：cm）'),
        'pier': g.asset('fig-pier', 69, 'K278+308桥梁桥墩构造图（单位：cm）'),
    }
    waves = [g.asset(f'fig-wave-{n}', 140 + 2 * (n - 1), f'E2 地震波加速度时程-第 {n} 条') for n in range(1, 8)]
    g.wave_spectra()
    g.asset('fig-fe-model', 163, 'K278+308有限元模型')
    g.asset('fig-bearing-layout', 199, '支座垫石布置图')
    modes = [g.asset(f'fig-mode-{n}', index, f'第{cn}阶振型')
             for n, (index, cn) in enumerate(zip((208, 211, 213, 216, 219), '一二三四五'), start=1)]
    g.asset('fig-fiber-pile', 241, '桩基截面纤维模型', nth=0)
    g.asset('fig-fiber-pier', 241, '桥墩截面纤维模型', nth=1)
    g.asset('fig-retrofit-1', 373, '桥墩增大截面设计图（单位：cm）', nth=0)
    g.asset('fig-retrofit-2', 373, '桥墩增大截面设计图（单位：cm）', nth=1)

    # E1 (tables 6.3-1 … 6.3-6)
    g.e1_members(254, 'longitudinal', '原表6.3-1')
    g.e1_members(257, 'longitudinal', '原表6.3-2')
    g.bearings(260, 'longitudinal', 'E1', '原表6.3-3')
    g.e1_members(264, 'transverse', '原表6.3-4')
    g.e1_members(267, 'transverse', '原表6.3-5')
    g.bearings(270, 'transverse', 'E1', '原表6.3-6')
    # E2 (tables 6.3-7 … 6.3-16)
    for index, direction, kind, locator in ((277, 'longitudinal', 'e2_moment', '原表6.3-7'), (280, 'longitudinal', 'shear', '原表6.3-8'),
                                            (283, 'longitudinal', 'e2_moment', '原表6.3-9'), (286, 'longitudinal', 'shear', '原表6.3-10'),
                                            (293, 'transverse', 'e2_moment', '原表6.3-12'), (296, 'transverse', 'shear', '原表6.3-13'),
                                            (299, 'transverse', 'e2_moment', '原表6.3-14'), (302, 'transverse', 'shear', '原表6.3-15')):
        g.e2_members(index, direction, kind, locator)
    g.bearings(289, 'longitudinal', 'E2', '原表6.3-11')
    g.bearings(305, 'transverse', 'E2', '原表6.3-16')
    # Ductility, original state (table 7.1-1)
    row = ref.table(369)[1]
    g.checks.append(g.add_check('P1', 'longitudinal', 'E2', 'hinge_shear', num(row[3]), num(row[4]), 'kN', row[1], '原表7.1-1',
                                axial_kN=num(row[2]), phi=HINGE_PHI))

    # Retrofit (tables 8-1 … 8-4): columns “加固前/加固后”; the original-state values are already in the checks above.
    moment, hinge = ref.table(378)[2], ref.table(384)[2]
    displacement, ratio = ref.table(391)[1], ref.table(404)[1]
    retrofit_checks = [
        g.add_check('P1', 'longitudinal', 'E2', 'e2_moment', num(moment[3]), num(moment[5]), 'kN*m', '1#墩底', '原表8-1',
                    revision=RETROFIT_REVISION),
        g.add_check('P1', 'longitudinal', 'E2', 'hinge_shear', num(hinge[3]), num(hinge[5]), 'kN', '1#墩底', '原表8-2',
                    revision=RETROFIT_REVISION, phi=HINGE_PHI),
        g.add_check('P1', 'longitudinal', 'E2', 'ductility_displacement', num(displacement[2]), num(displacement[3]), 'm', '1#墩底',
                    '原表8-3', revision=RETROFIT_REVISION),
        g.add_check('P1', 'longitudinal', 'E2', 'ductility_reinforcement', num(ratio[3]), num(ratio[2]), 'ratio', '1#墩底', '原表8-4',
                    revision=RETROFIT_REVISION),
    ]

    concrete, rebar = ref.table(116), ref.table(119)
    spectrum_rows = ref.table(130)[1:]
    spectrum = []
    for n, r in enumerate(spectrum_rows):
        spectrum.append({'level': 'E1' if 'E1' in r[1] else 'E2', 'location': r[0] or spectrum_rows[0][0], 'site_class': r[2],
                         'Tg': num(r[3]), 'Ci': num(r[4]), 'Cs': num(r[5]), 'Cd': num(r[6]), 'A': num(r[7]), 'Smax': num(r[8])})
    modal_rows = ref.table(206)[1:]
    detailing1 = ref.table(327)[1:]
    detailing2 = ref.table(330)[1:]
    detailing3 = ref.table(333)[1:]
    topics = {'11.3.2': '墩高限值', '11.3.7': '桥台、桥墩挡块设置', '11.4.3': '限位装置设置', '11.4.9': '下部结构混凝土强度等级'}

    def detailing_rows(rows):
        return [{'clause': r[0], 'requirement': r[1], 'design': r[2], 'satisfied': r[3] == '满足', 'topic': topics.get(r[0], '')}
                for r in rows]

    pier_text = ref.text(68)
    package = {
        'contract_version': '2.0',
        'data_kind': 'reference_reproduction',
        'bridge_id': 'G8511-K278+308',
        'model_revision': REVISION,
        'scenario': 'original',
        'project': {
            'route': 'G8511昆磨高速', 'program': '抗震韧性提升工程', 'stake': 'K278+308', 'stake_line': ref.text(9),
            'short_name': 'K278+308', 'spans_m': [20, 33, 20], 'span_text': ref.text(10), 'bridge_type': ref.text(11),
            'report_title': ref.text(12), 'organization': ref.text(25), 'date': ref.text(26),
            'header_text': 'G8511昆磨高速设计桩号 K278+308  20+33+20 m连续梁桥',
        },
        'overview': {
            'description': ref.text(64),
            'pier_description': pier_text[pier_text.index('该桥墩'):],
            'research_scope': ref.text(72),
            'figures': figures,
        },
        'codes': [re.sub(r'^（\d+）', '', ref.text(i)).rstrip('；;').replace('(', '（') for i in range(76, 89)],
        'seismic': {
            'intensity': 'Ⅶ度', 'pga_g': 0.10, 'site_class': 'Ⅱ类', 'tg_s': 0.45, 'category': 'B类',
            'performance_objectives': [{'category': 'B类', 'e1_use': '可正常使用', 'e1_damage': '结构总体反应在弹性范围，基本无损伤',
                                        'e2_use': '经临时加固后可供维修应急交通使用', 'e2_damage': '不致倒塌或产生严重结构损伤'}],
            'spectrum': spectrum,
            'time_history': {'count': 7, 'duration_s': 40, 'energy_s': 20, 'dt_s': 0.01, 'target': 'E2'},
            'figures': {'wave_spectra': 'fig-wave-spectra', 'waves': waves},
        },
        'materials': {
            'description': ref.text(99).split('由于')[0],
            'old_code_conversion': True,
            'old_code': '《公路钢筋混凝土及预应力混凝土桥涵设计规范》（JTJ 023-85）',
            'concrete_table': {'header': ['项  目'] + concrete[0][1:],
                               'rows': [[re.sub(r'\s+', ' ', r[0]).replace('f_{cu,}', 'f_{cu,k}').replace('Ec（', 'E_{c}（')
                                         .replace('fck', 'f_{ck}').replace('ftk', 'f_{tk}').replace('fcd', 'f_{cd}').replace('ftd', 'f_{td}')]
                                        + r[1:] for r in concrete[1:]]},
            'rebar_intro': ref.text(117).split('，材料参数')[0],
            'rebar_table': {'header': [h.replace('Ep（', 'E_{p}（') for h in rebar[0]], 'rows': rebar[1:]},
        },
        'model': {
            'software': 'SAP 2000 v22', 'nodes': 24, 'elements': 13,
            'figures': {'fe_model': 'fig-fe-model', 'bearing_layout': 'fig-bearing-layout', 'fiber_pile': 'fig-fiber-pile',
                        'fiber_pier': 'fig-fiber-pier'},
            'linear_boundary': {'header': ref.table(172)[0], 'rows': ref.table(172)[1:], 'notes': [ref.text(173)]},
            'foundation': {'springs': {'header': ref.table(179)[0], 'rows': ref.table(179)[1:]}, 'notes': [ref.text(180), ref.text(181)]},
            'bearings': {
                'description': ref.text(183).replace(' ，', '，'),
                'family': '盆式橡胶支座',
                'model_name': 'GPZ',
                'nonlinear_boundary': {'header': ref.table(187)[0], 'rows': ref.table(187)[1:],
                                       'notes': [ref.text(188), ref.text(189), ref.text(190)]},
                'parameters': {'clauses': '第6.2.7条及第10.3.3条', 'mu_d': 0.02, 'post_yield_ratio': 0.0001, 'yield_exponent': 20},
                'types': [{'name': 'GPZ1500DX/SX', 'position': '桥台', 'Fmax_kN': 15.04, 'xy_m': 0.002, 'k_kN_m': 7520.1},
                          {'name': 'GPZ6000GD/SX', 'position': '桥墩', 'Fmax_kN': 91.44, 'xy_m': 0.002, 'k_kN_m': 45722.1}],
            },
        },
        'modal': {
            'modes': [{'n': int(num(r[0])), 'period_s': num(r[1]), 'frequency_hz': num(r[2])} for r in modal_rows],
            'figures': [{'asset': asset_id, 'caption': caption} for asset_id, caption in
                        zip(modes, ('第一阶振型', '第二阶振型', '第三阶振型', '第四阶振型', '第五阶振型'))],
        },
        'analysis': {'software': 'SAP 2000 v22', 'converged': True, 'axial_sign': 'compression_positive',
                     'coordinate_convention': '模型总体坐标轴以顺桥向为 X 轴，横桥向为 Y 轴，竖向为 Z 轴',
                     'methods': {'E1': 'response_spectrum', 'E2': 'nonlinear_time_history'}},
        'scope_review': {'approved': True, 'evidence': SOURCE,
                         'note': '关键截面沿用原报告选取：纵桥向取墩底、横桥向取墩顶，桩基取桩顶'},
        'selection': {'method': '沿用原报告选取的关键截面', 'covered_components': ['P1', 'P2', 'F1', 'F2', 'B0', 'B1', 'B2', 'B3'],
                      'limitations': '原报告未提供同类截面分组与候选截面清单'},
        'components': [
            {'id': 'P1', 'kind': 'pier', 'label': '1#墩', 'directions': ['longitudinal', 'transverse']},
            {'id': 'P2', 'kind': 'pier', 'label': '2#墩', 'directions': ['longitudinal', 'transverse']},
            {'id': 'F1', 'kind': 'pile', 'label': '1#桩', 'parent_pier': 'P1', 'directions': ['longitudinal', 'transverse']},
            {'id': 'F2', 'kind': 'pile', 'label': '2#桩', 'parent_pier': 'P2', 'directions': ['longitudinal', 'transverse']},
            {'id': 'B0', 'kind': 'bearing', 'label': '0#桥台', 'directions': ['longitudinal', 'transverse']},
            {'id': 'B1', 'kind': 'bearing', 'label': '1#桥墩', 'directions': ['longitudinal', 'transverse']},
            {'id': 'B2', 'kind': 'bearing', 'label': '2#桥墩', 'directions': ['longitudinal', 'transverse']},
            {'id': 'B3', 'kind': 'bearing', 'label': '3#桥台', 'directions': ['longitudinal', 'transverse']},
        ],
        'actions': g.actions,
        'checks': g.checks,
        'not_applicable': g.na,
        'detailing': {
            'level1': {'rows': [{'location': r[0].replace(' ', ''), 'design_cm': num(r[1]), 'required_cm': num(r[2])} for r in detailing1]},
            'level2': detailing_rows(detailing2),
            'level3': detailing_rows(detailing3),
        },
        'pilecap': {'checks': [
            pilecap(ref, 308, 'strut', '承台斜压杆承载力验算', 'γ0C1d', 'tbsfce,d'),
            pilecap(ref, 311, 'tie', '承台拉杆承载力验算', 'γ0T1d', 'fsdAs'),
            pilecap(ref, 314, 'punching', '承台冲切承载力验算', 'γ0Fld', '公式(8.5.5-1)右侧计算式'),
        ]},
        'retrofit': {
            'model_revision': RETROFIT_REVISION,
            'description': ref.text(372),
            'scope_note': '加固后复核范围为E2纵桥向1#墩底截面',
            'figure': {'assets': ['fig-retrofit-1', 'fig-retrofit-2'], 'caption': '桥墩增大截面设计图（单位：cm）'},
            'checks': retrofit_checks,
        },
        'assets': g.assets,
        'sources': {SOURCE: {'kind': 'external', 'title': 'G8511 76K278+308 (20m+33m+20m) 抗震设计验算报告（原件）',
                             'sha256': file_hash(REFERENCE_76K),
                             'note': '位于 templates/reference；数值由 tools/extract_golden.py 按原表逐项抽取'}},
    }
    for cap in package['pilecap']['checks']:
        cap['locator'] = {'strut': '原表6.3-17', 'tie': '原表6.3-18', 'punching': '原表6.3-19'}[cap['id']]
    (out / 'handoff.json').write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"金标准：{out / 'handoff.json'}")
    print(f"构件 {len(package['components'])}，成组内力 {len(g.actions)}，验算记录 {len(g.checks)}（加固 {len(retrofit_checks)}），"
          f"不适用声明 {len(g.na)}，图件 {len(g.assets)}")
    return package


if __name__ == '__main__':
    build()
