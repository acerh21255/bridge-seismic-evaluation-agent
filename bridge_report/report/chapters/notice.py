"""Correction notice issued when the handoff package fails contract checks (no seismic judgement made)."""
from ..model import Table
from .common import cell, ref


def build(b):
    data = b.data if isinstance(b.data, dict) else {}
    bridge = data.get('bridge_id') or '（未提供）'
    revision = data.get('model_revision') or '（未提供）'
    b.h(1, '交接资料审查意见')
    b.p(f'第三步交接包（桥梁编号 {bridge}，模型版本 {revision}）未通过第四步的数据合同与证据检查，判定引擎未开展抗震验算。'
        '本文件仅列出需补正的问题，不构成任何验算结论，问题清单见', ref('tab-issues'), '。')
    issues = b.result.get('issues') or ['交接包结构无效']
    header = [[cell('序号', bold=True), cell('问题说明', bold=True)]]
    rows = [[cell(str(n)), cell(issue)] for n, issue in enumerate(issues, start=1)]
    b.add(Table('tab-issues', '交接资料问题清单', header, rows, widths=[900, 8100]))
    b.h(1, '后续处理')
    b.p('请第三步按《第三步数据交接说明》（合同 2.0）逐项补正上述问题，并以新的交接包重新提交；补正前不能形成抗震验算结论。')
