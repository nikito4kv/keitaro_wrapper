// Редактор офферов кампании.
//
// Кнопки «Добавить», «Убрать», «Вернуть» и «Закрепить» меняют только черновик на нашем сервере.
// В Keitaro состав потока уходит по кнопке «Отправить в Keitaro». Все цифры считает сервер,
// страница только показывает то, что он вернул.
//
// Все потоки показаны одинаково: название и офферы (или их отсутствие). Что поток делает
// без офферов (фильтры, редирект), редактор не разбирает, как и исходный редактор на видео.

import { api } from './api.js';
import { icon } from './icons.js';
import { attachListbox } from './listbox.js';
import {
  $,
  button,
  el,
  formatTime,
  infoTip,
  flashDone,
  linkBox,
  offerTitle,
  reportKeitaro,
  resetButton,
  setBusy,
  setConnection,
  setText,
  shortList,
  showDone,
} from './ui.js';

const campaignId = Number(location.pathname.split('/').filter(Boolean).pop());
const streamsBox = $('streams');
const refreshButton = $('refresh');
const live = $('live');

const PIN_ON = 'Доля закреплена и не меняется при пересчёте. Нажмите, чтобы открепить.';
const PIN_OFF = 'Закрепить долю: она перестанет меняться, когда вы добавляете или убираете офферы.';

function offerNote(item) {
  switch (item.status) {
    case 'new':
      return 'появится в Keitaro после отправки';
    case 'changed':
      return `в Keitaro сейчас ${item.keitaro_share}%`;
    case 'removing':
      return `будет убран, в Keitaro сейчас ${item.keitaro_share}%`;
    case 'removed':
      return 'убран из потока';
    default:
      return '';
  }
}

// Строка оффера ---------------------------------------------------------------

function createRow(view, item, animate) {
  const node = el('li', animate ? 'offer grow-in' : 'offer');
  const inner = el('div', 'offer-inner');

  const share = el('span', 'offer-share swap');
  const main = el('div', 'offer-main');
  const name = el('span', 'offer-name');
  const meta = el('span', 'offer-meta');
  const note = el('span', 'offer-note swap');
  meta.append(el('span', 'mono', String(item.offer_id)), note);
  main.append(name, meta);

  // Закрепление: значок-переключатель с подсказкой. Рядом одна кнопка: «Убрать» или «Вернуть».
  const actions = el('div', 'offer-actions');
  const pinHolder = el('span', 'has-tip');
  const pin = el('button', 'btn btn-ghost btn-small btn-square pin');
  pin.type = 'button';
  pin.append(icon('pin', 17));
  const pinTip = el('span', 'tip tip-end');
  pinTip.id = `pin-tip-${view.id}-${item.offer_id}`;
  pinTip.setAttribute('role', 'tooltip');
  pin.setAttribute('aria-describedby', pinTip.id);
  pinHolder.append(pin, pinTip);
  const toggle = el('button', 'btn btn-small offer-toggle');
  toggle.type = 'button';
  actions.append(pinHolder, toggle);

  inner.append(share, main, actions);
  const clip = el('div', 'clip');
  clip.append(inner);
  node.append(clip);
  // Когда строка раздвинулась, снимаем обрезку: иначе она срезала бы подсказку к закреплению.
  if (animate) setTimeout(() => node.classList.remove('grow-in'), 400);

  const row = { node, share, name, note, pin, pinHolder, pinTip, toggle, item };

  pin.addEventListener('click', () => {
    const pinned = !row.item.pinned;
    run(view, () =>
      api(`/editor/streams/${view.id}/offers/${row.item.offer_id}/pin`, { method: 'PUT', body: { pinned } }),
    );
  });

  toggle.addEventListener('click', () => {
    const { offer_id: offerId, removed } = row.item;
    const title = offerTitle({ id: offerId, name: row.item.name });
    if (removed) {
      run(view, () => api(`/editor/streams/${view.id}/offers/${offerId}/restore`, { method: 'POST' }), `Оффер «${title}» возвращён, доли пересчитаны.`);
    } else {
      run(view, () => api(`/editor/streams/${view.id}/offers/${offerId}`, { method: 'DELETE' }), `Оффер «${title}» убран, доли пересчитаны.`);
    }
  });

  return row;
}

