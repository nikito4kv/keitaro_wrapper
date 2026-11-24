import { api } from './api.js';
import { attachListbox } from './listbox.js';
import {
  $,
  button,
  el,
  linkBox,
  formatDate,
  offerTitle,
  regionNames,
  searchKey,
  flashDone,
  resetButton,
  setBusy,
  setConnection,
  showDone,
  shortList,
  showBanner,
} from './ui.js';

const state = {
  countries: [], // все страны: { code, name, key }
  picked: [], // выбранные страны, в порядке выбора
  offer: null, // выбранный оффер
  defaults: null, // домен, группа и источник по умолчанию
  reference: null, // справочники Keitaro для окна настроек
  redirectHost: 'google.com',
  busy: false,
};

const form = $('campaign-form');
const nameInput = $('name-input');
const countriesInput = $('countries-input');
const countriesBox = $('countries-box');
const offerInput = $('offer-input');
const submitButton = $('submit');

// Мелочи ----------------------------------------------------------------

const countryName = (code) => state.countries.find((country) => country.code === code)?.name ?? code;

// Ошибки полей ------------------------------------------------------------

const errorSlots = { name: 'name-error', countries: 'countries-error', offer_id: 'offer-error' };

function setFieldError(field, message) {
  const holder = document.querySelector(`[data-field="${field}"]`);
  holder?.classList.toggle('is-invalid', Boolean(message));
  const slot = $(errorSlots[field]);
  if (slot) {
    slot.textContent = message ?? '';
    slot.hidden = !message;
  }
}

function setFormError(message) {
  $('form-error').textContent = message ?? '';
  $('form-error').hidden = !message;
}

function clearErrors() {
  ['name', 'countries', 'offer_id', 'defaults'].forEach((field) => setFieldError(field, null));
  setFormError(null);
}

// Страны ------------------------------------------------------------------

function findCountries(query) {
  const free = state.countries.filter((country) => !state.picked.includes(country.code));
  const key = searchKey(query);
  if (!key) return free;

  const rank = (country) => {
    if (country.code.toLowerCase() === key) return 0;
    if (country.key.startsWith(key)) return 1;
    if (country.key.split(/[\s-]+/).some((word) => word.startsWith(key))) return 2;
    if (country.code.toLowerCase().startsWith(key)) return 3;
    if (country.key.includes(key)) return 4;
    return -1;
  };
  return free
    .map((country) => ({ country, rank: rank(country) }))
    .filter((entry) => entry.rank >= 0)
    .sort((a, b) => a.rank - b.rank)
    .map((entry) => entry.country);
}

function addCountry(code) {
  if (state.picked.includes(code)) return;
  state.picked.push(code);

  const chip = document.createElement('span');
  chip.className = 'chip';
  chip.dataset.code = code;

  const name = document.createElement('span');
  name.textContent = countryName(code);
  const codeLabel = document.createElement('span');
  codeLabel.className = 'mono chip-code';
  codeLabel.textContent = code;
  const remove = document.createElement('button');
  remove.type = 'button';
  remove.className = 'chip-x';
  remove.textContent = '×';
  remove.setAttribute('aria-label', `Убрать страну ${countryName(code)}`);
  remove.addEventListener('click', () => {
    removeCountry(code);
    countriesInput.focus();
  });

  chip.append(name, codeLabel, remove);
  countriesBox.insertBefore(chip, countriesInput);
  setFieldError('countries', null);
  renderPlan();
}

function removeCountry(code) {
  state.picked = state.picked.filter((item) => item !== code);
  countriesBox.querySelector(`.chip[data-code="${code}"]`)?.remove();
  renderPlan();
}

/**
 * Разбирает вставленный список кодов вроде «MX, AU, RO».
 * Узнанные коды становятся странами, неузнанные остаются в поле, чтобы их было видно.
 */
function addCountriesFromText(text) {
  const tokens = text.split(/[\s,;]+/).filter(Boolean);
  const known = new Set(state.countries.map((country) => country.code));
  const unknown = [];
  for (const token of tokens) {
    const code = token.toUpperCase();
    if (known.has(code)) addCountry(code);
    else unknown.push(token);
  }
  countriesInput.value = unknown.join(', ');
  setFieldError('countries', unknown.length ? `Не узнали коды: ${unknown.join(', ')}. Найдите страну по названию.` : null);
}

const looksLikeCodeList = (text) => /^\s*[a-z]{2}(\s*[\s,;]\s*[a-z]{2})+[\s,;]*$/i.test(text);

