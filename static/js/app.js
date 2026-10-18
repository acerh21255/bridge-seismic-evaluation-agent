// Workbench controller: selection, upload, run submission, incremental polling and history.
import { api, postJson, postZip } from './api.js';
import { createLightbox, renderContract } from './contract.js';
import { $, h, toast } from './dom.js';
import { icon, hydrateIcons } from './icons.js';
import { renderAdvice, renderData, renderDiagnosis, renderFiles, renderIssues, renderMatrix, renderPreview, renderVerdict } from './results.js';
import { markScenario, renderHistory, renderScenarios, renderUploadState } from './sidebar.js';
import { renderPipeline, renderTask, renderTimeline } from './workflow.js';
import { initWorkspace, renderExecution } from './workspace.js';
import { AGENT_PRESETS, DEFAULT_TASK } from './presets.js';

const POLL_MS = 700;
const state = {
  config: null,
  scenarios: [],
  selection: null, // { kind: 'scenario' | 'json' | 'zip', id, name, summary, package, packageId }
  preset: null,
  run: null,
  runInput: null,
  events: [],
  lastSeq: 0,
  seen: new Set(),
  filter: 'all',
  history: [],
  submitting: false,
  pollTimer: null,
  tickTimer: null,
  ready: false,
  valid: false,
};
const openPage = createLightbox();
const workspace = initWorkspace({getSelection:()=>state.selection,onReady:(ready,valid)=>{state.ready=ready;state.valid=valid;updateRunButton();},onConfig:cfg=>{state.config=cfg;renderEnvironment();}});

function summarize(data) {
  const project = data.project || {};
  return {
    bridge_name: `${project.route || ''} ${project.stake || ''}`.trim() || data.bridge_id || '未命名交接包',
    bridge_type: project.bridge_type, span_text: project.span_text, bridge_id: data.bridge_id, model_revision: data.model_revision,
    data_kind: data.data_kind, variant_title: data.variant?.title, components: (data.components || []).length,
    checks: (data.checks || []).length, retrofit_checks: (data.retrofit?.checks || []).length,
  };
}

function busy() {
  return state.submitting || (state.run && ['queued', 'running'].includes(state.run.status));
}

function updateRunButton() {
  const button = $('runBtn');
  button.disabled = !state.selection || !state.ready || busy();
  const label = state.submitting ? '提交中…' : busy() ? '生成中…' : state.ready && !state.valid ? '生成补正通知' : '生成报告与建议';
  button.replaceChildren(busy() ? h('span', { class: 'spin' }) : icon('play'), h('span', { text: label }));
  const inspected = $('readinessBadge').dataset.state;
  $('stepInspect').className = inspected ? `done ${inspected}` : '';
  $('stepConfirm').className = state.ready ? 'done' : '';
  const live = document.querySelector('input[name="mode"]:checked')?.value === 'live';
  const cfg = state.config;
  let hint;
  if (!state.selection) hint = '先从左侧选择工程案例，或选择一个应用场景。';
  else if (!state.ready) hint = '发起前需要先检查交接资料，并勾选确认。';
  else if (live) hint = `将由 ${cfg.model} 调用工具并撰写建议书；任务与必要工具结果会发送给该服务，可能产生费用。`;
  else hint = cfg?.live_available ? `离线演示：脚本按固定顺序调用工具，建议书由规则库生成。切换“真实模型”后由 ${cfg.model} 撰写。`
    : '离线演示：建议书由规则库生成。在“模型与模板”应用模型配置后，可由大模型按任务撰写。';
  $('agentModeHint').textContent = hint;
  const top = $('topStatus');
  top.className = `top-status ${live ? 'live' : ''}`;
  top.textContent = live ? `真实模型 · ${cfg.model}` : cfg?.live_available ? `离线演示 · 已配置 ${cfg.model}` : '离线演示';
}

function render() {
  const summary = state.run ? state.run.input_summary : state.selection?.summary;
  const packageData = state.run ? state.runInput : state.selection?.package;
  renderTask(summary);
  renderPipeline(state.run, state.events);
  renderTimeline(state.run, state.events, state.seen);
  renderExecution(state.run,state.events);
  renderVerdict(state.run);
  renderAdvice(state.run);
  renderDiagnosis(state.run);
  renderPreview(state.run, state.events, openPage);
  renderFiles(state.run);
  renderMatrix(state.run, state.filter, (filter) => { state.filter = filter; render(); });
  renderIssues(state.run);
  renderData(summary, packageData);
  renderHistory(state.history, state.run?.id, openRun);
  updateRunButton();
}

