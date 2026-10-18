// Result views: verdict, advisory memo, diagnosis, report preview, deliverables and the detail tabs.
import { $, DATA_KIND, STATUS, chip, clear, fmtBytes, fmtDuration, fmtNumber, fmtUnit, h } from './dom.js';
import { icon } from './icons.js';
import { renderMarkdown } from './markdown.js';

const GATE_TITLES = {
  e1: 'E1 验算', e2_pier: 'E2 桥墩屈服', e2_pile: '桩基能力保护', shear: '墩桩抗剪', bearing: '支座与专项', pilecap: '承台验算',
  detailing: '构造措施', ductility: '延性验算', retrofit: '加固复核',
};
const FILE_INFO = {
  'report.docx': ['DOCX', 'docx', 'Word 报告（实验室模板）'],
  'report.pdf': ['PDF', 'pdf', 'Word 导出的 PDF'],
  'report.html': ['HTML', 'html', '网页预览版'],
  'advice.md': ['MD', 'md', '建议书（Markdown）'],
  'diagnosis.json': ['JSON', 'json', '薄弱环节诊断（机器可读）'],
  'result.json': ['JSON', 'json', '判定结果（机器可读）'],
  'qa.json': ['JSON', 'json', '报告自检意见'],
  'input.json': ['JSON', 'json', '交接包快照'],
  'receipt.json': ['JSON', 'json', '交付回执（含 SHA256）'],
};
const FILTERS = [['all', '全部'], ['FAIL', '不满足'], ['PLASTIC', '进入塑性'], ['BLOCKED', '待补正'], ['SKIPPED', '未开展']];

const VERDICT_ICON = { PASS: 'check', FAIL: 'x', BLOCKED: 'alert' };

export function renderVerdict(run) {
  $('agentExplanation').textContent = run?.agent_message
    || (run && ['queued', 'running'].includes(run.status) ? 'Agent 正在调用工具，完成后在此显示回复。' : '运行完成后显示 Agent 的最终回复。');
  const node = clear($('verdict'));
  const result = run && run.result;
  if (!result) {
    node.className = 'verdict empty';
    const waiting = run && ['queued', 'running'].includes(run.status);
    node.append(h('div', { class: 'verdict-seal' }, h('span', { class: 'seal-label', text: '报告结论' }),
      h('span', { class: 'big', text: waiting ? '判定中' : (run && run.status === 'failed' ? '执行失败' : '尚未生成') })),
      h('div', { class: 'verdict-main' }, h('p', { class: 'verdict-reason',
        text: run && run.error ? run.error : '在“任务与资料”选择场景并生成。结论由确定性判定引擎给出，Agent 不改写数值。' })));
    return;
  }
  node.className = `verdict ${result.status}`;
  const final = (run.items || []).filter((i) => i.final && i.status !== 'NA');
  const count = (s) => final.filter((i) => i.status === s).length;
  const kind = DATA_KIND[run.input_summary?.data_kind]?.[0];
  const fact = (cls, value, label) => h('div', { class: `fact ${cls}` }, h('b', { text: value }), h('span', { text: label }));
  node.append(
    h('div', { class: 'verdict-seal' }, h('span', { class: 'seal-label', text: '报告结论' }),
      h('span', { class: 'big' }, icon(VERDICT_ICON[result.status] || 'alert'), STATUS[result.status])),
    h('div', { class: 'verdict-main' },
      h('p', { class: 'verdict-bridge', text: run.input_summary?.bridge_name || '' }),
      h('p', { class: 'verdict-reason', text: result.reason }),
      h('p', { class: 'verdict-note', text: `任务完成不等于验算通过${kind ? ` · 数据性质：${kind}` : ''} · engineering_release = false` })),
    h('div', { class: 'verdict-facts' },
      fact('pass', count('PASS'), '满足'), fact('fail', count('FAIL'), '不满足'),
      fact('plastic', count('PLASTIC'), '进入塑性'), fact('blocked', count('BLOCKED') + count('SKIPPED'), '待补正 / 未开展')));
}

