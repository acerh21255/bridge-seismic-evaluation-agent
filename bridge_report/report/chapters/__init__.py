"""Assemble the report document from a handoff package and its judgement result."""
from ...contract.package import Package
from ..model import ReportDoc, finalize
from . import (ch1_overview, ch2_codes, ch3_design, ch4_seismic, ch5_model, ch6_checks, ch7_ductility, ch8_retrofit,
               ch9_conclusion, notice)
from .common import Builder

CHAPTERS = (ch1_overview, ch2_codes, ch3_design, ch4_seismic, ch5_model, ch6_checks, ch7_ductility, ch8_retrofit, ch9_conclusion)
COVER_NOTES = {
    'reference_reproduction': '注：本报告据原报告数据复现，用于格式与流程验证，非工程签发。',
    'synthetic_variant': '注：演示变体（{title}），数据经人为修改，非实桥结论。',
}


def cover_meta(data, result):
    data = data if isinstance(data, dict) else {}
    project = data.get('project') if isinstance(data.get('project'), dict) else {}
    route = project.get('route') or data.get('bridge_id') or '未命名桥梁'
    first = f"{route}（{project['program']}）" if project.get('program') else route
    stake = project.get('stake', '')
    lines = [first, project.get('stake_line') or (f'设计桩号 {stake}' if stake else ''), project.get('span_text', ''),
             project.get('bridge_type', ''), project.get('report_title') or '抗震验算分析报告']
    kind = data.get('data_kind')
    note = COVER_NOTES.get(kind, '')
    if note:
        note = note.format(title=(data.get('variant') or {}).get('title', '修改数据'))
    if not result.get('evaluated'):
        note = ('注：交接资料未通过合同检查，本文件为补正通知，未开展抗震验算。' + (' ' + note if note else ''))
    return {
        'cover_lines': [line for line in lines if line],
        'organization': project.get('organization') or '土木工程防灾减灾全国重点实验室',
        'date': project.get('date', ''),
        'cover_note': note,
        'header_text': project.get('header_text') or f'{route} {stake} {project.get("span_text", "")}'.strip(),
        'title': f"{route} {stake} {project.get('report_title') or '抗震验算分析报告'}".strip(),
        'subject': '桥梁抗震验算分析报告',
        'keywords': f"{data.get('bridge_id', '')}; {data.get('model_revision', '')}; {result.get('status', '')}",
        'data_kind': kind,
        'bridge_id': data.get('bridge_id'),
        'status': result.get('status'),
    }


def build_report(package, result, workdir):
    if not isinstance(package, Package):
        package = Package(package if isinstance(package, dict) else {})
    builder = Builder(package, result, workdir)
    if result.get('evaluated'):
        for chapter in CHAPTERS:
            chapter.build(builder)
    else:
        notice.build(builder)
    meta = cover_meta(package.data, result)
    meta['missing'] = list(dict.fromkeys(builder.missing))
    return finalize(ReportDoc(meta=meta, blocks=builder.blocks))
