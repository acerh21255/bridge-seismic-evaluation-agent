// Authored 24px stroke icons (1.75 stroke, round caps) — one family for the whole workbench.
const PATHS = {
  check: 'M5 12.5l4.5 4.5L19 7.5',
  x: 'M6.5 6.5l11 11M17.5 6.5l-11 11',
  alert: 'M12 8v5M12 16.5v.5M10.3 3.9L2.6 17.5A2 2 0 004.3 20.5h15.4a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z',
  plus: 'M12 5v14M5 12h14',
  download: 'M12 4v11M7.5 10.5L12 15l4.5-4.5M5 19.5h14',
  play: 'M8 5.5v13l10.5-6.5z',
  arrow: 'M5 12h13M13 6.5l5.5 5.5-5.5 5.5',
  left: 'M14.5 6l-6 6 6 6',
  right: 'M9.5 6l6 6-6 6',
  close: 'M6.5 6.5l11 11M17.5 6.5l-11 11',
  refresh: 'M19.5 12a7.5 7.5 0 11-2.2-5.3M19.5 4.5v4h-4',
  file: 'M14 3.5H7a1.5 1.5 0 00-1.5 1.5v14A1.5 1.5 0 007 20.5h10a1.5 1.5 0 001.5-1.5V8L14 3.5zM14 3.5V8h4.5',
  search: 'M10.5 17a6.5 6.5 0 110-13 6.5 6.5 0 010 13zM15.5 15.5L20 20',
  clock: 'M12 7v5l3 2M12 20.5a8.5 8.5 0 110-17 8.5 8.5 0 010 17z',
};

export function icon(name, cls = 'ico') {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('class', cls);
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS(ns, 'path');
  path.setAttribute('d', PATHS[name]);
  svg.append(path);
  return svg;
}

export function hydrateIcons(root = document) {
  root.querySelectorAll('[data-icon]').forEach((node) => node.prepend(icon(node.dataset.icon)));
}
