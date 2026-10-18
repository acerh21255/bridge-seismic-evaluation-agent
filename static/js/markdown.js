// Minimal Markdown renderer for advisory memos. Builds DOM nodes only (never innerHTML), so model text cannot inject markup.
import { h } from './dom.js';

function inline(text) {
  const nodes = [];
  const pattern = /\*\*(.+?)\*\*|`([^`]+)`/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    nodes.push(match[1] !== undefined ? h('strong', { text: match[1] }) : h('code', { text: match[2] }));
    last = match.index + match[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

const cells = (line) => line.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
const isRule = (line) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(line);

export function renderMarkdown(source) {
  const out = [];
  const lines = String(source || '').replace(/\r/g, '').split('\n');
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i += 1; continue; }
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      out.push(h(`h${Math.min(heading[1].length + 1, 5)}`, {}, inline(heading[2])));
      i += 1;
    } else if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) {
      out.push(h('hr'));
      i += 1;
    } else if (line.startsWith('>')) {
      const block = [];
      while (i < lines.length && lines[i].startsWith('>')) block.push(lines[i++].replace(/^>\s?/, ''));
      out.push(h('blockquote', {}, inline(block.join(' '))));
    } else if (line.includes('|') && i + 1 < lines.length && isRule(lines[i + 1])) {
      const head = cells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) rows.push(cells(lines[i++]));
      out.push(h('div', { class: 'md-table' }, h('table', {},
        h('thead', {}, h('tr', {}, head.map((c) => h('th', {}, inline(c))))),
        h('tbody', {}, rows.map((r) => h('tr', {}, head.map((_, k) => h('td', {}, inline(r[k] || '')))))))));
    } else if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, ''));
      out.push(h(ordered ? 'ol' : 'ul', {}, items.map((t) => h('li', {}, inline(t)))));
    } else {
      const para = [];
      while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|>|\s*([-*]|\d+\.)\s|\s*-{3,}\s*$)/.test(lines[i])) para.push(lines[i++].trim());
      if (!para.length) para.push(lines[i++].trim());
      out.push(h('p', {}, inline(para.join(''))));
    }
  }
  return out;
}
