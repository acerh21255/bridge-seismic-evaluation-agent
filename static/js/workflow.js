// Task card, gate pipeline and the agent tool timeline (real backend events only).
import { $, STATUS, clear, fmtDuration, h } from './dom.js';
import { icon } from './icons.js';
import { dataKindTag } from './sidebar.js';

export const TOOLS = [
  ['inspect_handoff', '检查交接资料'],
  ['read_report_rules', '读取报告撰写规范'],
  ['evaluate_gates', '执行抗震验算'],
  ['diagnose_weaknesses', '诊断薄弱环节'],
  ['compose_report', '撰写报告章节'],
  ['render_documents', '渲染 Word / PDF'],
  ['run_quality_checks', '报告自检'],
  ['write_advisory_memo', '撰写建议书'],
  ['finalize_delivery', '整理交付文件'],
];
const OPTIONAL_TOOLS = [['query_checks', '查询验算记录']];
const GATES = [
  ['handoff', '交接校验'], ['e1', 'E1 验算'], ['e2_pier', 'E2 桥墩屈服'], ['e2_pile', '桩基能力保护'], ['shear', '墩桩抗剪'],
  ['bearing', '支座与专项'], ['pilecap', '承台验算'], ['detailing', '构造措施'], ['ductility', '延性验算'], ['retrofit', '加固复核'],
  ['report', '报告生成'],
];

export function renderTask(summary) {
  const node = clear($('taskBridge'));
  if (!summary) {
    node.append(h('span', { class: 'muted', text: '请从左侧选择工程案例，或导入交接包' }));
    return;
  }
  const tags = [dataKindTag(summary.data_kind)];
  if (summary.variant_title) tags.push(h('span', { class: 'tag', text: `变体：${summary.variant_title}` }));
  if (summary.bridge_type) tags.push(h('span', { class: 'tag', text: summary.bridge_type }));
  if (summary.span_text) tags.push(h('span', { class: 'tag', text: summary.span_text }));
  tags.push(h('span', { class: 'tag', text: `构件 ${summary.components} · 验算记录 ${summary.checks}${summary.retrofit_checks ? ` + 加固 ${summary.retrofit_checks}` : ''}` }));
  node.append(h('div', { class: 'name', text: summary.bridge_name || summary.bridge_id }), h('div', { class: 'meta' }, tags));
}

function toolState(events) {
  const state = {};
  for (const event of events) {
    if (!event.tool) continue;
    const calls = (state[event.tool]?.calls || 0) + (event.type === 'tool_call' ? 1 : 0);
    if (event.type === 'tool_call') state[event.tool] = { status: 'running', at: event.at, calls };
    if (event.type === 'tool_result') {
      const status = event.status === 'BLOCKED' ? 'blocked' : event.status === 'WARN' ? 'warn' : 'done';
      state[event.tool] = { status, detail: event.detail, elapsed: event.elapsed_ms, calls };
    }
  }
  return state;
}

export function renderPipeline(run, events) {
  const list = clear($('pipeline'));
  const result = run && run.result;
  const gates = Object.fromEntries(((result && result.gates) || []).map((g) => [g.id, g]));
  const tools = toolState(events || []);
  const writing = ['compose_report', 'render_documents', 'run_quality_checks', 'finalize_delivery'].some((t) => tools[t]?.status === 'running');
  for (const [id, title] of GATES) {
    let status = '';
    let summary = '待执行';
    if (id === 'report') {
      if (run && run.status === 'completed') {
        const qa = run.qa || {};
        status = qa.errors && qa.errors.length ? 'BLOCKED' : 'PASS';
        const pages = run.rendering && run.rendering.page_count ? `${run.rendering.page_count} 页 · ` : '';
        summary = `${pages}自检错误 ${(qa.errors || []).length}`;
      } else if (writing) {
        status = 'RUNNING';
        summary = '撰写与渲染中';
      }
    } else if (gates[id]) {
      status = gates[id].status;
      summary = gates[id].summary;
    } else if (result && id === 'retrofit') {
      status = 'NA';
      summary = '无加固复核';
    } else if (result && !result.evaluated && id !== 'handoff') {
      status = 'SKIPPED';
      summary = '交接未通过，未判定';
    } else if (!result && (tools.inspect_handoff || tools.evaluate_gates) && id === 'handoff') {
      status = 'RUNNING';
      summary = '检查中';
    }
    list.append(h('li', { class: `gate ${status}`, title: summary },
      h('span', { class: 'gate-state', text: status ? STATUS[status] : '' }),
      h('div', { class: 'gate-title', text: title }),
      h('div', { class: 'gate-summary', text: summary })));
  }
  $('pipelineHint').textContent = result
    ? (result.evaluated ? '停止条件：E1 不满足、桩基屈服、墩桩抗剪不满足' : '交接包未通过合同检查，未开展判定')
    : '判定引擎按项目流程逐级执行';
}

const STEP_ICON = { done: 'check', blocked: 'alert', warn: 'alert' };

export function renderTimeline(run, events, seen) {
  const list = clear($('timeline'));
  const tools = toolState(events || []);
  const now = Date.now();
  const rows = [...TOOLS, ...OPTIONAL_TOOLS.filter(([name]) => tools[name])];
  rows.forEach(([name, title], index) => {
    const step = tools[name];
    const status = step ? step.status : 'pending';
    let detail = '等待调用';
    let time = '';
    if (step && step.status === 'running') {
      detail = name === 'render_documents' ? '正在写出 DOCX，并由 Word 刷新目录页码、导出 PDF…' : '执行中…';
      time = fmtDuration(Math.max(0, now - new Date(step.at).getTime()));
    } else if (step) {
      detail = step.detail;
      time = fmtDuration(step.elapsed);
    } else if (run && ['failed', 'interrupted'].includes(run.status)) {
      detail = '未执行';
    }
    const fresh = step && !seen.has(`${name}:${status}`);
    if (step) seen.add(`${name}:${status}`);
    const mark = STEP_ICON[status] ? icon(STEP_ICON[status]) : status === 'running' ? '' : String(index + 1);
    const repeat = step?.calls > 1 ? h('span', { class: 'step-repeat', text: `×${step.calls}` }) : null;
    list.append(h('li', { class: `step ${status}${fresh ? ' fresh' : ''}` },
      h('span', { class: 'step-icon' }, mark),
      h('div', {}, h('div', { class: 'step-title' }, title, repeat, h('code', { text: name })), h('div', { class: 'step-detail', text: detail })),
      h('span', { class: 'step-time', text: time })));
  });
  const message = $('agentMessage');
  const failure = run && run.error;
  if (failure || (run && run.agent_message)) {
    message.hidden = false;
    message.className = `agent-message${failure ? ' error' : ''}`;
    clear(message).append(h('b', { text: failure ? '执行失败' : 'Agent 回复' }), h('span', { text: failure || run.agent_message }));
  } else {
    message.hidden = true;
  }
  const hint = $('timelineHint');
  if (!run) hint.textContent = '工具调用由后端实时记录';
  else if (run.status === 'completed' && run.duration_ms) hint.textContent = `${run.mode === 'live' ? '真实大模型' : '离线脚本模型'} · 总耗时 ${fmtDuration(run.duration_ms)}`;
  else hint.textContent = run.mode === 'live' ? '真实大模型选择工具' : '离线脚本模型按固定顺序调用真实工具';
}