export function renderAdvice(run) {
  const node = clear($('advice'));
  const meta = clear($('adviceMeta'));
  const advice = run && run.advice;
  if (!advice) {
    const waiting = run && ['queued', 'running'].includes(run.status);
    node.append(h('div', { class: 'placeholder' },
      h('p', { class: 'placeholder-title', text: waiting ? 'Agent 正在撰写建议书' : '建议书会出现在这里' }),
      h('p', { text: waiting ? '判定、诊断和报告渲染完成后，Agent 按任务说明写出建议，并核对每个数值的出处。'
        : '每次运行都会得到一份针对任务的建议书：薄弱环节、加固措施比选、下一步工作。先在“任务与资料”选一个应用场景。' })));
    return;
  }
  const file = (run.files || []).find((f) => f.name === 'advice.md');
  meta.append(h('span', { class: `source-tag ${advice.source}`, text: advice.source === 'model' ? `${run.model_config?.model || '大模型'} 撰写` : '规则库生成' }));
  meta.append(advice.ungrounded?.length ? chip('BLOCKED', `${advice.ungrounded.length} 个数值待核对`) : chip('PASS', '数值均有出处'));
  if (file) meta.append(h('a', { class: 'link-btn', href: file.url, download: 'advice.md' }, icon('download'), '下载'));
  node.append(h('div', { class: 'prose' }, renderMarkdown(advice.markdown)));
}

const SEVERITY_CLASS = { critical: 'FAIL', major: 'BLOCKED', watch: 'PLASTIC', data: 'SKIPPED' };

export function renderDiagnosis(run) {
  const node = clear($('diagnosis'));
  const diag = run && run.diagnosis;
  $('diagnosisHint').textContent = diag ? `${diag.modes.length} 类 · 后续 ${diag.next_steps.length} 步` : '';
  if (!diag) {
    node.append(h('div', { class: 'placeholder', text: '判定完成后按失效模式归类薄弱环节，并列出下一步工作。' }));
    return;
  }
  if (!diag.modes.length) node.append(h('p', { class: 'diag-empty', text: '未识别到不满足、进入塑性或待补正的项目。' }));
  node.append(h('ul', { class: 'diag-list' }, diag.modes.map((mode) => {
    const exceed = mode.items[0]?.exceed_pct;
    return h('li', { class: `diag-item ${SEVERITY_CLASS[mode.severity]}` },
      h('div', { class: 'diag-head' }, chip(SEVERITY_CLASS[mode.severity], mode.severity_label), h('strong', { text: mode.title })),
      h('p', { class: 'diag-where', text: mode.items.slice(0, 3).map((i) => i.label).join('；') + (mode.items.length > 3 ? ` 等 ${mode.items.length} 项` : '') }),
      exceed != null ? h('div', { class: 'exceed', title: '最不利项需求超出能力的比例' },
        h('span', { class: 'exceed-bar' }, h('i', { style: `width:${Math.min(exceed, 100)}%` })), h('span', { text: `需求超出 ${exceed}%` })) : null);
  })));
  node.append(h('h3', { class: 'diag-sub', text: '下一步' }), h('ol', { class: 'next-steps' }, diag.next_steps.map((step) =>
    h('li', {}, h('span', { class: 'owner', text: step.owner }), h('span', { text: step.action })))));
}

export function renderPreview(run, events, onOpenPage) {
  const node = clear($('preview'));
  const hint = $('pageHint');
  hint.textContent = '';
  if (!run) {
    node.append(h('div', { class: 'placeholder', text: '生成后在此逐页预览 Word 报告' }));
    return;
  }
  const rendering = (events || []).filter((e) => e.tool === 'render_documents');
  const inProgress = rendering.length && rendering[rendering.length - 1].type === 'tool_call';
  if (inProgress) {
    const started = new Date(rendering[rendering.length - 1].at).getTime();
    node.append(h('div', { class: 'rendering' }, h('span', { class: 'spin' }),
      h('span', { text: `正在写出 DOCX，并由 Word 刷新目录与页码、导出 PDF（${fmtDuration(Date.now() - started)}）` })));
    return;
  }
  if (run.status !== 'completed') {
    node.append(h('div', { class: 'placeholder', text: run.status === 'failed' ? '任务未完成，未生成报告' : '等待撰写与渲染…' }));
    return;
  }
  const pages = run.pages || [];
  const html = (run.files || []).find((f) => f.name === 'report.html');
  const pdf = (run.files || []).find((f) => f.name === 'report.pdf');
  if (pages.length) {
    hint.textContent = `共 ${pages.length} 页`;
    node.append(h('div', { class: 'pages' }, pages.map((url, index) => h('button', {
      type: 'button', class: 'page-thumb', title: `第 ${index + 1} 页`, onclick: () => onOpenPage(pages, index),
    }, h('img', { src: url, alt: `第 ${index + 1} 页`, loading: 'lazy' }), h('span', { text: index + 1 })))));
  } else {
    node.append(h('div', { class: 'placeholder', text: run.rendering?.message || '未生成页面预览' }));
  }
  const actions = h('div', { class: 'preview-actions' });
  if (pdf) actions.append(h('a', { class: 'btn-ghost', href: pdf.url, target: '_blank', rel: 'noopener', text: '打开 PDF' }));
  if (html) actions.append(h('a', { class: 'btn-ghost', href: html.url, target: '_blank', rel: 'noopener', text: '网页版预览' }));
  if (actions.childNodes.length) node.append(actions);
}

