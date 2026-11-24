// Мелочи, общие для всех страниц: шапка, плашка об ошибке, кнопки, подписи.

import { api } from './api.js';

export const $ = (id) => document.getElementById(id);

export const regionNames = new Intl.DisplayNames(['ru'], { type: 'region' });

const dateFormat = new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const timeFormat = new Intl.DateTimeFormat('ru', { hour: '2-digit', minute: '2-digit' });

export const formatDate = (date) => dateFormat.format(date);
export const formatTime = (date) => timeFormat.format(date);

const dayFormat = new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'long', year: 'numeric' });

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

export function setBusy(button, busy, label) {
  button.disabled = busy;
  button.setAttribute('aria-busy', String(busy));
  if (label) button.querySelector('.btn-label').textContent = label;
}

// Шапка: связь с Keitaro ----------------------------------------------------

export function setConnection(stateName, text) {
  $('conn').dataset.state = stateName;
  $('conn-text').textContent = text;
}

export function showBanner(message) {
  $('banner-text').textContent = message;
  $('banner').hidden = false;
}

export function hideBanner() {
  $('banner').hidden = true;
}

let hostPromise = null;

/** Адрес трекера для шапки. Берётся из настроек приложения, в Keitaro за ним ходить не нужно. */
export function keitaroHost() {
  hostPromise ??= api('/bootstrap')
    .then((boot) => (boot.keitaro_url ? new URL(boot.keitaro_url).host : 'Keitaro'))
    .catch(() => 'Keitaro');
  return hostPromise;
}

/** Отмечает в шапке, удался ли запрос к Keitaro. При неудаче показывает плашку с причиной. */
export async function reportKeitaro(error = null) {
  if (error) {
    setConnection('fail', 'Нет связи с Keitaro');
    showBanner(error.message);
    return;
  }
  hideBanner();
  setConnection('ok', await keitaroHost());
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

/** Показывает временную подпись и возвращает прежнюю. */
export function flashText(node, text, back, delay = 1800) {
  clearTimeout(node.flashTimer);
  setText(node, text);
  node.flashTimer = setTimeout(() => setText(node, back), delay);
}

export async function copyText(text, label, back) {
  let done = true;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    done = false;
  }
  flashText(label, done ? 'Скопировано' : 'Не вышло, выделите вручную', back);
}

/** Кнопка-ссылка «Скопировать ссылку» с подписью, которая на миг меняется на «Скопировано». */
export function copyButton(text, caption = 'Скопировать ссылку') {
  const button = el('button', 'link');
  button.type = 'button';
  const label = el('span', 'swap', caption);
  button.append(label);
  button.addEventListener('click', () => copyText(text, label, caption));
  return button;
}
