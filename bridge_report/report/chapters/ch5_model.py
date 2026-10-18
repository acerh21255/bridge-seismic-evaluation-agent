"""Chapter 5: structural dynamic model and dynamic properties."""
from .. import omml
from ..library import figure_path
from ..model import Run
from .common import FALLBACK, fmt, ref

ELEMENT_MODELING = ('本桥有限元建模过程中，主梁及桥墩均采用空间梁单元模拟，以准确反映其受力与变形特征；承台近似按刚体考虑，质量堆聚于承台质心处，'
                    '墩底节点与承台中心节点、桩顶中心节点之间采用主从约束关系连接。主梁恒载通过赋予截面面积及材料密度施加；桩土相互作用采用“m”法模拟。')
ELEMENT_TYPES = '在有限元模型中，主梁、盖梁及桥墩采用梁单元（Frame单元）模拟，支座采用连接单元（Link单元）模拟，桩-土相互作用则通过等代土弹簧进行模拟。'
COMBINATION = 'E1地震作用按照顺桥向和横桥向E1地震作用效应和永久作用效应组合，同理，E2地震作用按照顺桥向和横桥向E2地震作用效应和永久作用效应组合。'
MODE_NAMES = '一二三四五六七八九十'


def math_symbol(base, sub):
    return Run(math=omml.math(omml.sub(base, sub)))


def stiffness_equation(bearing):
    return omml.math('k=', omml.frac(omml.sub('F', omml.text('max')), omml.sub('x', 'y')), '=',
                     omml.frac(fmt(bearing['Fmax_kN']), fmt(bearing['xy_m'])), '=', fmt(bearing['k_kN_m']), omml.text(' kN/m'))


def pier_range(springs):
    labels = [row[0] for row in springs.get('rows', []) if row]
    if not labels:
        return '各桥墩'
    return labels[0] if len(labels) == 1 else f'{labels[0]}～{labels[-1]}'


