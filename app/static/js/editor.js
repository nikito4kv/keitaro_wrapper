// Редактор офферов кампании.
//
// Кнопки «Добавить», «Убрать», «Вернуть» и «Закрепить» меняют только черновик на нашем сервере.
// В Keitaro состав потока уходит по кнопке «Отправить в Keitaro». Все цифры считает сервер,
// страница только показывает то, что он вернул.

import { api } from './api.js';
import { attachListbox } from './listbox.js';
import {
  $,
  copyButton,
  el,
  formatTime,
  offerTitle,
  regionNames,
  reportKeitaro,
  setBusy,
  setConnection,
  setText,
  shortList,
} from './ui.js';

const campaignId = Number(location.pathname.split('/').filter(Boolean).pop());
const streamsBox = $('streams');
const refreshButton = $('refresh');
const live = $('live');

// Подписи ---------------------------------------------------------------------

function countryName(code) {
  try {
    return regionNames.of(code) ?? code;
  } catch {
    return code;
  }
}

/** Кому достаётся поток: словами, а не названиями фильтров. */
function audience(stream, index) {
  const country = stream.filters.find((filter) => filter.name === 'country');
  const otherFilters = stream.filters.length - (country ? 1 : 0);
  let text;
  if (country) {
    const names = shortList(country.payload.map(countryName), 5);
    text = country.mode === 'reject' ? `Все, кроме стран: ${names}` : `Посетители из стран: ${names}`;
  } else {
    text = index === 0 ? 'Все посетители' : 'Все остальные посетители';
  }
  return otherFilters ? `${text}. Других условий: ${otherFilters}` : text;
}

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

  const actions = el('div', 'offer-actions');
  const pin = el('button', 'link pin');
  pin.type = 'button';
  const toggle = el('button', 'link');
  toggle.type = 'button';
  actions.append(pin, toggle);

  inner.append(share, main, actions);
  const clip = el('div', 'clip');
  clip.append(inner);
  node.append(clip);

  const row = { node, share, name, note, pin, toggle, item };

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

function updateRow(row, item, initial) {
  row.item = item;
  row.node.classList.toggle('is-removed', item.removed);
  row.node.classList.toggle('is-unsent', ['new', 'changed', 'removing'].includes(item.status));

  const shareText = `${item.share}%`;
  const noteText = offerNote(item);
  if (initial) {
    row.share.textContent = shareText;
    row.note.textContent = noteText;
  } else {
    setText(row.share, shareText);
    setText(row.note, noteText);
  }

  row.name.textContent = offerTitle({ id: item.offer_id, name: item.name });
  row.name.title = item.name;

  row.pin.hidden = item.removed;
  row.pin.textContent = item.pinned ? 'Доля закреплена' : 'Закрепить долю';
  row.pin.setAttribute('aria-pressed', String(item.pinned));

  row.toggle.textContent = item.removed ? 'Вернуть' : 'Убрать';
  row.toggle.classList.toggle('danger', !item.removed);
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

  view.unsent.classList.toggle('is-open', offers.unsent);
  view.unsent.inert = !offers.unsent;
  // «Отправлено в 13:57» верно, только пока после отправки ничего не меняли.
  if (offers.unsent) view.status.hidden = true;

  const active = offers.items.filter((item) => !item.removed);
  const notes = [];
  if (!active.length) {
    notes.push('В потоке не осталось офферов. Добавьте хотя бы один, иначе отправить изменения не получится.');
  } else {
    if (offers.total !== 100) {
      notes.push(`Сумма долей ${offers.total}%. Keitaro делит посетителей пропорционально долям.`);
    }
    if (active.some((item) => item.share === 0)) {
      notes.push('Оффер с долей 0% не получит посетителей: закреплённые доли заняли все 100%.');
    }
  }
  view.note.textContent = notes.join(' ');
  view.note.hidden = !notes.length;
  view.empty.hidden = offers.items.length > 0;
}

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

