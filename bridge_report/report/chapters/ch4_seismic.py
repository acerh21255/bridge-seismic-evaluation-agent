"""Chapter 4: seismic fortification targets, performance objectives and ground motion input."""
from ..charts import design_spectrum_png
from ..model import Table
from .common import FALLBACK, cell, fmt, ref

PRINCIPLE = ('本桥抗震验算遵循两阶段设计、两水准设防原则。在E1地震作用下，地震作用效应与永久作用效应组合后，按现行《公路钢筋混凝土及预应力混凝土桥涵设计规范》'
             '（JTG 3362-2018）有关偏心受压构件的规定进行强度验算，结构总体反应保持在弹性范围，基本无损伤；在E2地震作用下，地震作用效应与永久作用效应组合后，'
             '按能力保护原则进行验算，墩柱作为延性构件允许进入塑性，采用等效屈服弯矩进行验算，同时按能力保护原则验算墩柱抗剪强度、基础及盖梁强度，'
             '确保结构不致倒塌或产生严重结构损伤。')


def objectives_table(b):
    rows = b.get('seismic.performance_objectives', [], '抗震设防标准和性能目标')
    header = [
        [cell('桥梁抗震设防类别', bold=True, vmerge='restart'), cell('设防目标', bold=True, span=4)],
        [cell('', vmerge='continue'), cell('E1地震作用', bold=True, span=2), cell('E2地震作用', bold=True, span=2)],
        [cell('', vmerge='continue')] + [cell(t, bold=True) for t in ('震后使用要求', '损伤状态', '震后使用要求', '损伤状态')],
    ]
    body = [[cell(r.get(k, '')) for k in ('category', 'e1_use', 'e1_damage', 'e2_use', 'e2_damage')] for r in rows] or \
           [[cell(FALLBACK)] + [cell('') for _ in range(4)]]
    b.add(Table('tab-objectives', '抗震设防标准和性能目标', header, body, kind='data', widths=[1413, 1843, 2126, 1877, 1735]))


def spectrum_table(b, spectra):
    header = ['位置', '设防类别', '场地类型', 'T_{g}(s)', 'C_{i}', 'C_{s}', 'C_{d}', 'A(g)', 'S_{max}(g)']
    rows = []
    for n, s in enumerate(spectra):
        location = s.get('location', '地表面')
        first = location if n == 0 or location != spectra[n - 1].get('location', '地表面') else ''
        rows.append([first, f"{s['level']}地震作用", s.get('site_class', ''), fmt(s['Tg'], 2), fmt(s['Ci']), fmt(s['Cs']), fmt(s['Cd']),
                     fmt(s['A'], 2), fmt(s['Smax'], 4)])
    b.data_table('tab-spectrum', '桥梁工程场地地表水平向加速度地震动参数（阻尼比5%）', {'header': header, 'rows': rows},
                 widths=[975, 1472, 850, 1048, 899, 831, 850, 1011, 1229], merge_first=True)


def build(b):
    b.h(1, '抗震设防标准、性能目标与地震动输入')
    b.h(2, '抗震设防标准、性能目标')
    category = b.get('seismic.category', FALLBACK, '抗震设防类别')
    b.p(f'参考《公路桥梁抗震设计规范》（JTG/T 2231-01—2020），本桥属于抗震设防类别{category}桥梁，其抗震设防目标采用E1地震作用和E2地震作用'
        '两水准地震动进行抗震设防。抗震设防目标应符合', ref('tab-objectives'), '的规定。')
    objectives_table(b)
    b.p(PRINCIPLE)

    b.h(2, '地震动（反应谱与加速度时程）输入')
    spectra = b.get('seismic.spectrum', [], '反应谱参数')
    history = b.get('seismic.time_history', {})
    count = history.get('count')
    time_history = b.get('analysis.methods.E2') == 'nonlinear_time_history' and count
    if time_history:
        b.p('反应谱曲线见', ref('fig-spectrum'), f'。本桥为抗震设防类别{category}桥梁，根据《公路桥梁抗震设计规范》（JTG/T 2231-01—2020）的要求，'
            f"进行E2地震作用下非线性时程分析。为考虑地震动的随机性，本次分析按照E2反应谱为目标谱，生成了{count}条人工地震加速度时程波。"
            f"生成的地震波持续时间为{fmt(history.get('duration_s'))}s，能量集中在前{fmt(history.get('energy_s'))}s，"
            f"计算步长为{fmt(history.get('dt_s'))} s，满足积分精度要求。")
    else:
        b.p('反应谱曲线见', ref('fig-spectrum'), f'。本桥为抗震设防类别{category}桥梁，结构无需开展非线性时程分析，E1、E2地震作用均采用反应谱法进行分析。')
    spectrum_table(b, spectra)
    images, subcaptions = [], []
    b.workdir.mkdir(parents=True, exist_ok=True)
    for n, s in enumerate(spectra):
        images.append(design_spectrum_png(s, b.workdir / f"spectrum-{s['level']}.png"))
        subcaptions.append(f"({chr(97 + n)}) {s['level']}地震水平向加速度反应谱")
    b.figure('fig-spectrum', '加速度反应谱', image=images or None, width_cm=13.25, subcaptions=subcaptions)
    if not time_history:
        return
    b.p(f'在后续非线性的计算中，取{count}条时程波计算结果的平均值作为E2地震作用下的能力验算依据，用于验算桥墩等构件的内力及变形能力。')
    figures = b.get('seismic.figures', {})
    b.figure('fig-wave-spectra', asset_id=figures.get('wave_spectra'), what='地震波加速度反应谱与规范对比图',
             default='各条地震波的加速度反应谱与规范对比')
    waves = figures.get('waves') or [None] * count
    for n, asset_id in enumerate(waves, start=1):
        b.figure(f'fig-wave-{n}', asset_id=asset_id, what=f'E2 地震波加速度时程第 {n} 条',
                 default=f'E2 地震波加速度时程-第 {n} 条')