function updateRow(row, item, instant) {
  row.item = item;
  row.node.classList.toggle('is-removed', item.removed);
  row.node.classList.toggle('is-unsent', ['new', 'changed', 'removing'].includes(item.status));

  const shareText = `${item.share}%`;
  const noteText = offerNote(item);
  if (instant) {
    row.share.textContent = shareText;
    row.note.textContent = noteText;
  } else {
    setText(row.share, shareText);
    setText(row.note, noteText);
  }

  row.name.textContent = offerTitle({ id: item.offer_id, name: item.name });
  row.name.title = item.name;

  row.pinHolder.hidden = item.removed;
  row.pin.setAttribute('aria-pressed', String(item.pinned));
  row.pin.setAttribute('aria-label', item.pinned ? 'Открепить долю' : 'Закрепить долю');
  row.pinTip.textContent = item.pinned ? PIN_ON : PIN_OFF;

  row.toggle.textContent = item.removed ? 'Вернуть' : 'Убрать';
  row.toggle.classList.toggle('btn-quiet', item.removed);
  row.toggle.classList.toggle('btn-ghost', !item.removed);
  row.toggle.classList.toggle('btn-danger', !item.removed);
}

// Поток -----------------------------------------------------------------------

function renderOffers(view, offers, { initial = false } = {}) {
  view.offers = offers;

  const seen = new Set();
  let previous = null;
  for (const item of offers.items) {
    let row = view.rows.get(item.offer_id);
    const isNew = !row;
    if (!row) {
      row = createRow(view, item, !initial);
      view.rows.set(item.offer_id, row);
    }
    updateRow(row, item, initial || isNew);
    const place = previous ? previous.nextSibling : view.list.firstChild;
    if (place !== row.node) view.list.insertBefore(row.node, place);
    previous = row.node;
    seen.add(item.offer_id);
  }
  for (const [offerId, row] of view.rows) {
    if (!seen.has(offerId)) {
      row.node.remove();
      view.rows.delete(offerId);
    }
  }

  const active = offers.items.filter((item) => !item.removed);
  syncUnsent(view);

  const notes = [];
  if (active.length && offers.total !== 100) {
    notes.push(`Сумма долей ${offers.total}%. Keitaro делит посетителей пропорционально долям.`);
  }
  if (active.some((item) => item.share === 0)) {
    notes.push('Оффер с долей 0% не получит посетителей: закреплённые доли заняли все 100%.');
  }
  view.note.textContent = notes.join(' ');
  view.note.hidden = !notes.length;

  view.empty.hidden = offers.items.length > 0;
}

/**
 * Полоса с неотправленными изменениями. Последствие отправки написано до нажатия кнопки.
 * Сразу после отправки полоса ещё секунду держится открытой (view.holdUnsent),
 * чтобы человек увидел галочку и слова «Отправлено в Keitaro», и только потом сворачивается.
 */