function offersBlock(view, stream) {
  const block = document.createDocumentFragment();

  // Полоса с неотправленными изменениями. Появляется, когда черновик расходится с Keitaro.
  view.unsent = el('div', 'fold unsent');
  view.unsent.inert = true;
  const unsentInner = el('div', 'fold-inner');
  const unsentBody = el('div', 'unsent-body');
  const unsentText = el('p');
  unsentText.append(el('strong', '', 'Изменения ещё не отправлены. '), 'В Keitaro пока прежний состав офферов.');
  const unsentActions = el('div', 'unsent-actions');
  const push = el('button', 'btn btn-primary btn-small');
  push.type = 'button';
  push.append(el('span', 'spinner'), el('span', 'btn-label', 'Отправить в Keitaro'));
  const cancel = el('button', 'btn btn-quiet btn-small', 'Отменить');
  cancel.type = 'button';
  unsentActions.append(push, cancel);
  unsentBody.append(unsentText, unsentActions);
  unsentInner.append(unsentBody);
  view.unsent.append(unsentInner);

  push.addEventListener('click', async () => {
    setBusy(push, true, 'Отправляем');
    const done = await run(view, () => api(`/editor/streams/${view.id}/push`, { method: 'POST' }), 'Изменения отправлены в Keitaro.');
    setBusy(push, false, 'Отправить в Keitaro');
    if (done) {
      view.status.textContent = `Отправлено в Keitaro в ${formatTime(new Date())}`;
      view.status.hidden = false;
    }
  });
  cancel.addEventListener('click', () => {
    run(view, () => api(`/editor/streams/${view.id}/cancel`, { method: 'POST' }), 'Изменения отменены.');
  });

  view.error = el('p', 'form-error');
  view.error.hidden = true;
  view.error.setAttribute('role', 'alert');

  view.list = el('ul', 'offers');
  view.empty = el('p', 'stream-plain', 'В этом потоке пока нет офферов.');
  view.empty.hidden = true;
  view.note = el('p', 'hint stream-note');
  view.note.hidden = true;

  // Добавление оффера
  const field = el('div', 'field add-offer');
  const label = el('label', '', 'Добавить оффер');
  const input = el('input', 'input');
  input.type = 'text';
  input.id = `add-${view.id}`;
  input.autocomplete = 'off';
  input.spellcheck = false;
  input.placeholder = 'Название или номер';
  label.htmlFor = input.id;
  const hint = el('p', 'hint', 'Доли делятся поровну. Закреплённая доля не меняется, когда вы добавляете или убираете офферы.');
  hint.id = `add-hint-${view.id}`;
  input.setAttribute('aria-describedby', hint.id);
  const combo = el('div', 'combo');
  const list = el('ul', 'listbox');
  list.id = `add-list-${view.id}`;
  list.setAttribute('role', 'listbox');
  list.setAttribute('aria-label', 'Офферы');
  combo.append(input, list);
  field.append(label, combo, hint);

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

  block.append(view.unsent, view.error, view.list, view.empty, view.note, field);
  renderOffers(view, stream.offers, { initial: true });
  return block;
}

function streamSection(stream, index) {
  const section = el('section', 'stream');
  section.setAttribute('aria-busy', 'false');
  const view = { id: stream.id, section, rows: new Map(), busy: false, offers: null };

  const head = el('header', 'stream-head');
  const title = el('h2', '', stream.name);
  if (stream.state !== 'active') title.append(' ', el('span', 'tag', 'выключен'));
  const who = el('p', 'stream-who', `Поток ${index + 1}. ${audience(stream, index)}`);
  view.status = el('p', 'stream-status');
  view.status.hidden = true;
  head.append(title, who, view.status);
  section.append(head);

  if (stream.kind === 'offers') {
    section.append(offersBlock(view, stream));
  } else if (stream.kind === 'redirect' && stream.redirect_url) {
    const plain = el('p', 'stream-plain', 'Отправляет на ');
    plain.append(el('span', 'mono', stream.redirect_url), '. Офферов в этом потоке нет.');
    section.append(plain);
  } else {
    section.append(el('p', 'stream-plain', 'Этот поток не раздаёт офферы, менять в нём нечего.'));
  }
  return section;
}

// Страница --------------------------------------------------------------------

function renderCampaign(campaign) {
  document.title = `${campaign.name}: офферы`;
  $('campaign-name').textContent = campaign.name;

  const links = $('campaign-links');
  links.replaceChildren();
  // Ссылку кампании показываем текстом: переход по ней засчитался бы в трекере как клик.
  if (campaign.url) links.append(el('span', 'mono camp-url', campaign.url), copyButton(campaign.url));
  const admin = el('a', 'link', 'Открыть в Keitaro');
  admin.href = campaign.admin_url;
  admin.target = '_blank';
  admin.rel = 'noopener';
  links.append(admin);
}

async function load() {
  try {
    const data = await api(`/editor/campaigns/${campaignId}`);
    renderCampaign(data.campaign);
    streamsBox.replaceChildren(...data.streams.map(streamSection));
    $('no-streams').hidden = data.streams.length > 0;
    $('sync-note').textContent = `Сверено с Keitaro в ${formatTime(new Date())}`;
    refreshButton.disabled = false;
    await reportKeitaro();
    return true;
  } catch (error) {
    if (error.status === 404) {
      $('campaign-name').textContent = 'Кампания не найдена';
      streamsBox.replaceChildren(el('p', 'stream-plain', 'В Keitaro нет кампании с таким номером. Возможно, её удалили.'));
      setConnection('ok', 'Keitaro');
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
  setBusy(refreshButton, true, 'Сверяем');
  const done = await load();
  setBusy(refreshButton, false, 'Обновить из Keitaro');
  if (done) live.textContent = 'Состав потоков обновлён из Keitaro.';
});

$('banner-retry').addEventListener('click', () => {
  setConnection('checking', 'Проверяем связь с Keitaro');
  load();
});

load();
