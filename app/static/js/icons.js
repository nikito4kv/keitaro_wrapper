// Значки интерфейса. Контуры взяты из набора Tabler Icons (лицензия MIT), логотип NL свой.
//
// В разметке значок ставится так: <span data-icon="copy"></span>
// В коде так: icon('copy')

const NS = 'http://www.w3.org/2000/svg';

const PATHS = {
  info: ['M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0', 'M12 9h.01', 'M11 12h1v4h1'],
  copy: [
    'M7 7m0 2.667a2.667 2.667 0 0 1 2.667 -2.667h8.666a2.667 2.667 0 0 1 2.667 2.667v8.666a2.667 2.667 0 0 1 -2.667 2.667h-8.666a2.667 2.667 0 0 1 -2.667 -2.667z',
    'M4.012 16.737a2.005 2.005 0 0 1 -1.012 -1.737v-10c0 -1.1 .9 -2 2 -2h10c.75 0 1.158 .385 1.5 1',
  ],
  check: ['M5 12l5 5l10 -10'],
  external: ['M17 7l-10 10', 'M8 7l9 0l0 9'],
  plus: ['M12 5l0 14', 'M5 12l14 0'],
  refresh: ['M20 11a8.1 8.1 0 0 0 -15.5 -2m-.5 -4v4h4', 'M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4'],
  pin: ['M15 4.5l-4 4l-4 1.5l-1.5 1.5l7 7l1.5 -1.5l1.5 -4l4 -4', 'M9 15l-4.5 4.5', 'M14.5 4l5.5 5.5'],
  back: ['M5 12l14 0', 'M5 12l6 6', 'M5 12l6 -6'],
  edit: ['M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4', 'M13.5 6.5l4 4'],
  chevron: ['M9 6l6 6l-6 6'],
};

export function icon(name, size = 16) {
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', String(size));
  svg.setAttribute('height', String(size));
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.75');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  svg.classList.add('icon');
  for (const d of PATHS[name] ?? []) {
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', d);
    svg.append(path);
  }
  return svg;
}

/** Подставляет значки во все места разметки, помеченные data-icon. */
export function hydrateIcons(root = document) {
  for (const holder of root.querySelectorAll('[data-icon]')) {
    if (holder.firstChild) continue;
    holder.append(icon(holder.dataset.icon, Number(holder.dataset.size) || 16));
  }
}
