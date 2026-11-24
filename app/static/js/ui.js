// Мелочи, общие для всех страниц: шапка, плашка об ошибке, кнопки, подсказки, подписи.

import { api } from './api.js';
import { hydrateIcons, icon } from './icons.js';

export const $ = (id) => document.getElementById(id);

export const regionNames = new Intl.DisplayNames(['ru'], { type: 'region' });

const dateFormat = new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const timeFormat = new Intl.DateTimeFormat('ru', { hour: '2-digit', minute: '2-digit' });
const dayFormat = new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'long', year: 'numeric' });

export const formatDate = (date) => dateFormat.format(date);
export const formatTime = (date) => timeFormat.format(date);

/**
 * Keitaro отдаёт время строкой «2026-11-24 10:18:03» в часовом поясе трекера, которого мы не знаем.
 * Поэтому показываем только день: часы могли бы оказаться чужими.
 */
export function formatTrackerDate(text) {
  if (!text) return '';
  const date = new Date(`${text.slice(0, 10)}T12:00:00`);
  return Number.isNaN(date.getTime()) ? '' : dayFormat.format(date);
}

/** Приводит текст к виду, удобному для поиска: без регистра и без разницы между «е» и «ё». */
export const searchKey = (text) => text.toLowerCase().replaceAll('ё', 'е').trim();

/** У части офферов название начинается с их же номера. Номер мы показываем отдельно, повтор убираем. */
export function offerTitle(offer) {
  const prefix = `${offer.id} `;
  return offer.name.startsWith(prefix) ? offer.name.slice(prefix.length) : offer.name;
}

export function shortList(items, shown) {
  if (items.length <= shown) return items.join(', ');
  return `${items.slice(0, shown).join(', ')} и ещё ${items.length - shown}`;
}

/** Создаёт элемент с классом и текстом. Текст всегда вставляется как текст, не как разметка. */
export function el(tag, className = '', text = '') {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== '') node.textContent = text;
  return node;
}

// Кнопки --------------------------------------------------------------------

/**
 * Кнопка или ссылка в виде кнопки. Значок можно поставить до подписи или после неё.
 *   button('Убрать', 'btn-ghost btn-small')
 *   button('Открыть в Keitaro', 'btn-ghost btn-small', { href, iconAfter: 'external' })
 */
export function button(text, className, { href = '', iconBefore = '', iconAfter = '', spinner = false } = {}) {
  const node = el(href ? 'a' : 'button', `btn ${className}`);
  if (href) {
    node.href = href;
    if (/^https?:/.test(href)) {
      node.target = '_blank';
      node.rel = 'noopener';
    }
  } else {
    node.type = 'button';
  }
  if (spinner) node.append(el('span', 'spinner'));
  if (iconBefore) {
    const holder = el('span', 'btn-icon');
    holder.append(icon(iconBefore, 15));
    node.append(holder);
  }
  node.append(el('span', 'btn-label', text));
  if (iconAfter) node.append(icon(iconAfter, 14));
  return node;
}

export function setBusy(node, busy, label) {
  node.disabled = busy;
  node.setAttribute('aria-busy', String(busy));
  if (label) node.querySelector('.btn-label').textContent = label;
}

/** Значок «i» и подсказка к нему. Ставятся в строку .label-row сразу после подписи. */
export function infoTip(text, id, label = 'Подсказка') {
  const trigger = el('button', 'info');
  trigger.type = 'button';
  trigger.setAttribute('aria-label', label);
  trigger.append(icon('info', 16));
  const tip = el('span', 'tip', text);
  tip.id = id;
  tip.setAttribute('role', 'tooltip');
  return [trigger, tip];
}

/**
 * Ссылка кампании с кнопкой «Скопировать».
 * Сама ссылка показана текстом: переход по ней засчитался бы в трекере как клик.
 * Кнопка после нажатия заливается цветом и пишет «Скопировано», ширина её при этом не меняется.
 */
export function linkBox(url) {
  const box = el('div', 'linkbox');
  box.append(el('span', 'mono linkbox-url', url));

  const copy = el('button', 'copy');
  copy.type = 'button';
  copy.dataset.state = 'idle';
  const idle = el('span', 'copy-face copy-idle');
  const idleLabel = el('span', '', 'Скопировать');
  idle.append(icon('copy', 14), idleLabel);
  const done = el('span', 'copy-face copy-done');
  done.append(icon('check', 14), el('span', '', 'Скопировано'));
  done.setAttribute('aria-hidden', 'true');
  copy.append(idle, done);

  let timer = 0;
  copy.addEventListener('click', async () => {
    clearTimeout(timer);
    try {
      await navigator.clipboard.writeText(url);
      copy.dataset.state = 'done';
      copy.setAttribute('aria-label', 'Ссылка скопирована');
    } catch {
      copy.dataset.state = 'fail';
      idleLabel.textContent = 'Не вышло';
      copy.setAttribute('aria-label', 'Не удалось скопировать. Выделите ссылку вручную');
    }
    timer = setTimeout(() => {
      copy.dataset.state = 'idle';
      idleLabel.textContent = 'Скопировать';
      copy.removeAttribute('aria-label');
    }, 1800);
  });

  box.append(copy);
  return box;
}

// Шапка: связь с Keitaro ----------------------------------------------------

let knownHost = '';

const CONNECTION = {
  checking: { text: 'Проверяем связь', tip: () => 'Проверяем, отвечает ли трекер Keitaro.' },
  ok: {
    text: 'Keitaro подключён',
    tip: (host) =>
      `Связь с трекером есть${host ? `: ${host}` : ''}. Кампании создаются и меняются прямо в нём, это приложение только отправляет туда запросы.`,
  },
  fail: {
    text: 'Нет связи с Keitaro',
    tip: (host) =>
      `Трекер${host ? ` ${host}` : ''} не отвечает или не принял ключ. Причина написана в красной плашке на странице.`,
  },
};

/** Показывает в шапке состояние связи с трекером. Что оно значит, объясняет подсказка при наведении. */
export function setConnection(stateName, host = knownHost) {
  if (host) knownHost = host;
  const view = CONNECTION[stateName];
  $('conn').dataset.state = stateName;
  $('conn-text').textContent = view.text;
  $('conn-tip').textContent = view.tip(knownHost);
}

export function showBanner(message) {
  $('banner-text').textContent = message;
  $('banner').hidden = false;
}

export function hideBanner() {
  $('banner').hidden = true;
}

let hostPromise = null;

/** Адрес трекера для подсказки в шапке. Берётся из настроек приложения, в Keitaro за ним ходить не нужно. */
export function keitaroHost() {
  hostPromise ??= api('/bootstrap')
    .then((boot) => (boot.keitaro_url ? new URL(boot.keitaro_url).host : ''))
    .catch(() => '');
  return hostPromise;
}

/** Отмечает в шапке, удался ли запрос к Keitaro. При неудаче показывает плашку с причиной. */
export async function reportKeitaro(error = null) {
  const host = await keitaroHost();
  if (error) {
    setConnection('fail', host);
    showBanner(error.message);
    return;
  }
  hideBanner();
  setConnection('ok', host);
}

// Подписи, которые меняются на глазах -----------------------------------------

/** Меняет текст с коротким размытием, чтобы смена не выглядела рывком. */
export function setText(node, text) {
  if (node.textContent === text) return;
  clearTimeout(node.textTimer);
  node.classList.add('is-swapping');
  node.textTimer = setTimeout(() => {
    node.textContent = text;
    node.classList.remove('is-swapping');
  }, 140);
}

// Значки, расставленные в разметке страницы, подставляем сразу при загрузке.
hydrateIcons();