export function renderFiles(run) {
  const node = clear($('files'));
  const files = (run && run.files) || [];
  if (!files.length) {
    node.append(h('li', { class: 'placeholder', text: run && run.status === 'failed' ? '任务未完成，无交付文件' : '报告生成后可下载 Word、PDF 与数据文件' }));
    return;
  }
  for (const file of files) {
    const [label, cls, desc] = FILE_INFO[file.name] || [file.name.split('.').pop().toUpperCase(), 'json', ''];
    node.append(h('li', {}, h('a', { class: 'file', href: file.url, target: ['report.pdf', 'report.html'].includes(file.name) ? '_blank' : null, rel: 'noopener' },
      h('span', { class: `file-ico ${cls}`, text: label }),
      h('span', {}, h('div', { class: 'file-name', text: file.name }), h('div', { class: 'file-desc', text: desc })),
      h('span', { class: 'file-size', text: fmtBytes(file.bytes) }))));
  }
}

function ratioCell(item) {
  if (item.ratio === null || item.ratio === undefined) return h('td', { class: 'num', text: '—' });
  const width = Math.min(item.ratio / 2, 1) * 100;
  return h('td', { class: 'num' }, h('span', { class: 'ratio' }, fmtNumber(item.ratio, 3),
    h('span', { class: 'ratio-bar', title: '中线为能力/需求 = 1' }, h('i', { class: item.ratio < 1 ? 'low' : '', style: `width:${width}%` }))));
}

function valueText(value, unit) {
  const text = fmtNumber(value);
  const u = fmtUnit(unit);
  return text === '—' || !u ? text : `${text} ${u}`;
}

export function renderMatrix(run, filter, onFilter) {
  const node = clear($('panel-matrix'));
  const items = (run && run.items) || [];
  if (!items.length) {
    node.append(h('div', { class: 'placeholder', text: run && run.result && !run.result.evaluated
      ? '交接包未通过合同检查，未形成验算明细，见“待补正与自检”' : '判定完成后显示逐项验算：需求、能力、能需比与结论' }));
    return;
  }
  const counted = (s) => items.filter((i) => i.final && i.status === s).length;
  node.append(h('div', { class: 'filters' }, FILTERS.map(([id, label]) => h('button', {
    type: 'button', class: 'filter', 'aria-pressed': String(filter === id), onclick: () => onFilter(id),
  }, `${label} ${id === 'all' ? items.length : counted(id)}`))));
  const rows = [];
  let lastGate = null;
  for (const item of items) {
    if (filter !== 'all' && !(item.final && item.status === filter)) continue;
    if (item.gate !== lastGate) {
      rows.push(h('tr', { class: 'group' }, h('td', { colspan: 7, text: GATE_TITLES[item.gate] || item.gate })));
      lastGate = item.gate;
    }
    const before = item.before ? ` · 加固前 ${STATUS[item.before.status] || item.before.status}` : '';
    rows.push(h('tr', { class: item.final ? '' : 'superseded', title: item.reason + (item.final ? '' : '（已被加固复核替代）') },
      h('td', {}, item.section_label, item.stage === 'retrofit' ? h('span', { class: 'stage-tag', text: '加固后' }) : null),
      h('td', { text: item.direction_label || '—' }),
      h('td', { text: `${item.level ? `${item.level} ` : ''}${item.kind_label}` }),
      h('td', { class: 'num', text: valueText(item.demand, item.unit) }),
      h('td', { class: 'num', text: valueText(item.capacity, item.unit) + (item.provisional ? '*' : '') }),
      ratioCell(item),
      h('td', {}, chip(item.status, item.verdict), before ? h('span', { class: 'before-note', text: before }) : null)));
  }
  if (!rows.length) rows.push(h('tr', {}, h('td', { colspan: 7, class: 'placeholder', text: '没有符合筛选条件的验算项' })));
  node.append(h('div', { class: 'table-wrap' }, h('table', { class: 'grid' },
    h('thead', {}, h('tr', {}, ['截面 / 项目', '方向', '验算内容', '需求', '能力', '能力/需求', '结论'].map((t) => h('th', { text: t })))),
    h('tbody', {}, rows))));
  if (items.some((i) => i.provisional)) {
    node.append(h('p', { class: 'table-note', text: '* 支座未提供规范位移限值，暂按 0.0375 m 评定，待补充规范依据。' }));
  }
}