function renderEnvironment() {
  const env = $('env');
  const cfg = state.config;
  const chipNode = (cls, text, title) => h('span', { class: `env-chip ${cls}`, title }, h('i'), text);
  env.replaceChildren(
    chipNode('ok', '离线脚本模型', '按固定顺序调用真实工具，不调用大模型，无 API 费用'),
    chipNode(cfg.live_available ? 'ok' : '', cfg.live_available ? `真实模型：${cfg.model}` : '真实模型未配置', '在服务端环境变量中配置后可用'),
    chipNode(cfg.word_available ? 'ok' : 'warn', cfg.word_available ? 'Word 渲染可用' : 'Word 不可用', cfg.word_available
      ? '本机 Word 刷新目录页码并导出 PDF' : '仅生成 DOCX 与网页预览，目录在打开文档时更新'),
    chipNode('', `交接合同 v${cfg.contract_version}`, '第三步 → 第四步数据合同'));
  const live = document.querySelector('input[name="mode"][value="live"]');
  live.disabled = !cfg.live_available;
  if(!cfg.live_available)document.querySelector('input[name="mode"][value="offline"]').checked=true;
  $('liveMode').title = cfg.live_available ? '使用服务端配置的真实大模型' : '真实模型未配置（本轮仅离线演示）';
  updateRunButton();
}

function renderAgentPresets() {
  const caseName = (id) => state.scenarios.find((s) => s.id === id)?.title || id;
  $('agentPresets').replaceChildren(...AGENT_PRESETS.map((preset) => h('button', {
    type: 'button', class: 'preset', 'aria-pressed': String(state.preset === preset.id), dataset: { preset: preset.id },
    onclick: () => loadPreset(preset),
  },
  h('span', { class: 'preset-role', text: preset.role }),
  h('span', { class: 'preset-question', text: preset.question }),
  h('span', { class: 'preset-meta' }, h('b', { text: preset.title }), ` · ${caseName(preset.scenario_id)}`),
  h('span', { class: 'preset-output', text: preset.output }))));
}

function markPreset() {
  document.querySelectorAll('.preset').forEach((node) => node.setAttribute('aria-pressed', String(node.dataset.preset === state.preset)));
}

async function loadPreset(preset) {
  if (busy()) { toast('请等待当前任务完成后再切换场景。'); return; }
  await selectScenario(preset.scenario_id);
  state.preset = preset.id;
  markPreset();
  $('taskText').value = preset.task;
  $('composerTitle').textContent = preset.question;
  if (state.config?.live_available) document.querySelector('input[name="mode"][value="live"]').checked = true;
  $('presetFeedback').textContent = `已载入“${preset.title}”。检查交接资料并确认后即可生成。`;
  updateRunButton();
}

async function selectScenario(id) {
  const entry = state.scenarios.find((s) => s.id === id);
  if (!entry) return;
  resetTask();
  workspace.reset();
  showView('intake');
  workspace.loadVisual(id);
  stopPolling();
  state.run = null;
  state.events = [];
  markScenario(id);
  renderUploadState(null);
  history.replaceState(null, '', location.pathname);
  state.selection = { kind: 'scenario', id, name: entry.title, summary: null, package: null };
  render();
  try {
    const data = await api(`/api/scenarios/${encodeURIComponent(id)}`);
    if (state.selection?.id !== id) return;
    state.selection.package = data;
    state.selection.summary = summarize(data);
    render();
  } catch (error) {
    toast(`读取场景失败：${error.message}`, 'error');
  }
}

function resetTask() {
  state.preset = null;
  markPreset();
  $('taskText').value = DEFAULT_TASK;
  $('composerTitle').textContent = '生成报告，并给出工程建议';
  $('presetFeedback').textContent = '选择场景只载入案例与任务说明，点击生成后才调用模型。';
}

async function handleFile(file) {
  if (!file) return;
  resetTask();
  workspace.reset(); workspace.loadVisual(null); showView('intake');
  stopPolling();
  state.run = null;
  state.events = [];
  markScenario(null);
  try {
    if (file.name.toLowerCase().endsWith('.zip')) {
      renderUploadState({ message: `正在上传 ${file.name}…` });
      const result = await postZip('/api/packages', file);
      state.selection = { kind: 'zip', id: null, packageId: result.package_id, name: file.name, summary: result.summary, package: null };
      renderUploadState({ message: `已载入 ${file.name}：图件 ${result.assets} 个，合同检查问题 ${result.issues_count} 项` });
    } else {
      const data = JSON.parse(await file.text());
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('交接包顶层必须是 JSON 对象');
      state.selection = { kind: 'json', id: null, name: file.name, summary: summarize(data), package: data };
      renderUploadState({ message: `已载入 ${file.name}（单文件 JSON 不含图件，报告中以占位呈现）` });
    }
  } catch (error) {
    state.selection = null;
    renderUploadState({ error: `无法载入 ${file.name}：${error.message}` });
  }
  render();
}

async function submitRun() {
  if (!state.selection || !state.ready || busy()) return;
  const selection = state.selection;
  const body = { task: $('taskText').value.trim(), mode: document.querySelector('input[name="mode"]:checked').value };
  Object.assign(body,workspace.extra());
  if (selection.kind === 'scenario') body.scenario_id = selection.id;
  else if (selection.kind === 'zip') Object.assign(body, { package_id: selection.packageId, name: selection.name });
  else Object.assign(body, { package: selection.package, name: selection.name });
  state.submitting = true;
  updateRunButton();
  try {
    const created = await postJson('/api/runs', body);
    state.submitting = false;
    await openRun(created.id);
    showView('process');
  } catch (error) {
    state.submitting = false;
    updateRunButton();
    toast(`提交失败：${error.message}`, 'error');
  }
}

