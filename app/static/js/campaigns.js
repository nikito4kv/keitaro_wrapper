// Страница «Все кампании»: список из Keitaro, по щелчку открывается редактор офферов.

import { api } from './api.js';
import { $, el, formatTrackerDate, reportKeitaro, searchKey, setBusy, setConnection } from './ui.js';

const PAGE = 100;

const rows = $('rows');
const searchInput = $('search-input');
const moreButton = $('more');

let campaigns = [];
let hasMore = false;

function campaignRow(campaign, index) {
  const item = el('li', 'row is-initial');
  item.style.setProperty('--i', String(Math.min(index, 10)));

  const link = el('a', 'row-link');
  link.href = `/campaigns/${campaign.id}`;

  const main = el('span', 'row-main');
  main.append(el('span', 'row-title', campaign.name));
  const created = formatTrackerDate(campaign.created_at);
  const meta = el('span', 'row-meta');
  meta.append(el('span', 'mono', `№ ${campaign.id}`));
  if (created) meta.append(el('span', '', `создана ${created}`));
  if (campaign.state !== 'active') meta.append(el('span', 'tag', 'выключена'));
  main.append(meta);

  link.append(main, el('span', 'row-go', 'Изменить офферы'));
  item.append(link);
  return item;
}

function render() {
  const key = searchKey(searchInput.value);
  const visible = key
    ? campaigns.filter((campaign) => searchKey(`${campaign.id} ${campaign.name}`).includes(key))
    : campaigns;

  rows.replaceChildren(...visible.map(campaignRow));
  rows.setAttribute('aria-busy', 'false');
  $('empty').hidden = campaigns.length > 0;
  $('nothing-found').hidden = !(campaigns.length > 0 && visible.length === 0);
  // Поиск нужен, когда строк уже много. До того он только занимает место.
  $('search-field').hidden = campaigns.length < 8 && !key;
  // Поиск идёт по уже загруженным кампаниям, поэтому «ещё» при поиске тоже полезно.
  moreButton.hidden = !hasMore;
}

async function load({ append = false } = {}) {
  try {
    const page = await api(`/editor/campaigns?limit=${PAGE}&offset=${append ? campaigns.length : 0}`);
    campaigns = append ? [...campaigns, ...page.items] : page.items;
    hasMore = page.has_more;
    await reportKeitaro();
    render();
  } catch (error) {
    rows.replaceChildren();
    rows.setAttribute('aria-busy', 'false');
    await reportKeitaro(error);
  }
}

searchInput.addEventListener('input', render);

moreButton.addEventListener('click', async () => {
  setBusy(moreButton, true, 'Загружаем');
  await load({ append: true });
  setBusy(moreButton, false, 'Показать ещё');
});

$('banner-retry').addEventListener('click', () => {
  setConnection('checking', 'Проверяем связь с Keitaro');
  load();
});

load();
