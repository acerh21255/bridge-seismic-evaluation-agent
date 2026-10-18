// Left rail: scenario cards, upload state and run history.
import { $, DATA_KIND, RUN_STATUS, STATUS, clear, fmtTime, h } from './dom.js';

export function renderScenarios(scenarios, selectedId, onSelect) {
  const list = clear($('scenarioList'));
  const golden = scenarios.filter((s) => s.group === 'golden');
  const variants = scenarios.filter((s) => s.group !== 'golden');
  const card = (s) => h('button', {
    type: 'button', role: 'option', class: `scenario ${s.group === 'golden' ? 'golden' : ''}`,
    'aria-selected': String(s.id === selectedId), dataset: { id: s.id }, onclick: () => onSelect(s.id),
  },
  h('span', { class: 'scenario-title', text: s.title }),
  h('span', { class: `chip ${s.expected_status}`, title: '该场景设计的预期结论', text: `预期${STATUS[s.expected_status]}` }),
  h('span', { class: 'scenario-desc', text: s.description }));
  golden.forEach((s) => list.append(card(s)));
  if (variants.length) list.append(h('div', { class: 'group-label', text: '演示变体（由金标准派生，每个只改一处）' }));
  variants.forEach((s) => list.append(card(s)));
}

export function markScenario(selectedId) {
  document.querySelectorAll('#scenarioList .scenario').forEach((node) => {
    node.setAttribute('aria-selected', String(node.dataset.id === selectedId));
  });
}

export function renderUploadState(state) {
  const node = $('uploadState');
  if (!state) { node.hidden = true; return; }
  node.hidden = false;
  node.className = `upload-state ${state.error ? 'error' : ''}`;
  node.textContent = state.error ? state.error : state.message;
}

export function renderHistory(runs, currentId, onOpen) {
  const list = clear($('historyList'));
  if (!runs.length) {
    list.append(h('li', { class: 'empty-note', text: '还没有运行记录' }));
    return;
  }
  for (const run of runs.slice(0, 30)) {
    const active = run.status === 'queued' || run.status === 'running';
    const dotClass = active ? 'running' : (run.report_status || '');
    const summary = run.input_summary || {};
    const title = summary.variant_title ? `${summary.variant_title} · ${summary.bridge_name}` : (summary.bridge_name || '未命名交接包');
    const state = active ? RUN_STATUS[run.status] : (run.report_status ? STATUS[run.report_status] : RUN_STATUS[run.status]);
    list.append(h('li', { class: 'history-item' },
      h('button', { type: 'button', 'aria-current': String(run.id === currentId), title: `${title}（${state}）`, onclick: () => onOpen(run.id) },
        h('span', { class: `dot ${dotClass}` }),
        h('span', { class: 'history-name', text: title }),
        h('span', { class: 'history-time', text: fmtTime(run.created_at) }))));
  }
}

export function dataKindTag(kind) {
  const [label, cls] = DATA_KIND[kind] || ['数据性质未声明', ''];
  return h('span', { class: `tag ${cls}`, text: label });
}