const countriesList = attachListbox({
  input: countriesInput,
  list: $('countries-list'),
  source: (query) => ({ items: findCountries(query), emptyText: 'Такой страны нет в списке' }),
  renderOption(element, country) {
    const name = document.createElement('span');
    name.className = 'option-main';
    name.textContent = country.name;
    const code = document.createElement('span');
    code.className = 'mono option-side';
    code.textContent = country.code;
    element.append(name, code);
  },
  onPick(country) {
    countriesInput.value = '';
    addCountry(country.code);
    // Список после выбора закрывается: открытым он лежал поверх поля «Оффер», и щелчок
    // по этому полю добавлял случайную страну. Чтобы выбрать ещё одну, достаточно начать печатать.
  },
});

countriesInput.addEventListener('paste', (event) => {
  const text = event.clipboardData?.getData('text') ?? '';
  if (!looksLikeCodeList(text)) return;
  event.preventDefault();
  addCountriesFromText(text);
  countriesList.close(); // иначе список закрыл бы сообщение о неузнанных кодах
});

countriesInput.addEventListener('input', () => {
  // Набрали код и поставили запятую: сразу превращаем в страну.
  if (/[,;]/.test(countriesInput.value)) {
    addCountriesFromText(countriesInput.value);
    countriesList.close(); // иначе список закрыл бы сообщение о неузнанных кодах
  } else {
    setFieldError('countries', null);
  }
});

countriesInput.addEventListener('keydown', (event) => {
  if (event.key === 'Backspace' && !countriesInput.value && state.picked.length) {
    removeCountry(state.picked.at(-1));
    countriesList.reload();
  }
});

countriesBox.addEventListener('mousedown', (event) => {
  // Щелчок по свободному месту рамки ставит курсор в поле.
  if (event.target === countriesBox) {
    event.preventDefault();
    countriesInput.focus();
  }
});

// Оффер -------------------------------------------------------------------

function setOffer(offer) {
  state.offer = offer;
  $('offer-picked').hidden = !offer;
  offerInput.hidden = Boolean(offer);
  if (offer) {
    $('offer-picked-id').textContent = offer.id;
    $('offer-picked-name').textContent = offerTitle(offer);
    $('offer-picked-name').title = offer.name;
    setFieldError('offer_id', null);
  }
  offerInput.value = '';
  renderPlan();
}

const offersList = attachListbox({
  input: offerInput,
  list: $('offer-list'),
  debounce: 160,
  async source(query, signal) {
    const result = await api(`/offers?limit=20&q=${encodeURIComponent(query)}`, { signal });
    const more = result.total > result.items.length;
    return {
      items: result.items,
      hint: more ? `Показаны первые ${result.items.length} из ${result.total}. Уточните запрос.` : '',
      emptyText: 'Таких офферов нет. Попробуйте другое слово или номер.',
    };
  },
  renderOption(element, offer) {
    const id = document.createElement('span');
    id.className = 'mono option-id';
    id.textContent = offer.id;
    const name = document.createElement('span');
    name.className = 'option-main';
    name.textContent = offerTitle(offer);
    name.title = offer.name;
    const countries = document.createElement('span');
    countries.className = 'mono option-side';
    countries.textContent = shortList(offer.countries, 2);
    element.append(id, name, countries);
  },
  onPick(offer) {
    setOffer(offer);
    $('offer-clear').focus();
  },
});

$('offer-clear').addEventListener('click', () => {
  setOffer(null);
  offerInput.focus();
});

// Что будет создано -------------------------------------------------------

function renderPlan() {
  const geo = $('plan-geo');
  geo.classList.toggle('is-empty', !state.picked.length);
  geo.textContent = state.picked.length ? shortList(state.picked.map(countryName), 4) : 'страны не выбраны';

  const offer = $('plan-offer');
  offer.classList.toggle('is-empty', !state.offer);
  offer.textContent = state.offer ? `${state.offer.id} ${offerTitle(state.offer)}` : 'оффер не выбран';
}

// Домен, группа и источник ------------------------------------------------

function renderDefaults() {
  const defaults = state.defaults;
  $('defaults-rows').hidden = !defaults;
  $('defaults-empty').hidden = Boolean(defaults);
  $('defaults-edit').textContent = defaults ? 'Изменить' : 'Выбрать';
  if (defaults) {
    $('defaults-domain').textContent = defaults.domain.name;
    $('defaults-group').textContent = defaults.group.name;
    $('defaults-source').textContent = defaults.traffic_source.name;
    setFieldError('defaults', null);
  }
}

const dialog = $('defaults-dialog');
const selects = {
  domain: $('domain-select'),
  group: $('group-select'),
  source: $('source-select'),
};

