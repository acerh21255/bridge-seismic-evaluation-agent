"""Chapter 1: project overview."""
from .common import FALLBACK, ref


def build(b):
    b.h(1, '工程概况')
    b.h(2, '桥梁概况')
    b.p(b.get('overview.description', FALLBACK, '桥梁概况文字'))
    figures = b.get('overview.figures', {})
    b.figure('fig-elevation', asset_id=figures.get('elevation'), what='桥梁立面图',
             default=f'{b.short}桥梁立面图（单位：cm）')
    pier_text = b.get('overview.pier_description', '', '桥墩构造说明')
    b.p(ref('fig-pier'), f'为{b.short}桥梁桥墩构造图，展示了桥墩的详细尺寸及构造形式。', pier_text)
    b.figure('fig-pier', asset_id=figures.get('pier'), what='桥墩构造图', default=f'{b.short}桥梁桥墩构造图（单位：cm）')
    b.h(2, '报告主要研究内容')
    default = (f"本报告主要针对{b.get('project.route', '')}{b.get('project.stake', '')}桥梁进行抗震性能研究，主要研究内容包括："
               '建立大桥动力分析模型，计算结构的动力特性，完成桥梁地震作用下的响应分析。')
    b.p(b.get('overview.research_scope', default))

    if b.get('source_notes', []):
        b.h(2, '原始资料复核说明')
        for note in b.get('source_notes', []):
            b.p(note)