async function openRun(id) {
  showView('process');
  stopPolling();
  state.run = { id, status: 'queued', input_summary: state.selection?.summary };
  state.runInput = null;
  state.events = [];
  state.lastSeq = 0;
  state.seen = new Set();
  state.filter = 'all';
  history.replaceState(null, '', `?run=${id}`);
  render();
  await poll(id);
}

async function poll(id) {
  try {
    const run = await api(`/api/runs/${id}?after=${state.lastSeq}`);
    if (!state.run || state.run.id !== id) return;
    const fresh = run.events || [];
    if (fresh.length) {
      state.events.push(...fresh);
      state.lastSeq = fresh[fresh.length - 1].seq;
    }
    delete run.events;
    state.run = run;
    const active = ['queued', 'running'].includes(run.status);
    if (active) {
      state.pollTimer = setTimeout(() => poll(id), POLL_MS);
      startTicking();
    } else {
      stopPolling();
      await Promise.all([loadHistory(), loadRunInput(run)]);
      if (fresh.some((e) => e.type === 'completed')) toast(`报告已生成：${run.result?.status_label || ''}`);
      if (fresh.some((e) => e.type === 'error')) toast(run.error || '任务执行失败', 'error');
    }
    render();
  } catch (error) {
    if (!state.run || state.run.id !== id) return;
    if (error.status === 404) {
      stopPolling();
      state.run = null;
      history.replaceState(null, '', location.pathname);
      render();
      toast('该运行记录不存在或已清理', 'error');
      return;
    }
    toast(`读取运行状态失败：${error.message}（2 秒后重试查询，不会重复提交任务）`, 'error');
    state.pollTimer = setTimeout(() => poll(id), 2000);
  }
}

async function loadRunInput(run) {
  const file = (run.files || []).find((f) => f.name === 'input.json');
  if (!file) return;
  try { state.runInput = await api(file.url); } catch { state.runInput = null; }
}

function startTicking() {
  if (state.tickTimer) return;
  state.tickTimer = setInterval(() => {
    renderTimeline(state.run, state.events, state.seen);
    renderPreview(state.run, state.events, openPage);
  }, 500);
}

function stopPolling() {
  clearTimeout(state.pollTimer);
  clearInterval(state.tickTimer);
  state.pollTimer = null;
  state.tickTimer = null;
}

async function loadHistory() {
  try {
    state.history = await api('/api/runs');
    renderHistory(state.history, state.run?.id, openRun);
  } catch (error) {
    toast(`读取运行历史失败：${error.message}`, 'error');
  }
}

async function showView(view) {
  document.querySelectorAll('.topnav-btn').forEach((b) => {
    if (b.dataset.view === view) b.setAttribute('aria-current', 'page');
    else b.removeAttribute('aria-current');
  });
  document.querySelectorAll('.view').forEach(node=>node.hidden=node.id!==`view-${view}`);
  if (view === 'contract' && !$('contract').childNodes.length) {
    try { renderContract(await api('/api/contract')); } catch (error) { toast(`读取交接合同失败：${error.message}`, 'error'); }
  }
}

function bind() {
  document.querySelectorAll('input[name="mode"]').forEach(input=>input.addEventListener('change',updateRunButton));
  $('runBtn').addEventListener('click', submitRun);
  $('uploadBtn').addEventListener('click', () => $('fileInput').click());
  $('fileInput').addEventListener('change', (event) => { handleFile(event.target.files[0]); event.target.value = ''; });
  $('refreshHistory').addEventListener('click', loadHistory);
  document.querySelectorAll('.topnav-btn').forEach((b) => b.addEventListener('click', () => showView(b.dataset.view)));
  document.querySelectorAll('[data-open]').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.open)));
  document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((t) => t.setAttribute('aria-selected', String(t === tab)));
    document.querySelectorAll('.tab-panel').forEach((p) => { p.hidden = p.id !== `panel-${tab.dataset.tab}`; });
  }));
  const upload = $('upload');
  upload.addEventListener('dragover', (event) => { event.preventDefault(); });
  upload.addEventListener('drop', (event) => { event.preventDefault(); handleFile(event.dataTransfer.files[0]); });
}

async function boot() {
  hydrateIcons();
  $('taskText').value = DEFAULT_TASK;
  bind();
  render();
  try {
    state.config = await api('/api/config');
    renderEnvironment();
    workspace.hydrate(state.config);
    state.scenarios = await api('/api/scenarios');
    renderScenarios(state.scenarios, null, selectScenario);
    renderAgentPresets();
  } catch (error) {
    toast(error.message, 'error');
    return;
  }
  await loadHistory();
  const runId = new URLSearchParams(location.search).get('run');
  if (runId && /^[a-f0-9]{32}$/.test(runId)) {
    await openRun(runId);
  } else if (state.scenarios.length) {
    await selectScenario(state.scenarios[0].id);
  }
}

boot();