function fillSelect(select, items, currentId) {
  const options = items.map((item) => new Option(item.name, item.id));
  // Если выбирать не из чего (вариант один), подставляем его сразу.
  const preselected = currentId ?? (items.length === 1 ? items[0].id : null);
  if (preselected === null || !items.some((item) => item.id === preselected)) {
    const placeholder = new Option(items.length ? 'Выберите' : 'В Keitaro пока ничего нет', '');
    placeholder.disabled = true;
    placeholder.selected = true;
    options.unshift(placeholder);
  }
  select.replaceChildren(...options);
  if (preselected !== null) select.value = String(preselected);
}

function setDialogError(message) {
  $('dialog-error').textContent = message ?? '';
  $('dialog-error').hidden = !message;
}

async function openDefaults() {
  setDialogError(null);
  const saveButton = $('defaults-save');
  const ready = Boolean(state.reference);
  fillDialog();
  saveButton.disabled = !ready;
  dialog.showModal();
  if (ready) return;
  try {
    await loadReference();
    fillDialog();
    saveButton.disabled = false;
  } catch (error) {
    setDialogError(error.message);
  }
}

function fillDialog() {
  const reference = state.reference ?? { domains: [], groups: [], traffic_sources: [] };
  fillSelect(selects.domain, reference.domains, state.defaults?.domain.id);
  fillSelect(selects.group, reference.groups, state.defaults?.group.id);
  fillSelect(selects.source, reference.traffic_sources, state.defaults?.traffic_source.id);
}

$('defaults-edit').addEventListener('click', openDefaults);
$('defaults-cancel').addEventListener('click', () => dialog.close());

$('defaults-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!selects.domain.value || !selects.group.value || !selects.source.value) {
    setDialogError('Выберите домен, группу и источник.');
    return;
  }
  const saveButton = $('defaults-save');
  setDialogError(null);
  setBusy(saveButton, true);
  try {
    state.defaults = await api('/defaults', {
      method: 'PUT',
      body: {
        domain_id: Number(selects.domain.value),
        group_id: Number(selects.group.value),
        traffic_source_id: Number(selects.source.value),
      },
    });
    renderDefaults();
    // Галочка на кнопке, и только потом окно закрывается: видно, что сохранилось.
    await showDone(saveButton, 600);
    dialog.close();
    resetButton(saveButton);
  } catch (error) {
    setDialogError(error.message);
    setBusy(saveButton, false);
  }
});

// Связь с Keitaro ---------------------------------------------------------

async function loadReference() {
  try {
    state.reference = await api('/reference');
    $('banner').hidden = true;
    setConnection('ok', state.keitaroHost);
    return state.reference;
  } catch (error) {
    setConnection('fail', state.keitaroHost);
    showBanner(error.message);
    throw error;
  }
}

$('banner-retry').addEventListener('click', async () => {
  const button = $('banner-retry');
  button.disabled = true;
  setConnection('checking');
  try {
    await loadReference();
  } catch {
    // Плашка уже показывает причину.
  } finally {
    button.disabled = false;
  }
});

// Созданные кампании ------------------------------------------------------

function campaignRow(campaign, { fresh = false, index = 0 } = {}) {
  const row = document.createElement('li');
  row.className = fresh ? 'camp is-fresh' : 'camp is-initial';
  row.style.setProperty('--i', String(Math.min(index, 8)));

  const body = el('div', 'camp-body');

  const head = el('div', 'camp-head');
  const time = el('time', '', formatDate(new Date(campaign.created_at)));
  time.dateTime = campaign.created_at;
  head.append(el('h3', '', campaign.name), time);

  // Потоки показаны так же, как в блоке «Что будет создано» слева: один вид для одного понятия.
  const host = new URL(campaign.redirect_url).host;
  const flows = el('dl', 'flows');
  const offerName = offerTitle({ id: campaign.offer_id, name: campaign.offer_name });
  for (const [title, text] of [
    ['Поток 1', `${shortList(campaign.countries.map(countryName), 3)} → ${host}`],
    ['Поток 2', `остальные → ${offerName}`],
  ]) {
    const line = el('div');
    line.append(el('dt', '', title), el('dd', '', text));
    flows.append(line);
  }

  const actions = el('div', 'camp-actions');
  actions.append(
    linkBox(campaign.url),
    button('Изменить офферы', 'btn-quiet btn-small', { href: `/campaigns/${campaign.keitaro_campaign_id}` }),
    button('Keitaro', 'btn-ghost btn-small', { href: campaign.admin_url, iconAfter: 'external' }),
  );
  actions.lastChild.title = 'Открыть кампанию в админке Keitaro';

  body.append(head, flows, actions);
  const clip = el('div', 'clip');
  clip.append(body);
  row.append(clip);
  return row;
}