export function renderIssues(run) {
  const node = clear($('panel-issues'));
  const badge = $('issueCount');
  if (!run || !run.result) {
    badge.hidden = true;
    node.append(h('div', { class: 'placeholder', text: '判定与自检完成后，在此汇总待补正事项与报告自检意见' }));
    return;
  }
  const result = run.result;
  const qa = run.qa || { errors: [], warnings: [], hints: [] };
  const pending = (run.items || []).filter((i) => i.final && ['BLOCKED', 'SKIPPED'].includes(i.status));
  const groups = [
    ['交接包问题（阻止判定）', (result.issues || []).map((t) => ['err', t])],
    ['待补正与未开展的验算项', pending.map((i) => [i.status === 'BLOCKED' ? 'warn' : '', `${i.section_label} ${i.direction_label || ''} ${i.kind_label}：${i.reason}`])],
    ['流程停止点', (result.stops || []).map((s) => ['warn', s.reason])],
    ['报告自检 · 错误', (qa.errors || []).map((t) => ['err', t])],
    ['报告自检 · 警告', (qa.warnings || []).map((t) => ['warn', t])],
    ['报告自检 · 提示', (qa.hints || []).map((t) => ['hint', t])],
  ];
  const total = (result.issues || []).length + pending.length + (qa.errors || []).length + (qa.warnings || []).length;
  badge.hidden = !total;
  badge.textContent = total;
  for (const [title, entries] of groups) {
    if (!entries.length) continue;
    node.append(h('div', { class: 'issue-group' }, h('h3', {}, title, h('span', { class: 'count', text: entries.length })),
      h('ul', { class: 'issue-list' }, entries.map(([cls, text]) => h('li', { class: cls, text })))));
  }
  if (!node.childNodes.length) node.append(h('div', { class: 'placeholder', text: '无待补正事项，自检未发现问题' }));
}

export function renderData(summary, packageData) {
  const node = clear($('panel-data'));
  if (!summary) {
    node.append(h('div', { class: 'placeholder', text: '选择交接数据后显示概况' }));
    return;
  }
  const project = (packageData && packageData.project) || {};
  const analysis = (packageData && packageData.analysis) || {};
  const variant = packageData && packageData.variant;
  const rows = [
    ['桥梁', summary.bridge_name], ['桥型 / 跨径', [summary.bridge_type, summary.span_text].filter(Boolean).join(' · ') || '—'],
    ['桥梁编号', summary.bridge_id], ['模型版本', summary.model_revision], ['数据性质', DATA_KIND[summary.data_kind]?.[0] || '未声明'],
    ['构件 / 验算记录', `${summary.components} / ${summary.checks}${summary.retrofit_checks ? `（加固 ${summary.retrofit_checks}）` : ''}`],
  ];
  if (analysis.methods) rows.push(['分析方法', `E1 ${analysis.methods.E1 || '—'}；E2 ${analysis.methods.E2 || '—'}`]);
  if (project.organization) rows.push(['编制单位', project.organization]);
  if (variant) rows.push(['变体修改', variant.changes.join('；')]);
  node.append(h('dl', { class: 'kv' }, rows.flatMap(([k, v]) => [h('dt', { text: k }), h('dd', { text: v ?? '—' })])));
  if (packageData) {
    const details = h('details', { class: 'raw' }, h('summary', { text: '查看交接包原始 JSON' }));
    details.addEventListener('toggle', () => {
      if (details.open && !details.querySelector('pre')) details.append(h('pre', { text: JSON.stringify(packageData, null, 2) }));
    }, { once: false });
    node.append(details);
  } else {
    node.append(h('p', { class: 'table-note', text: 'zip 交接包已在服务端解包，原始 JSON 可在运行后下载 input.json 查看。' }));
  }
}
