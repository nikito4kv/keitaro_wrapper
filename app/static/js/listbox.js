// Поле с выпадающим списком подсказок. Работает и мышью, и клавиатурой:
// стрелки ходят по списку, Enter выбирает, Esc закрывает.

export function attachListbox({ input, list, source, renderOption, onPick, onEnter, debounce = 0 }) {
  let options = [];
  let active = -1;
  let isOpen = false;
  let timer = 0;
  let controller = null;
  let requestNo = 0;

  input.setAttribute('role', 'combobox');
  input.setAttribute('aria-autocomplete', 'list');
  input.setAttribute('aria-expanded', 'false');
  input.setAttribute('aria-controls', list.id);
  // Прокручиваемый список браузер считает остановкой для Tab. Нам это не нужно:
  // по списку ходят стрелками из поля, а Tab должен вести к следующему полю.
  list.tabIndex = -1;

  function setOpen(value) {
    if (isOpen === value) return;
    isOpen = value;
    list.classList.toggle('is-open', value);
    input.setAttribute('aria-expanded', String(value));
    if (!value) input.removeAttribute('aria-activedescendant');
  }

  function setActive(index, { scroll = true } = {}) {
    list.querySelector('.is-active')?.classList.remove('is-active');
    active = index;
    const element = list.querySelector(`[data-index="${index}"]`);
    if (!element) {
      input.removeAttribute('aria-activedescendant');
      return;
    }
    element.classList.add('is-active');
    input.setAttribute('aria-activedescendant', element.id);
    if (scroll) element.scrollIntoView({ block: 'nearest' });
  }

  function note(text, isError = false) {
    const item = document.createElement('li');
    item.className = isError ? 'listbox-note is-error' : 'listbox-note';
    item.setAttribute('role', 'presentation');
    item.textContent = text;
    return item;
  }

  function showOnly(text, isError = false) {
    options = [];
    list.replaceChildren(note(text, isError));
    setActive(-1);
  }

  function render({ items, hint = '', emptyText = 'Ничего не найдено' }, query) {
    options = items;
    if (!items.length) {
      showOnly(emptyText);
      return;
    }
    const nodes = items.map((item, index) => {
      const element = document.createElement('li');
      element.className = 'option';
      element.id = `${list.id}-${index}`;
      element.dataset.index = String(index);
      element.setAttribute('role', 'option');
      renderOption(element, item, query);
      return element;
    });
    if (hint) nodes.push(note(hint));
    list.replaceChildren(...nodes);
    list.scrollTop = 0;
    setActive(0, { scroll: false });
  }

  async function load() {
    const query = input.value.trim();
    controller?.abort();
    controller = new AbortController();
    const myNo = ++requestNo;
    let slowTimer = 0;
    try {
      let result = source(query, controller.signal);
      if (result instanceof Promise) {
        // Слово «Ищем» показываем, только если ответ и правда задерживается.
        slowTimer = setTimeout(() => {
          if (myNo === requestNo && !options.length) showOnly('Ищем…');
        }, 300);
        result = await result;
      }
      if (myNo === requestNo) render(result, query);
    } catch (error) {
      if (error.name === 'AbortError' || myNo !== requestNo) return;
      showOnly(error.message || 'Не удалось загрузить список.', true);
    } finally {
      clearTimeout(slowTimer);
    }
  }

  function open() {
    setOpen(true);
    load();
  }

  function pick(item) {
    const keepOpen = onPick(item) === 'keep';
    if (keepOpen) load();
    else setOpen(false);
  }

  // Когда человек возвращается в окно браузера, поле заново получает фокус.
  // Список в этот момент открывать нельзя: он выскочит под курсор, и щелчок
  // по соседнему полю выберет случайную строку.
  let returningToWindow = false;
  window.addEventListener('blur', () => {
    returningToWindow = true;
  });
  window.addEventListener('focus', () => {
    setTimeout(() => {
      returningToWindow = false;
    }, 0);
  });

  // Фокус «без списка»: когда поле подсвечено из-за ошибки, список закрыл бы её текст.
  let quietFocus = false;

  input.addEventListener('focus', () => {
    if (!returningToWindow && !quietFocus) open();
  });
  input.addEventListener('click', () => {
    if (!isOpen) open();
  });
  input.addEventListener('blur', () => setOpen(false));

  input.addEventListener('input', () => {
    setOpen(true);
    clearTimeout(timer);
    if (debounce) timer = setTimeout(load, debounce);
    else load();
  });

  input.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!isOpen) {
        open();
        return;
      }
      if (!options.length) return;
      const step = event.key === 'ArrowDown' ? 1 : -1;
      setActive(Math.max(0, Math.min(options.length - 1, active + step)));
    } else if (event.key === 'Enter') {
      // Enter в таком поле выбирает вариант и никогда не отправляет форму.
      event.preventDefault();
      if (onEnter?.(input.value)) return;
      if (isOpen && active >= 0) pick(options[active]);
    } else if (event.key === 'Escape' && isOpen) {
      event.stopPropagation();
      setOpen(false);
    }
  });

  // Нажатие по списку не должно забирать фокус у поля.
  list.addEventListener('mousedown', (event) => event.preventDefault());
  list.addEventListener('click', (event) => {
    const element = event.target.closest('.option');
    if (element) pick(options[Number(element.dataset.index)]);
  });
  list.addEventListener('mousemove', (event) => {
    const element = event.target.closest('.option');
    if (element && Number(element.dataset.index) !== active) {
      setActive(Number(element.dataset.index), { scroll: false });
    }
  });

  return {
    reload: load,
    close: () => setOpen(false),
    /** Ставит курсор в поле, не раскрывая список. Список откроется, когда человек начнёт печатать. */
    focusQuietly() {
      quietFocus = true;
      input.focus();
      quietFocus = false;
    },
  };
}
