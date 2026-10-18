// Handoff contract view and the page lightbox.
import { $, clear, h } from './dom.js';

export function renderContract(contract) {
  const node = clear($('contract'));
  node.append(h('div', { class: 'card contract-hero' },
    h('h1', { text: `第三步 → 第四步 交接合同 ${contract.version}` }),
    h('p', { text: contract.summary }),
    h('div', { class: 'contract-downloads' }, contract.downloads.map((d) => h('a', { class: 'btn-ghost', href: d.url, text: d.name })))));
  node.append(h('div', { class: 'contract-grid' }, contract.sections.map((section) => h('div', { class: 'card contract-card' },
    h('h3', {}, section.name, h('span', { class: `chip ${section.required ? 'BLOCKED' : 'NA'}`, text: section.required ? '必交' : '可选' })),
    h('p', { text: section.description }),
    h('div', { class: 'field-list' }, section.fields.map((f) => h('code', { text: f })))))));
}

export function createLightbox() {
  const box = $('lightbox');
  const image = $('lbImage');
  const caption = $('lbCaption');
  let pages = [];
  let index = 0;
  const show = (next) => {
    index = Math.max(0, Math.min(pages.length - 1, next));
    image.src = pages[index];
    image.alt = `报告第 ${index + 1} 页`;
    caption.textContent = `${index + 1} / ${pages.length}`;
  };
  const close = () => { box.hidden = true; };
  $('lbClose').addEventListener('click', close);
  $('lbPrev').addEventListener('click', () => show(index - 1));
  $('lbNext').addEventListener('click', () => show(index + 1));
  box.addEventListener('click', (event) => { if (event.target === box) close(); });
  document.addEventListener('keydown', (event) => {
    if (box.hidden) return;
    if (event.key === 'Escape') close();
    if (event.key === 'ArrowLeft') show(index - 1);
    if (event.key === 'ArrowRight') show(index + 1);
  });
  return (list, start) => {
    pages = list;
    box.hidden = false;
    show(start);
    $('lbClose').focus();
  };
}