def build(b):
    short = b.short
    figures = b.get('model.figures', {})
    b.h(1, '结构动力模型及动力特性')
    b.h(2, '线性结构动力模型')
    b.h(3, '主梁、桥墩、桩基模拟')
    b.p(b.get('model.element_modeling', ELEMENT_MODELING))
    b.h(3, '结构三维动力分析模型')
    software = b.get('model.software', FALLBACK, '建模软件')
    b.p(f'使用 {software}有限元分析软件建立{short}三维结构空间动力分析模型，如', ref('fig-fe-model'),
        f"所示。全桥共 {fmt(b.get('model.nodes', None, '模型节点数'))} 个节点，{fmt(b.get('model.elements', None, '模型单元数'))} 个单元，"
        '模型总体坐标轴以顺桥向为 X 轴，横桥向为 Y 轴，竖向为 Z 轴，各单元局部坐标系以单元轴向为1轴（从I节点指向J节点），'
        '3轴保持水平且垂直于1轴，2轴按右手螺旋准则确定。')
    b.p(ELEMENT_TYPES)
    b.figure('fig-fe-model', asset_id=figures.get('fe_model'), what='有限元模型图', default=f'{short}有限元模型')

    b.h(3, '支承连接条件的模拟')
    b.p(f'{short}动力约束体系如', ref('tab-linear-boundary'), '所示。')
    linear = b.get('model.linear_boundary', None, '有限元模型墩-梁连接关系')
    if linear:
        b.data_table('tab-linear-boundary', '有限元模型墩-梁连接关系', linear, notes=linear.get('notes', []))
    else:
        b.data_table('tab-linear-boundary', '有限元模型墩-梁连接关系', {'header': ['位置'], 'rows': [[FALLBACK]]})

    b.h(3, '桩基础的模拟')
    if b.get('model.foundation.method') == 'distributed_m':
        b.p('桩土相互作用按 m 法采用沿桩身分布的土弹簧模拟，原报告给出的土层参数与弹簧刚度见下表。')
        b.data_table('tab-springs', '桩土弹簧参数', b.get('model.foundation.springs'), notes=b.get('model.foundation.notes', []))
    else:
        b.figure('fig-six-spring', '桩基础的六弹簧模型', image=figure_path('six_spring'), width_cm=14.3)
        springs = b.get('model.foundation.springs', None, '六弹簧刚度表') or {'header': ['墩号'], 'rows': [[FALLBACK]]}
        b.p('桥梁地震反应分析中，群桩基础的常用处理方法是在承台底加六个方向的弹簧来模拟桩基础的作用（见', ref('fig-six-spring'),
            '），并由承台底部内力按静力方法（m法）反推单桩最不利受力。弹簧刚度根据土层状况和桩的布置形式按静力等效原则确定，由土性资料确定m值，'
            f'这种处理方法在低桩承台桩基础中广泛采用。采用六弹簧模型模拟{pier_range(springs)}群桩基础的影响，各桩基础的弹簧刚度见', ref('tab-springs'), '。')
        b.data_table('tab-springs', '各群桩基础的六弹簧刚度', springs, notes=b.get('model.foundation.notes', []))

    bearings = b.get('model.bearings', {}, '支座模拟资料')
    b.h(2, '支座模拟')
    b.p(bearings.get('description', FALLBACK))
    b.h(3, '非线性模型中边界连接条件的模拟')
    family = bearings.get('family', '支座')
    b.p(f'在进行非线性时程分析时，考虑{family}的减震作用，非线性模型墩-梁连接关系见', ref('tab-nonlinear-boundary'), '。')
    nonlinear = bearings.get('nonlinear_boundary') or {'header': ['位置'], 'rows': [[FALLBACK]]}
    b.data_table('tab-nonlinear-boundary', '非线性模型中墩-梁连接关系', nonlinear, notes=nonlinear.get('notes', []))
    b.h(3, '支座参数')
    parameters = bearings.get('parameters', {})
    types = bearings.get('types', [])
    if types:
        first = types[0]
        b.p(f"根据《公路桥梁抗震设计规范》（JTG/T 2231-01—2020）{parameters.get('clauses', '')}的规定，{family}{first['name']}"
            '采用双线性理想弹塑性恢复力模型进行模拟（如', ref('fig-bearing-model'), '所示）。在线性分析阶段，可忽略支座摩擦效应，其有效刚度取为0。'
            '在非线性分析阶段，支座滑动摩擦系数取', math_symbol('μ', 'd'), f"={fmt(parameters.get('mu_d'))}，临界滑动摩擦力（即屈服强度）"
            '根据恒载支反力计算，取', math_symbol('F', omml.text('max')), f"={fmt(first['Fmax_kN'])} kN；屈服位移取", math_symbol('x', 'y'),
            f"={fmt(first['xy_m'])} m，屈服后刚度比取{fmt(parameters.get('post_yield_ratio'))}，屈服指数取{fmt(parameters.get('yield_exponent'))}，"
            '初始刚度取为：')
        b.equation(stiffness_equation(first))
        for other in types[1:]:
            b.p(f"对于{other.get('position', '')}支座{other['name']}，初始刚度取：")
            b.equation(stiffness_equation(other))
    else:
        b.missing.append('支座参数')
        b.p('（支座参数资料未提供）')
    b.figure('fig-bearing-model', f"{bearings.get('model_name', '')}支座的双线性模型", image=figure_path('bearing_bilinear'), width_cm=8.3)
    b.figure('fig-bearing-layout', asset_id=figures.get('bearing_layout'), what='支座垫石布置图', default='支座垫石布置图')
    b.p(COMBINATION)

    b.h(2, '动力特性')
    modes = b.get('modal.modes', [], '结构动力特性')
    mode_figures = b.get('modal.figures', [])
    if mode_figures:
        b.p(f'结构前{len(modes)}阶自振周期与频率见', ref('tab-modal'), '，', ref('fig-mode-1'), '～', ref(f'fig-mode-{len(mode_figures)}'),
            '给出了结构典型振型图。')
    else:
        b.p(f'结构前{len(modes)}阶自振周期与频率见', ref('tab-modal'), '。')
    rows = [[str(m['n']), fmt(m['period_s'], 3), fmt(m['frequency_hz'], 3)] for m in modes] or [[FALLBACK, '', '']]
    b.data_table('tab-modal', f'{short}动力特性', {'header': ['振型阶数', '周 期 (s)', '频 率 (Hz)'], 'rows': rows})
    for n, entry in enumerate(mode_figures, start=1):
        default = f'第{MODE_NAMES[n - 1]}阶振型' if n <= len(MODE_NAMES) else f'第{n}阶振型'
        b.figure(f'fig-mode-{n}', entry.get('caption'), asset_id=entry.get('asset'), what=f'第{n}阶振型图', default=default)
