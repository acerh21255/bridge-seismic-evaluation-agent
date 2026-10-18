// DOM helpers, status vocabulary and formatting shared by the workbench modules.

export function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = String(value);
    else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else node.setAttribute(key, value === true ? '' : String(value));
  }
  for (const child of children.flat()) {
    if (child === undefined || child === null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function $(id) {
  return document.getElementById(id);
}

export const STATUS = {
  PASS: '满足',
  FAIL: '不满足',
  BLOCKED: '待补正',
  PLASTIC: '进入塑性',
  SKIPPED: '未开展',
  NA: '不适用',
  RUNNING: '进行中',
};

export const RUN_STATUS = { queued: '排队中', running: '执行中', completed: '已完成', failed: '执行失败', interrupted: '已中断' };

export const DATA_KIND = {
  reference_reproduction: ['原报告复现', 'kind-ref'],
  synthetic_variant: ['演示变体', 'kind-var'],
  engineering_input: ['工程输入', 'kind-eng'],
};

export function chip(status, text) {
  return h('span', { class: `chip ${status}` }, text || STATUS[status] || status);
}

export function fmtNumber(value, digits) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value !== 'number' || !Number.isFinite(value)) return String(value);
  if (digits !== undefined) return value.toFixed(digits);
  if (Number.isInteger(value)) return String(value);
  return String(Number(value.toPrecision(10)));
}

export function fmtUnit(unit) {
  return { 'kN*m': 'kN·m', ratio: '' }[unit] ?? unit ?? '';
}

export function fmtBytes(bytes) {
  if (!bytes && bytes !== 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function fmtTime(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  const today = new Date();
  const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`;
  return date.toDateString() === today.toDateString() ? time : `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${time}`;
}

export function fmtDuration(ms) {
  if (ms === undefined || ms === null) return '';
  if (ms < 1000) return `${Math.max(ms, 1)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

let toastTimer;
export function toast(message, kind = 'info') {
  const node = $('toast');
  node.textContent = message;
  node.className = `toast ${kind === 'error' ? 'error' : ''}`;
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, kind === 'error' ? 6000 : 3200);
}
