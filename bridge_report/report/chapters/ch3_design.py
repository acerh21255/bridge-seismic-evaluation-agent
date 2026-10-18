"""Chapter 3: design criteria and material parameters."""
from .common import FALLBACK, fmt, ref


def build(b):
    b.h(1, '设计标准及参数')
    b.h(2, '地震作用')
    pga = b.get('seismic.pga_g', None, '设计基本地震动峰值加速度')
    tg = b.get('seismic.tg_s', None, '场地特征周期')
    b.p(f"（1）桥址区抗震设防烈度：{b.get('seismic.intensity', FALLBACK, '抗震设防烈度')}；")
    b.p(f"（2）设计基本地震动峰值加速度：{fmt(pga, 2) + 'g' if pga is not None else FALLBACK}；")
    b.p(f"（3）场地类别：{b.get('seismic.site_class', FALLBACK, '场地类别')}；")
    b.p(f"（4）场地特征周期：{fmt(tg, 2) + 's' if tg is not None else FALLBACK}。")

    b.h(2, '材料参数')
    description = b.get('materials.description', FALLBACK, '材料说明')
    conversion = b.get('materials.old_code_conversion', False)
    if conversion:
        old_code = b.get('materials.old_code', '原设计规范')
        b.p(description, f'由于该桥梁的原设计文件依据的是{old_code}，新老规范混凝土强度等级（标号）基本定义存在差异，需要进行换算。')
        b.fragment('materials_conversion')
        b.p('各材料强度换算后的参数见', ref('tab-concrete'), '。')
    else:
        b.p(description, '混凝土材料参数见', ref('tab-concrete'), '。')
    concrete = b.get('materials.concrete_table', None, '混凝土力学指标表')
    b.data_table('tab-concrete', '混凝土力学指标表', concrete or {'header': ['项目'], 'rows': [['（资料未提供）']]})
    rebar_intro = b.get('materials.rebar_intro', '钢筋混凝土构件的普通钢筋', '钢筋说明')
    b.p(f'{rebar_intro}，材料参数见', ref('tab-rebar'), '。')
    rebar = b.get('materials.rebar_table', None, '普通钢筋力学指标表')
    b.data_table('tab-rebar', '普通钢筋力学指标表', rebar or {'header': ['钢筋种类'], 'rows': [['（资料未提供）']]})