function syncUnsent(view) {
  const offers = view.offers;
  const open = offers.unsent || view.holdUnsent;
  view.unsent.classList.toggle('is-open', open);
  view.unsent.inert = !open;
  if (!offers.unsent) return; // текст не трогаем: полоса либо закрыта, либо показывает «Отправлено»

  view.unsentTitle.textContent = 'Изменения не отправлены. ';
  if (!offers.items.some((item) => !item.removed)) {
    view.unsentTail.textContent = 'После отправки в потоке не останется офферов, посетителям будет некуда идти.';
  } else if (!view.servesOffers) {
    view.unsentTail.textContent = 'Сейчас поток офферы не раздаёт. После отправки начнёт.';
  } else {
    view.unsentTail.textContent = 'В Keitaro пока прежний состав офферов.';
  }
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function setError(view, message) {
  view.error.textContent = message ?? '';
  view.error.hidden = !message;
}

/** Выполняет одно действие над потоком: пока идёт запрос, остальные кнопки потока не работают. */
async function run(view, request, announce = '') {
  if (view.busy) return false;
  view.busy = true;
  view.section.setAttribute('aria-busy', 'true');
  setError(view, null);
  try {
    renderOffers(view, await request());
    if (announce) live.textContent = announce;
    return true;
  } catch (error) {
    setError(view, error.message);
    return false;
  } finally {
    view.busy = false;
    view.section.setAttribute('aria-busy', 'false');
  }
}

function unsentBar(view) {
  const bar = el('div', 'fold unsent');
  bar.inert = true;
  const inner = el('div', 'fold-inner');
  const body = el('div', 'unsent-body');
  const text = el('p');
  view.unsentTitle = el('strong', '', 'Изменения не отправлены. ');
  view.unsentTail = el('span');
  text.append(view.unsentTitle, view.unsentTail);

  const actions = el('div', 'unsent-actions');
  const push = button('Отправить в Keitaro', 'btn-primary btn-small', { spinner: true });
  const cancel = button('Отменить', 'btn-quiet btn-small');
  actions.append(push, cancel);
  body.append(text, actions);
  inner.append(body);
  bar.append(inner);

  push.addEventListener('click', async () => {
    const willServe = view.offers.items.some((item) => !item.removed);
    setBusy(push, true);
    cancel.disabled = true;
    view.holdUnsent = true; // полоса не сворачивается, пока не покажем результат
    const done = await run(view, () => api(`/editor/streams/${view.id}/push`, { method: 'POST' }), 'Изменения отправлены в Keitaro.');

    if (done) {
      if (willServe) view.servesOffers = true;
      // Вертушку на кнопке сменяет галочка, рядом слова «Отправлено в Keitaro».
      view.unsentTitle.textContent = 'Отправлено в Keitaro.';
      view.unsentTail.textContent = '';
      await showDone(push);
    }

    // Теперь полоса плавно сворачивается (если за эту секунду не появилось новых изменений).
    view.holdUnsent = false;
    syncUnsent(view);
    if (done && !view.offers.unsent) await wait(320);
    resetButton(push);
    cancel.disabled = false;
  });
  cancel.addEventListener('click', () => {
    run(view, () => api(`/editor/streams/${view.id}/cancel`, { method: 'POST' }), 'Изменения отменены.');
  });

  return bar;
}

function addField(view) {
  const field = el('div', 'field add-offer');
  const input = el('input', 'input');
  input.type = 'text';
  input.id = `add-${view.id}`;
  input.autocomplete = 'off';
  input.spellcheck = false;
  input.placeholder = 'Название или номер оффера';

  const labelRow = el('div', 'label-row');
  const label = el('label', '', 'Добавить оффер');
  label.htmlFor = input.id;
  const hint = view.servesOffers
    ? 'Доли делятся поровну между офферами. Закреплённая доля не меняется, когда вы добавляете или убираете офферы.'
    : 'Сейчас этот поток офферы не раздаёт. Когда вы добавите оффер и отправите изменения, поток начнёт отправлять посетителей на офферы вместо прежнего действия.';
  const [info, tip] = infoTip(hint, `add-hint-${view.id}`, 'Подсказка про добавление оффера');
  input.setAttribute('aria-describedby', tip.id);
  labelRow.append(label, info, tip);

  const combo = el('div', 'combo');
  const list = el('ul', 'listbox');
  list.id = `add-list-${view.id}`;
  list.setAttribute('role', 'listbox');
  list.setAttribute('aria-label', 'Офферы');
  combo.append(input, list);
  field.append(labelRow, combo);

  attachListbox({
    input,
    list,
    debounce: 160,
    async source(query, signal) {
      const result = await api(`/offers?limit=30&q=${encodeURIComponent(query)}`, { signal });
      // Офферы, которые уже в потоке, второй раз не предлагаем. Убранные предлагаем: так их можно вернуть.
      const taken = new Set(view.offers.items.filter((item) => !item.removed).map((item) => item.offer_id));
      const items = result.items.filter((offer) => !taken.has(offer.id));
      return {
        items,
        hint: result.total > result.items.length ? `Показаны первые ${result.items.length} из ${result.total}. Уточните запрос.` : '',
        emptyText: result.items.length ? 'Все найденные офферы уже в потоке.' : 'Таких офферов нет. Попробуйте другое слово или номер.',
      };
    },
    renderOption(element, offer) {
      const name = el('span', 'option-main', offerTitle(offer));
      name.title = offer.name;
      element.append(el('span', 'mono option-id', String(offer.id)), name, el('span', 'mono option-side', shortList(offer.countries, 2)));
    },
    onPick(offer) {
      input.value = '';
      run(
        view,
        () => api(`/editor/campaigns/${campaignId}/streams/${view.id}/offers`, { method: 'POST', body: { offer_id: offer.id } }),
        `Оффер «${offerTitle(offer)}» добавлен, доли пересчитаны.`,
      );
    },
  });

  return { field, input };
}

function streamSection(stream, index) {
  const section = el('section', 'stream');
  section.setAttribute('aria-busy', 'false');
  const view = {
    id: stream.id,
    section,
    rows: new Map(),
    busy: false,
    holdUnsent: false,
    offers: null,
    servesOffers: stream.serves_offers,
  };

  const head = el('header', 'stream-head');
  const title = el('h2', '', stream.name);
  if (stream.state !== 'active') title.append(' ', el('span', 'tag', 'выключен'));
  head.append(title, el('p', 'stream-who', `Поток ${index + 1}`));

  view.unsent = unsentBar(view);
  view.error = el('p', 'form-error');
  view.error.hidden = true;
  view.error.setAttribute('role', 'alert');
  view.list = el('ul', 'offers');
  view.empty = el('p', 'stream-plain', 'В этом потоке нет офферов.');
  view.note = el('p', 'stream-note');
  view.note.hidden = true;

  const { field, input } = addField(view);
  section.append(head, view.unsent, view.error, view.list, view.empty, view.note);

  // В пустой поток оффер добавляют редко, поэтому поле поиска открывается по кнопке.
  // У потока с офферами оно на виду: это главное действие страницы.
  if (stream.offers.items.length === 0) {
    const reveal = button('Добавить оффер', 'btn-quiet btn-small add-reveal', { iconBefore: 'plus' });
    reveal.addEventListener('click', () => {
      reveal.replaceWith(field);
      input.focus();
    });
    const holder = el('div');
    holder.append(reveal);
    section.append(holder);
  } else {
    section.append(field);
  }

  renderOffers(view, stream.offers, { initial: true });
  return section;
}

// Страница --------------------------------------------------------------------

function renderCampaign(campaign) {
  document.title = `${campaign.name}: офферы`;
  $('campaign-name').textContent = campaign.name;
  $('campaign-link').replaceChildren(...(campaign.url ? [linkBox(campaign.url)] : []));
  $('admin-link').href = campaign.admin_url;
  $('admin-link').hidden = false;
}

async function load() {
  try {
    const data = await api(`/editor/campaigns/${campaignId}`);
    renderCampaign(data.campaign);
    if (data.streams.length) {
      streamsBox.replaceChildren(...data.streams.map(streamSection));
    } else {
      streamsBox.replaceChildren(
        el('p', 'stream-plain', 'В этой кампании нет потоков. Добавьте поток в Keitaro и нажмите «Обновить из Keitaro».'),
      );
    }
    $('sync-note').textContent = `Сверено с Keitaro в ${formatTime(new Date())}`;
    refreshButton.disabled = false;
    await reportKeitaro();
    return true;
  } catch (error) {
    if (error.status === 404) {
      $('campaign-name').textContent = 'Кампания не найдена';
      streamsBox.replaceChildren(el('p', 'stream-plain', 'В Keitaro нет кампании с таким номером. Возможно, её удалили.'));
      setConnection('ok');
    } else {
      if (!$('campaign-name').textContent.trim()) $('campaign-name').textContent = 'Кампания';
      streamsBox.replaceChildren();
      refreshButton.disabled = false;
      await reportKeitaro(error);
    }
    return false;
  } finally {
    streamsBox.setAttribute('aria-busy', 'false');
  }
}

refreshButton.addEventListener('click', async () => {
  setBusy(refreshButton, true);
  const done = await load();
  if (done) {
    live.textContent = 'Состав потоков обновлён из Keitaro.';
    flashDone(refreshButton); // вертушку сменяет галочка, потом возвращается подпись
  } else {
    setBusy(refreshButton, false);
  }
});

$('banner-retry').addEventListener('click', () => {
  setConnection('checking');
  load();
});

load();