async function loadCampaigns() {
  const list = $('camps');
  try {
    const campaigns = await api('/campaigns');
    list.replaceChildren(...campaigns.map((campaign, index) => campaignRow(campaign, { index })));
    $('camps-empty').hidden = campaigns.length > 0;
    $('camps-error').hidden = true;
  } catch (error) {
    list.replaceChildren();
    $('camps-error').textContent = error.message;
    $('camps-error').hidden = false;
  } finally {
    list.setAttribute('aria-busy', 'false');
  }
}

// Создание кампании -------------------------------------------------------

function validate() {
  clearErrors();
  // Каждая проблема: поле, текст ошибки и способ поставить туда курсор.
  // В поля со списком курсор ставится «тихо», чтобы раскрывшийся список не закрыл текст ошибки.
  const problems = [];
  if (!nameInput.value.trim()) problems.push(['name', 'Введите название кампании.', () => nameInput.focus()]);

  // Текст, который остался в поле стран и не стал страной (например, UK вместо GB), нельзя молча
  // отбросить: кампания создалась бы без этой страны, а в Keitaro это уже не отменить.
  const leftover = countriesInput.value.trim();
  if (leftover) {
    problems.push([
      'countries',
      `«${leftover}» не стало страной. Выберите страну из подсказок или сотрите этот текст.`,
      () => countriesList.focusQuietly(),
    ]);
  } else if (!state.picked.length) {
    problems.push(['countries', 'Выберите хотя бы одну страну.', () => countriesList.focusQuietly()]);
  }

  if (!state.offer) problems.push(['offer_id', 'Выберите оффер из списка.', () => offersList.focusQuietly()]);
  if (!state.defaults) {
    problems.push(['defaults', 'Выберите домен, группу и источник.', () => $('defaults-edit').focus()]);
  }

  problems.forEach(([field, message]) => setFieldError(field, message));
  problems[0]?.[2]();
  return problems.length === 0;
}

function resetForm() {
  nameInput.value = '';
  [...state.picked].forEach(removeCountry);
  countriesInput.value = '';
  setOffer(null);
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (state.busy || !validate()) return;

  state.busy = true;
  setBusy(submitButton, true);
  let created = false;
  try {
    const campaign = await api('/campaigns', {
      method: 'POST',
      body: { name: nameInput.value, countries: state.picked, offer_id: state.offer.id },
    });
    $('camps-empty').hidden = true;
    const row = campaignRow(campaign, { fresh: true });
    $('camps').prepend(row);
    $('live').textContent = `Кампания «${campaign.name}» создана.`;
    created = true;
    resetForm();
    if (window.matchMedia('(max-width: 920px)').matches) {
      row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      nameInput.focus();
    }
  } catch (error) {
    const fields = error.fields ?? {};
    const known = Object.keys(fields).filter((field) => field in errorSlots);
    known.forEach((field) => setFieldError(field, fields[field]));
    if ('defaults' in fields) setFieldError('defaults', fields.defaults);
    if (!known.length) setFormError(error.message);
    else document.querySelector('.field.is-invalid input')?.focus();
  } finally {
    state.busy = false;
    // После успеха вертушку сменяет галочка, потом возвращается подпись.
    if (created) flashDone(submitButton);
    else setBusy(submitButton, false);
  }
});

nameInput.addEventListener('input', () => setFieldError('name', null));

// Запуск ------------------------------------------------------------------

async function start() {
  let boot;
  try {
    boot = await api('/bootstrap');
  } catch (error) {
    setConnection('fail');
    showBanner(error.message);
    $('banner-retry').hidden = true;
    $('camps').replaceChildren();
    return;
  }

  state.countries = boot.countries
    .map((code) => {
      const name = regionNames.of(code) ?? code;
      return { code, name, key: searchKey(name) };
    })
    .sort((a, b) => a.name.localeCompare(b.name, 'ru'));
  state.defaults = boot.defaults;
  state.redirectHost = new URL(boot.redirect_url).host;
  state.keitaroHost = boot.keitaro_url ? new URL(boot.keitaro_url).host : '';

  document.querySelectorAll('[data-redirect-host]').forEach((node) => {
    node.textContent = state.redirectHost;
  });
  renderDefaults();
  renderPlan();

  loadCampaigns();
  loadReference().catch(() => {});
}

start();
