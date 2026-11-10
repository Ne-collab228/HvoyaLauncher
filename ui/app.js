'use strict';
// ================================================================ helpers
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  if (props) for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'html') el.innerHTML = v;
    else if (k in el && !k.includes('-') && k !== 'list') el[k] = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
const $ = (s, r = document) => r.querySelector(s);
const fmtNum = n => n >= 1e6 ? (n / 1e6).toFixed(1).replace('.0', '') + ' млн' : n >= 1e3 ? Math.round(n / 1e3) + ' тыс' : String(n);
const fmtSize = b => !b ? '0 МБ' : b >= 1073741824 ? (b / 1073741824).toFixed(2) + ' ГБ'
  : b > 1048576 ? (b / 1048576).toFixed(1) + ' МБ' : Math.max(1, Math.round(b / 1024)) + ' КБ';
function fmtTime(s) {
  s = s || 0;
  const hh = Math.floor(s / 3600), mm = Math.floor(s % 3600 / 60);
  return hh ? `${hh} ч ${mm} мин` : mm ? `${mm} мин` : s ? `${s} с` : '—';
}
function fmtDate(ts) {
  if (!ts) return 'никогда';
  const d = new Date(ts * 1000), now = new Date();
  if (d.toDateString() === now.toDateString()) return 'сегодня, ' + d.toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleDateString('ru', { day: 'numeric', month: 'short', year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined });
}
const LOADER_NAMES = { vanilla: 'Vanilla', fabric: 'Fabric', forge: 'Forge', neoforge: 'NeoForge', quilt: 'Quilt' };
const SRC_NAMES = { modrinth: 'Modrinth', curseforge: 'CurseForge' };
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

async function call(name, ...args) {
  const r = await window.pywebview.api[name](...args);
  if (!r || !r.ok) {
    const e = new Error(r ? r.error : 'Нет ответа');
    e.twofactor = r && r.twofactor;
    throw e;
  }
  return r.data;
}
async function safe(promise) {
  try { return await promise; } catch (e) { toast(e.message, 'err'); return undefined; }
}
function toast(text, kind = '') {
  const t = h('div', { class: 'toast ' + kind }, text);
  $('#toasts').append(t);
  setTimeout(() => t.remove(), kind === 'err' ? 7000 : 3500);
}
function fillIcons(root = document) {
  root.querySelectorAll('i[data-i]').forEach(el => {
    const n = icon(el.dataset.i, el.className);
    el.replaceWith(n);
  });
}
function spinner(text = 'Загрузка…') { return h('div', { class: 'loading' }, h('div', { class: 'spin' }), text); }
function pbar(task) {
  const ind = !task || !task.max;
  return h('div', { class: 'pbar' + (ind ? ' ind' : '') },
    h('div', { style: { width: ind ? '' : Math.min(100, task.progress / task.max * 100) + '%' } }));
}
function sw(checked, onchange) {
  return h('label', { class: 'switch' }, h('input', { type: 'checkbox', checked, onchange: e => onchange(e.target.checked) }), h('span'));
}
function seg(options, value, onchange) {
  const el = h('div', { class: 'seg' });
  const draw = v => {
    el.innerHTML = '';
    options.forEach(([val, label]) => el.append(h('button', {
      class: val === v ? 'on' : '', onclick: () => { draw(val); onchange(val); } }, label)));
  };
  draw(value);
  return el;
}

// ================================================================ state
const S = {
  instances: [], accounts: { accounts: [], selected: null }, settings: {}, running: new Set(),
  selected: null, tasks: new Map(), icons: {}, collapsed: new Set(), ram: 8192, filter: '',
  logs: {}, versions: null,
};
const listeners = { log: new Set(), task: new Set(), instances: new Set(), game: new Set() };

// ================================================================ icons for instances / heads
function instIconUrl(inst) {
  if (inst.hasIcon && S.icons[inst.id]) return S.icons[inst.id];
  return pixUrl(PIX[inst.icon] || PIX.grass);
}
async function loadCustomIcons() {
  await Promise.all(S.instances.filter(i => i.hasIcon && !S.icons[i.id]).map(async i => {
    const url = await call('instance_icon', i.id).catch(() => null);
    if (url) S.icons[i.id] = url;
  }));
}
function headEl(acc, size = 24) {
  const el = h('span', { class: 'head', style: { width: size + 'px', height: size + 'px' } });
  const def = pixUrl(DEFAULT_HEAD);
  if (!acc || !acc.skin) {
    el.style.backgroundImage = `url(${def})`;
    el.style.backgroundSize = '100% 100%';
    return el;
  }
  const img = new Image();
  img.onload = () => {
    const sc = size / 8, w = 64 * sc;  // голова — квадрат 8x8 в развёртке 64px (HD-скины масштабируются)
    el.style.backgroundImage = `url(${acc.skin})`;
    el.style.backgroundSize = `${w}px auto`;
    el.style.backgroundPosition = `${-8 * sc}px ${-8 * sc}px`;
    el.append(h('span', { style: { backgroundImage: `url(${acc.skin})`, backgroundSize: `${w}px auto`, backgroundPosition: `${-40 * sc}px ${-8 * sc}px` } }));
  };
  img.onerror = () => { el.style.backgroundImage = `url(${def})`; el.style.backgroundSize = '100% 100%'; };
  img.src = acc.skin;
  return el;
}
function currentAccount() {
  return S.accounts.accounts.find(a => a.id === S.accounts.selected) || null;
}

// ================================================================ modal / menu
function modal({ title, cls = '', body, footer, onclose, closable = true }) {
  const close = () => { ov.remove(); document.removeEventListener('keydown', esc); onclose && onclose(); };
  const esc = e => { if (e.key === 'Escape' && closable && ov === $('#layer').lastElementChild) close(); };
  const box = h('div', { class: 'modal ' + cls },
    h('div', { class: 'modal-h' }, h('h3', null, title), h('button', { class: 'xbtn', onclick: close }, icon('x'))),
    body, footer ? h('div', { class: 'modal-f' }, footer) : null);
  const ov = h('div', { class: 'overlay', onmousedown: e => { if (e.target === ov && closable) ov._down = true; },
    onmouseup: e => { if (e.target === ov && ov._down) close(); ov._down = false; } }, box);
  $('#layer').append(ov);
  document.addEventListener('keydown', esc);
  return { el: box, close };
}
function confirmBox(title, text, okText = 'Удалить', danger = true) {
  return new Promise(res => {
    let done = false;
    const m = modal({
      title, body: h('div', { class: 'modal-b' }, text),
      footer: [h('button', { class: 'btn', onclick: () => m.close() }, 'Отмена'),
        h('button', { class: 'btn ' + (danger ? 'danger' : 'primary'), onclick: () => { done = true; m.close(); } }, okText)],
      onclose: () => res(done),
    });
  });
}
function promptBox(title, label, value = '', okText = 'OK') {
  return new Promise(res => {
    let out = null;
    const inp = h('input', { class: 'input', value, onkeydown: e => { if (e.key === 'Enter') ok(); } });
    const ok = () => { out = inp.value.trim(); m.close(); };
    const m = modal({
      title, body: h('div', { class: 'modal-b' }, h('div', { class: 'field' }, h('label', null, label), inp)),
      footer: [h('button', { class: 'btn', onclick: () => m.close() }, 'Отмена'), h('button', { class: 'btn primary', onclick: ok }, okText)],
      onclose: () => res(out),
    });
    setTimeout(() => { inp.focus(); inp.select(); }, 30);
  });
}
let _menu = null;
function closeMenu() { if (_menu) { _menu.remove(); _menu = null; } }
function menu(x, y, items) {
  closeMenu();
  const m = h('div', { class: 'menu' }, items.map(it => {
    if (it === '-') return h('div', { class: 'sep' });
    if (it.header) return h('div', { class: 'mh' }, it.header);
    return h('button', { class: it.danger ? 'danger' : '', onclick: () => { closeMenu(); it.act(); } },
      it.icon ? icon(it.icon) : h('i', { class: 'ic' }), it.label);
  }));
  document.body.append(m);
  const r = m.getBoundingClientRect();
  m.style.left = Math.min(x, innerWidth - r.width - 6) + 'px';
  m.style.top = Math.min(y, innerHeight - r.height - 6) + 'px';
  _menu = m;
}
document.addEventListener('mousedown', e => { if (_menu && !_menu.contains(e.target)) closeMenu(); });
window.addEventListener('blur', closeMenu);

// ================================================================ events from python
window.hvEvent = ev => {
  if (ev.type === 'task') onTask(ev);
  else if (ev.type === 'game') onGame(ev);
  else if (ev.type === 'log') {
    const arr = (S.logs[ev.inst] = S.logs[ev.inst] || []);
    arr.push(...ev.lines);
    if (arr.length > 5000) arr.splice(0, arr.length - 5000);
    listeners.log.forEach(fn => fn(ev));
  }
};

function onTask(ev) {
  if (ev.done) {
    S.tasks.delete(ev.id);
    if (ev.error) toast(`${ev.title}: ${ev.error}`, 'err');
    else if (!ev.title.startsWith('Запуск')) toast(`${ev.title} — готово`);
    if (ev.result && ev.result.inst) {
      refreshInstances().then(() => select(ev.result.inst));
    } else if (ev.inst) refreshInstances();
  } else S.tasks.set(ev.id, ev);
  renderTasks();
  renderTileProgress();
  listeners.task.forEach(fn => fn(ev));
}
function onGame(ev) {
  if (ev.state === 'running') {
    S.running.add(ev.inst);
    S.logs[ev.inst] = [];
  } else {
    S.running.delete(ev.inst);
    if (ev.crashed) {
      if (ev.analysis) S.crash[ev.inst] = ev.analysis;
      const first = ev.analysis && ev.analysis.problems.find(p => p.level === 'error');
      toast(first ? `Игра вылетела: ${first.title}` : `Игра завершилась с ошибкой (код ${ev.code})`, 'err');
      if (S.settings.openLogOnCrash && !document.querySelector('.log')) openInstance(ev.inst, 'log');
    } else delete S.crash[ev.inst];
    refreshInstances();
  }
  renderInstances();
  renderSide();
  listeners.game.forEach(fn => fn(ev));
}

// ================================================================ toolbar / status
function renderTasks() {
  const box = $('#tasks');
  box.innerHTML = '';
  for (const t of S.tasks.values()) {
    box.append(h('div', { class: 'task' }, h('span', { class: 't' }, t.title), pbar(t), h('span', { class: 's' }, t.status || '')));
  }
  const total = S.instances.reduce((a, i) => a + (i.playtime || 0), 0);
  $('#statusRight').textContent = S.tasks.size ? '' : `Сборок: ${S.instances.length} · Всего в игре: ${fmtTime(total)}`;
}
function renderAccountBtn() {
  const acc = currentAccount();
  const head = headEl(acc, 24);
  head.id = 'accHead';
  $('#accHead').replaceWith(head);
  $('#accName').textContent = acc ? acc.name : 'Добавить аккаунт';
}

// ================================================================ instances grid
async function refreshInstances() {
  S.instances = await call('instances');
  await loadCustomIcons();
  if (S.selected && !S.instances.find(i => i.id === S.selected)) S.selected = null;
  renderInstances();
  renderSide();
  renderTasks();
  listeners.instances.forEach(fn => fn());
}
function taskFor(id) {
  for (const t of S.tasks.values()) if (t.inst === id) return t;
  return null;
}
function renderInstances() {
  const root = $('#instances');
  root.innerHTML = '';
  const q = S.filter.toLowerCase();
  const list = S.instances.filter(i => !q || i.name.toLowerCase().includes(q) || i.mc.includes(q));
  if (!S.instances.length) {
    root.append(h('div', { class: 'empty' },
      h('div', { class: 'big', style: { backgroundImage: `url(${pixUrl(PIX.cone)})` } }),
      h('div', null, h('div', { style: { fontSize: '16px', color: 'var(--text)', marginBottom: '4px' } }, 'Пока нет ни одной сборки'),
        'Создайте свою или установите модпак с Modrinth / CurseForge'),
      h('button', { class: 'btn primary', onclick: () => openNewInstance() }, icon('plus'), 'Добавить сборку')));
    return;
  }
  const groups = new Map();
  for (const i of list) {
    const g = i.group || '';
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(i);
  }
  const names = [...groups.keys()].sort((a, b) => (a === '') - (b === '') || a.localeCompare(b));
  for (const g of names) {
    const collapsed = S.collapsed.has(g);
    if (names.length > 1 || g) {
      root.append(h('div', { class: 'group-h' + (collapsed ? ' collapsed' : ''), onclick: () => {
        collapsed ? S.collapsed.delete(g) : S.collapsed.add(g); renderInstances();
      } }, icon('chev', 'sm'), g || 'Без группы', h('span', { class: 'muted' }, groups.get(g).length)));
    }
    if (collapsed) continue;
    root.append(h('div', { class: 'grid' }, groups.get(g).map(tile)));
  }
  renderTileProgress();
}
function tile(inst) {
  return h('div', {
    class: 'tile' + (S.selected === inst.id ? ' sel' : ''), 'data-id': inst.id, title: inst.name,
    onclick: () => select(inst.id),
    ondblclick: () => play(inst.id),
    oncontextmenu: e => { e.preventDefault(); select(inst.id); instMenu(inst, e.clientX, e.clientY); },
  },
  h('div', { class: 'ico', style: { backgroundImage: `url(${instIconUrl(inst)})` } }),
  h('div', { class: 'nm' }, inst.name),
  h('div', { class: 'sub' }, `${inst.loader !== 'vanilla' ? LOADER_NAMES[inst.loader] + ' ' : ''}${inst.mc}`),
  S.running.has(inst.id) ? h('span', { class: 'run', title: 'Запущена' }) : null);
}
function renderTileProgress() {
  document.querySelectorAll('.tile').forEach(t => {
    const old = t.querySelector('.pbar');
    if (old) old.remove();
    const task = taskFor(t.dataset.id);
    if (task) t.append(pbar(task));
  });
  if (S.selected) {
    const btn = $('#side .play');
    const task = taskFor(S.selected);
    if (btn && !S.running.has(S.selected)) {
      btn.disabled = !!task;
      btn.lastChild.textContent = task ? (task.status || 'Подготовка…') : 'Играть';
    }
  }
}
function select(id) {
  S.selected = id;
  document.querySelectorAll('.tile').forEach(t => t.classList.toggle('sel', t.dataset.id === id));
  renderSide();
}
function instMenu(inst, x, y) {
  const running = S.running.has(inst.id);
  menu(x, y, [
    running ? { label: 'Остановить', icon: 'stop', act: () => call('kill', inst.id) } : { label: 'Играть', icon: 'play', act: () => play(inst.id) },
    '-',
    { label: 'Редактировать', icon: 'edit', act: () => openInstance(inst.id, 'version') },
    { label: 'Моды', icon: 'box', act: () => openInstance(inst.id, 'mods') },
    { label: 'Миры', icon: 'globe', act: () => openInstance(inst.id, 'worlds') },
    { label: 'Скриншоты', icon: 'camera', act: () => openInstance(inst.id, 'screenshots') },
    { label: 'Журнал', icon: 'terminal', act: () => openInstance(inst.id, 'log') },
    { label: 'Открыть папку', icon: 'folder', act: () => call('open_folder', 'instance', inst.id) },
    '-',
    { label: 'Переименовать', icon: 'edit', act: () => renameInstance(inst) },
    { label: 'Сменить группу', icon: 'layers', act: () => changeGroup(inst) },
    { label: 'Копировать', icon: 'copy', act: () => copyInstance(inst) },
    { label: 'Экспортировать…', icon: 'upload', act: () => openExport(inst) },
    { label: 'Проверить файлы', icon: 'wrench', act: () => safe(call('repair', inst.id)) },
    '-',
    { label: 'Удалить', icon: 'trash', danger: true, act: () => deleteInstance(inst) },
  ]);
}

// ================================================================ side panel
function renderSide() {
  const side = $('#side');
  side.innerHTML = '';
  const inst = S.instances.find(i => i.id === S.selected);
  if (!inst) {
    const acc = currentAccount();
    side.append(h('div', { class: 'side-empty' },
      h('h3', null, 'Hvoya Launcher'),
      h('div', null, 'Выберите сборку слева, чтобы запустить её, или создайте новую.'),
      h('div', { class: 'acc on', onclick: openAccounts, style: { marginTop: '6px' } }, headEl(acc, 34),
        h('div', { class: 'am' }, h('div', { class: 'an' }, acc ? acc.name : 'Нет аккаунта'),
          h('div', { class: 'at' }, acc ? (acc.type === 'elyby' ? 'Ely.by' : 'Офлайн') : 'Нажмите, чтобы добавить'))),
      h('div', { class: 'muted', style: { fontSize: '12px' } },
        'Двойной клик по сборке — запуск. Правый клик — меню.')));
    return;
  }
  const running = S.running.has(inst.id);
  const task = taskFor(inst.id);
  const playBtn = running
    ? h('button', { class: 'play stop', onclick: () => call('kill', inst.id) }, icon('stop'), h('span', null, 'Остановить'))
    : h('button', { class: 'play', disabled: !!task, onclick: () => play(inst.id) }, icon('play'), h('span', null, task ? (task.status || 'Подготовка…') : 'Играть'));
  const mp = inst.modpack;
  side.append(
    h('div', { class: 'side-head' },
      h('div', { class: 'ico', style: { backgroundImage: `url(${instIconUrl(inst)})` } }),
      h('h2', null, inst.name),
      h('div', { class: 'chips' },
        h('span', { class: 'chip' }, inst.mc),
        inst.loader !== 'vanilla' ? h('span', { class: 'chip ld-' + inst.loader }, `${LOADER_NAMES[inst.loader]} ${inst.loaderVersion || ''}`.trim()) : h('span', { class: 'chip' }, 'Vanilla'),
        mp && mp.source ? h('span', { class: 'chip' }, SRC_NAMES[mp.source]) : null)),
    h('div', { class: 'side-actions' },
      playBtn,
      sa('edit', 'Редактировать', () => openInstance(inst.id, 'version')),
      sa('box', 'Моды', () => openInstance(inst.id, 'mods')),
      sa('image', 'Ресурспаки', () => openInstance(inst.id, 'resourcepacks')),
      sa('sun', 'Шейдеры', () => openInstance(inst.id, 'shaderpacks')),
      sa('globe', 'Миры', () => openInstance(inst.id, 'worlds')),
      sa('camera', 'Скриншоты', () => openInstance(inst.id, 'screenshots')),
      inst.loader !== 'vanilla' ? sa('zap', 'Ускорить игру', () => openOptimize(inst)) : null,
      mp && mp.source ? sa('download', 'Обновить модпак', () => openModpackUpdate(inst)) : null,
      sa('terminal', 'Журнал', () => openInstance(inst.id, 'log')),
      sa('folder', 'Открыть папку', () => call('open_folder', 'instance', inst.id)),
      sa('copy', 'Копировать', () => copyInstance(inst)),
      sa('upload', 'Экспорт', () => openExport(inst)),
      sa('trash', 'Удалить', () => deleteInstance(inst), true)),
    h('div', { class: 'side-stats' },
      h('div', null, 'В игре', h('b', null, fmtTime(inst.playtime))),
      h('div', null, 'Последний запуск', h('b', null, fmtDate(inst.lastPlayed))),
      h('div', null, 'Память', h('b', null, `${inst.ramMax || S.settings.ramMax} МБ`))));
}
function sa(ic, label, act, danger) {
  return h('button', { class: 'sa' + (danger ? ' danger' : ''), onclick: act }, icon(ic), label);
}

// ================================================================ instance actions
async function play(id) {
  if (S.running.has(id) || taskFor(id)) return;
  if (!currentAccount()) { toast('Сначала добавьте аккаунт', 'warn'); openAccounts(); return; }
  if (!await memoryGate(id)) return;
  await safe(call('launch', id));
}
async function deleteInstance(inst) {
  if (!await confirmBox('Удалить сборку?', `Сборка «${inst.name}» и вся её папка (миры, моды, настройки) будут удалены без возможности восстановления.`)) return;
  if (await safe(call('delete_instance', inst.id))) { toast('Сборка удалена'); refreshInstances(); }
}
async function copyInstance(inst) {
  const name = await promptBox('Копировать сборку', 'Название копии', inst.name + ' (копия)', 'Копировать');
  if (!name) return;
  const n = await safe(call('copy_instance', inst.id, name));
  if (n) { await refreshInstances(); select(n.id); }
}
async function renameInstance(inst) {
  const name = await promptBox('Переименовать', 'Название', inst.name, 'Сохранить');
  if (name && await safe(call('update_instance', inst.id, { name }))) refreshInstances();
}
async function changeGroup(inst) {
  const g = await promptBox('Группа', 'Название группы (пусто — без группы)', inst.group || '', 'Сохранить');
  if (g !== null && await safe(call('update_instance', inst.id, { group: g }))) refreshInstances();
}

// ================================================================ versions helpers
async function getVersions() {
  if (!S.versions) S.versions = await call('mc_versions');
  return S.versions;
}
const LOADER_OPTS = [['vanilla', 'Нет'], ['fabric', 'Fabric'], ['forge', 'Forge'], ['neoforge', 'NeoForge'], ['quilt', 'Quilt']];

function iconPicker(current, onpick, extra) {
  const box = h('div', { class: 'icon-pick' });
  const draw = cur => {
    box.innerHTML = '';
    Object.keys(PIX).forEach(k => box.append(h('button', {
      class: cur === k ? 'on' : '', title: k, style: { backgroundImage: `url(${pixUrl(PIX[k])})` },
      onclick: () => { draw(k); onpick(k); } })));
    if (extra) box.append(extra(cur));
  };
  draw(current);
  return box;
}

/** Блок выбора загрузчика и его версии. Возвращает {el, get()} */
function loaderBlock(initLoader, initLv, getMc) {
  let loader = initLoader, lv = initLv || '';
  const lvSel = h('select', { class: 'input', onchange: e => { lv = e.target.value; } });
  const lvField = h('div', { class: 'field' }, h('label', null, 'Версия загрузчика'), lvSel);
  const note = h('div', { class: 'hint' });
  let reqId = 0;
  async function loadLv() {
    lvField.classList.toggle('hidden', loader === 'vanilla');
    note.textContent = '';
    if (loader === 'vanilla') return;
    const mc = getMc();
    if (!mc) { lvSel.innerHTML = ''; return; }
    const my = ++reqId;
    lvSel.innerHTML = '';
    lvSel.append(h('option', { value: '' }, 'Загрузка…'));
    lvSel.disabled = true;
    const list = await call('loader_versions', loader, mc).catch(() => []);
    if (my !== reqId) return;
    lvSel.disabled = false;
    lvSel.innerHTML = '';
    if (!list.length) {
      lvSel.append(h('option', { value: '' }, '—'));
      note.textContent = `${LOADER_NAMES[loader]} не поддерживает Minecraft ${mc}`;
      block.ok = false;
      return;
    }
    block.ok = true;
    lvSel.append(h('option', { value: '' }, `Последняя (${list[0]})`));
    list.forEach(v => lvSel.append(h('option', { value: v, selected: v === lv }, v)));
    if (!list.includes(lv)) lv = '';
  }
  const block = {
    ok: true,
    el: h('div', null,
      h('div', { class: 'field' }, h('label', null, 'Загрузчик модов'),
        seg(LOADER_OPTS, loader, v => { loader = v; lv = ''; block.ok = true; loadLv(); })),
      lvField, note),
    get: () => ({ loader, loaderVersion: loader === 'vanilla' ? '' : lv }),
    reload: loadLv,
  };
  loadLv();
  return block;
}

// ================================================================ new instance window
function openNewInstance(tab = 'custom') {
  const nav = h('div', { class: 'nav' });
  const pane = h('div', { class: 'pane' });
  const m = modal({ title: 'Новая сборка', cls: 'wide', body: h('div', { class: 'split' }, nav, pane) });
  const tabs = [
    ['custom', 'plus', 'Своя сборка'], ['modrinth', 'download', 'Modrinth'], ['curseforge', 'download', 'CurseForge'], ['-'],
    ['other', 'swap', 'Из другого лаунчера'], ['import', 'upload', 'Модпак из файла'],
  ];
  const show = t => {
    nav.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.t === t));
    pane.innerHTML = '';
    if (t === 'custom') pane.append(newCustomPane(m));
    else if (t === 'import') pane.append(importPane(m));
    else if (t === 'other') pane.append(importOtherPane(m));
    else pane.append(browser({ source: t, ptype: 'modpack', onDone: () => m.close() }));
  };
  tabs.forEach(([t, ic, label]) => nav.append(t === '-' ? h('div', { class: 'sep' }) :
    h('button', { 'data-t': t, onclick: () => show(t) }, icon(ic), label)));
  show(tab);
}

function importPane(m) {
  return h('div', { class: 'pane-scroll' },
    h('div', { class: 'list-empty' }, icon('upload', 'lg'),
      h('div', null, h('div', { style: { color: 'var(--text)', fontSize: '14px', marginBottom: '4px' } }, 'Импорт модпака из файла'),
        'Поддерживаются .mrpack (Modrinth) и .zip (CurseForge)'),
      h('button', { class: 'btn primary', onclick: async () => {
        const id = await safe(call('import_pack'));
        if (id) { m.close(); toast('Импорт начат — прогресс внизу'); }
      } }, icon('file'), 'Выбрать файл…')));
}

function newCustomPane(m) {
  let mc = null, icon_ = 'grass';
  const filters = { release: true, snapshot: !!S.settings.showSnapshots, old_beta: false, old_alpha: false };
  const name = h('input', { class: 'input', placeholder: 'Название сборки' });
  const group = h('input', { class: 'input', placeholder: 'Без группы', list: 'groupsList' });
  const groups = [...new Set(S.instances.map(i => i.group).filter(Boolean))];
  const dl = h('datalist', { id: 'groupsList' }, groups.map(g => h('option', { value: g })));
  const search = h('input', { class: 'input', placeholder: 'Поиск версии…', oninput: () => drawTable() });
  const table = h('div', { class: 'vtable', style: { height: '260px' } }, spinner());
  const create = h('button', { class: 'btn primary', disabled: true }, icon('plus'), 'Создать');
  const lb = loaderBlock('vanilla', '', () => mc);
  let versions = [];
  let autoName = true;
  name.addEventListener('input', () => { autoName = !name.value; });

  function drawTable() {
    const q = search.value.trim();
    table.innerHTML = '';
    const types = { release: 'Релиз', snapshot: 'Снапшот', old_beta: 'Бета', old_alpha: 'Альфа' };
    const rows = versions.filter(v => filters[v.type] && (!q || v.id.includes(q)));
    if (!rows.length) table.append(h('div', { class: 'loading' }, 'Ничего не найдено'));
    rows.forEach(v => table.append(h('div', { class: 'vrow' + (v.id === mc ? ' sel' : ''), onclick: () => pick(v.id) },
      h('span', { class: 'v1' }, v.id), h('span', { class: 'v2' }, types[v.type]), h('span', { class: 'v3' }, v.date))));
  }
  function pick(id) {
    mc = id;
    if (autoName) name.placeholder = `Minecraft ${id}`;
    table.querySelectorAll('.vrow').forEach(r => r.classList.toggle('sel', r.firstChild.textContent === id));
    create.disabled = false;
    lb.reload();
  }
  getVersions().then(v => { versions = v; drawTable(); const first = v.find(x => x.type === 'release'); if (first) pick(first.id); })
    .catch(e => { table.innerHTML = ''; table.append(h('div', { class: 'loading' }, 'Не удалось загрузить список версий: ' + e.message)); });

  create.onclick = async () => {
    if (!mc) return;
    if (!lb.ok) { toast('Этот загрузчик недоступен для выбранной версии', 'warn'); return; }
    const data = { name: name.value.trim() || name.placeholder, group: group.value.trim(), mc, icon: icon_, ...lb.get() };
    create.disabled = true;
    const inst = await safe(call('create_instance', data));
    create.disabled = false;
    if (!inst) return;
    m.close();
    await refreshInstances();
    select(inst.id);
    toast(`Сборка «${inst.name}» создана`);
  };

  const filterBox = h('div', { class: 'row', style: { gap: '14px', marginBottom: '8px' } },
    [['release', 'Релизы'], ['snapshot', 'Снапшоты'], ['old_beta', 'Бета'], ['old_alpha', 'Альфа']].map(([k, l]) =>
      h('label', { class: 'check' }, h('input', { type: 'checkbox', checked: filters[k], onchange: e => { filters[k] = e.target.checked; drawTable(); } }), l)));

  return h('div', { class: 'pane', style: { borderRadius: '0 0 12px 0' } },
    h('div', { class: 'pane-scroll' },
      h('div', { class: 'row', style: { alignItems: 'flex-start' } },
        h('div', { class: 'field' }, h('label', null, 'Название'), name),
        h('div', { class: 'field', style: { maxWidth: '220px' } }, h('label', null, 'Группа'), group, dl)),
      h('div', { class: 'field' }, h('label', null, 'Иконка'), iconPicker(icon_, k => { icon_ = k; })),
      h('div', { class: 'field' }, h('label', null, 'Версия Minecraft'), h('div', { class: 'row' }, search), filterBox, table),
      lb.el),
    h('div', { class: 'modal-f' }, h('button', { class: 'btn', onclick: () => m.close() }, 'Отмена'), create));
}

// ================================================================ content browser (Modrinth / CurseForge)
/**
 * opts: {source, ptype: mod|resourcepack|shader|modpack, inst?, onDone?}
 */
function browser(opts) {
  const st = { source: opts.source, query: '', sort: 'relevance', offset: 0, total: 0, hits: [], sel: null,
    mc: opts.inst ? opts.inst.mc : '', loader: opts.inst ? opts.inst.loader : '', installed: new Set(), req: 0 };
  const results = h('div', { class: 'b-results' });
  const detail = h('div', { class: 'b-detail' });
  const q = h('input', { placeholder: 'Поиск…', spellcheck: false, oninput: debounce(() => { st.query = q.value; reload(); }, 350) });
  const sortSel = h('select', { class: 'input', style: { width: '150px' }, onchange: e => { st.sort = e.target.value; reload(); } },
    [['relevance', 'По релевантности'], ['downloads', 'По загрузкам'], ['updated', 'Недавно обновлённые'], ['newest', 'Новые']]
      .map(([v, l]) => h('option', { value: v }, l)));
  const bar = h('div', { class: 'pane-bar' });
  if (opts.showSourceTabs) {
    bar.append(seg([['modrinth', 'Modrinth'], ['curseforge', 'CurseForge']], st.source, v => { st.source = v; reload(); }));
  }
  bar.append(h('label', { class: 'tb-search' }, icon('search'), q), sortSel);
  if (opts.ptype === 'modpack') {
    const mcSel = h('select', { class: 'input', style: { width: '120px' }, onchange: e => { st.mc = e.target.value; reload(); } },
      h('option', { value: '' }, 'Все версии'));
    getVersions().then(vs => vs.filter(v => v.type === 'release').forEach(v => mcSel.append(h('option', { value: v.id }, v.id)))).catch(() => {});
    const ldSel = h('select', { class: 'input', style: { width: '120px' }, onchange: e => { st.loader = e.target.value; reload(); } },
      h('option', { value: '' }, 'Любой'), ...['fabric', 'forge', 'neoforge', 'quilt'].map(l => h('option', { value: l }, LOADER_NAMES[l])));
    bar.append(mcSel, ldSel);
  } else if (opts.inst) {
    bar.append(h('span', { class: 'chip' }, opts.inst.mc), opts.ptype === 'mod' ? h('span', { class: 'chip ld-' + opts.inst.loader }, LOADER_NAMES[opts.inst.loader]) : null);
  }
  const el = h('div', { class: 'pane' }, bar, h('div', { class: 'browser' }, h('div', { class: 'b-list' }, results), detail));

  async function refreshInstalled() {
    if (!opts.inst) return;
    st.installed = new Set(await call('installed_projects', opts.inst.id).catch(() => []));
    results.querySelectorAll('.b-item').forEach(it => {
      const has = st.installed.has(`${st.source}:${it.dataset.id}`);
      const b = it.querySelector('.inst-badge');
      if (has && !b) it.querySelector('.bt').append(h('span', { class: 'inst-badge' }, 'Установлен'));
    });
    if (st.sel) showDetail(st.sel, true);
  }
  const onTaskDone = ev => { if (ev.done && opts.inst && ev.inst === opts.inst.id) refreshInstalled(); };
  listeners.task.add(onTaskDone);
  const obs = new MutationObserver(() => { if (!el.isConnected) { listeners.task.delete(onTaskDone); obs.disconnect(); } });
  setTimeout(() => obs.observe(document.body, { childList: true, subtree: true }), 0);

  async function reload() {
    st.offset = 0; st.hits = []; st.sel = null;
    results.innerHTML = '';
    results.append(spinner());
    detail.innerHTML = '';
    detail.append(h('div', { class: 'list-empty' }, icon('info', 'lg'), 'Выберите проект из списка'));
    await more();
  }
  async function more() {
    const my = ++st.req;
    let res;
    try {
      res = await call('search', st.source, st.query, opts.ptype, st.mc, st.loader, st.offset, st.sort);
    } catch (e) {
      if (my !== st.req) return;
      results.innerHTML = '';
      results.append(h('div', { class: 'list-empty' }, 'Ошибка поиска: ' + e.message, h('button', { class: 'btn', onclick: reload }, 'Повторить')));
      return;
    }
    if (my !== st.req) return;
    const sp = results.querySelector('.loading'); if (sp) sp.remove();
    const mb = results.querySelector('.b-more'); if (mb) mb.remove();
    st.total = res.total;
    st.offset += res.hits.length;
    st.hits.push(...res.hits);
    if (!st.hits.length) results.append(h('div', { class: 'list-empty' }, 'Ничего не найдено'));
    res.hits.forEach(p => results.append(item(p)));
    if (st.offset < st.total && res.hits.length) {
      const b = h('button', { class: 'btn', onclick: () => { b.disabled = true; b.textContent = 'Загрузка…'; more(); } }, 'Показать ещё');
      results.append(h('div', { class: 'b-more' }, b));
    }
  }
  function item(p) {
    const has = st.installed.has(`${st.source}:${p.id}`);
    return h('div', { class: 'b-item', 'data-id': p.id, onclick: e => {
      results.querySelectorAll('.b-item').forEach(x => x.classList.remove('sel'));
      e.currentTarget.classList.add('sel');
      showDetail(p);
    } },
    h('div', { class: 'bi', style: { backgroundImage: p.icon ? `url("${p.icon}")` : '' } }),
    h('div', { class: 'bm' },
      h('div', { class: 'bt' }, h('span', null, p.title), has ? h('span', { class: 'inst-badge' }, 'Установлен') : null),
      h('div', { class: 'bd' }, p.description),
      h('div', { class: 'bx' }, h('span', null, p.author ? 'от ' + p.author : ''), h('span', null, '↓ ' + fmtNum(p.downloads)))));
  }

  async function showDetail(p, keepVersion) {
    st.sel = p;
    const prevVer = keepVersion && detail.querySelector('select') ? detail.querySelector('select').value : null;
    detail.innerHTML = '';
    const verSel = h('select', { class: 'input', disabled: true }, h('option', null, 'Загрузка версий…'));
    const has = st.installed.has(`${st.source}:${p.id}`);
    const nameInp = opts.ptype === 'modpack' ? h('input', { class: 'input', value: p.title, placeholder: 'Название сборки' }) : null;
    const btn = h('button', { class: 'btn primary', disabled: true }, icon('download'),
      opts.ptype === 'modpack' ? 'Установить модпак' : has ? 'Переустановить / сменить версию' : 'Установить');
    const body = h('div', { class: 'db' }, p.description);
    detail.append(
      h('div', { class: 'dh' }, h('div', { class: 'bi', style: { backgroundImage: p.icon ? `url("${p.icon}")` : '' } }),
        h('div', { style: { minWidth: 0 } }, h('h4', null, p.title),
          h('div', { class: 'muted', style: { fontSize: '12px' } }, p.author ? 'от ' + p.author : ''),
          h('div', { class: 'muted', style: { fontSize: '12px' } }, '↓ ' + fmtNum(p.downloads) + ' загрузок'),
          p.url ? h('a', { href: '#', style: { color: 'var(--accent-h)', fontSize: '12px' }, onclick: e => { e.preventDefault(); call('open_url', p.url); } }, 'Открыть на сайте ↗') : null)),
      body,
      h('div', { class: 'df' }, nameInp ? h('div', { class: 'field', style: { margin: 0 } }, h('label', null, 'Название сборки'), nameInp) : null,
        h('div', { class: 'field', style: { margin: 0 } }, h('label', null, 'Версия'), verSel), btn));
    if (st.source === 'modrinth') {
      call('project', st.source, p.id).then(d => { if (st.sel === p && d.body) body.textContent = cleanMd(d.body); }).catch(() => {});
    }
    let vers;
    try {
      vers = await call('versions', st.source, p.id, opts.ptype, opts.ptype === 'modpack' ? st.mc : st.mc, opts.ptype === 'modpack' ? '' : st.loader);
    } catch (e) {
      verSel.innerHTML = ''; verSel.append(h('option', null, 'Ошибка: ' + e.message));
      return;
    }
    if (st.sel !== p) return;
    verSel.innerHTML = '';
    vers = vers.filter(v => v.file);
    if (!vers.length) {
      verSel.append(h('option', null, opts.inst ? `Нет версий для ${opts.inst.mc} ${opts.ptype === 'mod' ? LOADER_NAMES[opts.inst.loader] : ''}` : 'Нет версий'));
      return;
    }
    const tag = { release: '', beta: ' [beta]', alpha: ' [alpha]' };
    vers.forEach(v => verSel.append(h('option', { value: v.id, selected: v.id === prevVer },
      `${v.number || v.name}${tag[v.type] || ''} · ${v.mc.slice(0, 3).join(', ')}${v.mc.length > 3 ? '…' : ''}`)));
    verSel.disabled = false;
    btn.disabled = false;
    btn.onclick = async () => {
      btn.disabled = true;
      const vid = verSel.value;
      if (opts.ptype === 'modpack') {
        const id = await safe(call('install_modpack', st.source, p.id, vid, nameInp.value.trim() || p.title));
        if (id) { toast('Установка модпака началась — прогресс внизу'); opts.onDone && opts.onDone(); }
        else btn.disabled = false;
      } else {
        const id = await safe(call('install_content', st.source, opts.ptype, opts.inst.id, p.id, vid, p.title));
        if (id) toast(`Устанавливается ${p.title}…`);
        setTimeout(() => { btn.disabled = false; }, 800);
      }
    };
  }
  refreshInstalled().then(reload);
  return el;
}
function cleanMd(md) {
  return md.replace(/<[^>]+>/g, '').replace(/!\[[^\]]*\]\([^)]*\)/g, '').replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]*)\]\[[^\]]*\]/g, '$1').replace(/^\s*\[[^\]]+\]:\s*\S+.*$/gm, '')
    .replace(/^#+\s*/gm, '').replace(/[*_`]{1,3}/g, '').replace(/\n{3,}/g, '\n\n').trim().slice(0, 4000);
}

// ================================================================ instance window
const INST_TABS = [
  ['version', 'layers', 'Версия'], ['mods', 'box', 'Моды'], ['resourcepacks', 'image', 'Ресурспаки'],
  ['shaderpacks', 'sun', 'Шейдеры'], ['worlds', 'globe', 'Миры'], ['screenshots', 'camera', 'Скриншоты'], ['-'], ['log', 'terminal', 'Журнал'], ['settings', 'sliders', 'Настройки'], ['notes', 'note', 'Заметки'],
];
function openInstance(id, tab = 'version') {
  const inst = S.instances.find(i => i.id === id);
  if (!inst) return;
  const nav = h('div', { class: 'nav' });
  const pane = h('div', { class: 'pane' });
  const m = modal({ title: inst.name, cls: 'wide', body: h('div', { class: 'split' }, nav, pane), onclose: () => cleanup() });
  let cleanup = () => {};
  const show = t => {
    cleanup(); cleanup = () => {};
    nav.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.t === t));
    pane.innerHTML = '';
    const cur = S.instances.find(i => i.id === id) || inst;
    const reg = fn => { cleanup = fn; };
    if (t === 'version') pane.append(versionPane(cur, m));
    else if (['mods', 'resourcepacks', 'shaderpacks'].includes(t)) pane.append(contentPane(cur, t, reg));
    else if (t === 'log') pane.append(logPane(cur, reg, show));
    else if (t === 'worlds') pane.append(worldsPane(cur, reg));
    else if (t === 'screenshots') pane.append(shotsPane(cur, reg));
    else if (t === 'settings') pane.append(instSettingsPane(cur));
    else if (t === 'notes') pane.append(notesPane(cur));
  };
  INST_TABS.forEach(([t, ic, label]) => nav.append(t === '-' ? h('div', { class: 'sep' }) :
    h('button', { 'data-t': t, onclick: () => show(t) }, icon(ic), label)));
  nav.append(h('div', { class: 'spacer' }),
    h('button', { onclick: () => openExport(S.instances.find(i => i.id === id) || inst) }, icon('upload'), 'Экспорт'),
    h('button', { onclick: () => call('open_folder', 'instance', id) }, icon('folder'), 'Папка сборки'));
  show(tab);
}

function versionPane(inst, m) {
  const name = h('input', { class: 'input', value: inst.name });
  const group = h('input', { class: 'input', value: inst.group || '', placeholder: 'Без группы' });
  let iconName = inst.icon;
  const mcSel = h('select', { class: 'input' }, h('option', { value: inst.mc }, inst.mc));
  const lb = loaderBlock(inst.loader, inst.loaderVersion, () => mcSel.value);
  mcSel.onchange = () => lb.reload();
  getVersions().then(vs => {
    mcSel.innerHTML = '';
    vs.filter(v => v.type === 'release' || v.id === inst.mc || S.settings.showSnapshots && v.type === 'snapshot')
      .forEach(v => mcSel.append(h('option', { value: v.id, selected: v.id === inst.mc }, v.id)));
  }).catch(() => {});
  const customBtn = cur => h('button', { class: 'custom' + (cur === 'custom' ? ' on' : ''), title: 'Своя картинка',
    style: inst.hasIcon && S.icons[inst.id] ? { backgroundImage: `url(${S.icons[inst.id]})`, backgroundSize: 'cover' } : null,
    onclick: async () => {
      const r = await safe(call('pick_icon', inst.id));
      if (r) { delete S.icons[inst.id]; await refreshInstances(); toast('Иконка обновлена'); }
    } }, inst.hasIcon ? null : icon('upload'));
  const save = async () => {
    const values = { name: name.value.trim() || inst.name, group: group.value.trim(), mc: mcSel.value, ...lb.get() };
    if (!lb.ok) { toast('Этот загрузчик недоступен для выбранной версии', 'warn'); return; }
    const changedIcon = iconName !== inst.icon && iconName !== 'custom';
    const r = await safe(call('update_instance', inst.id, values));
    if (!r) return;
    if (changedIcon) { await call('reset_icon', inst.id, iconName); delete S.icons[inst.id]; }
    await refreshInstances();
    m.el.querySelector('.modal-h h3').textContent = r.name;
    toast('Сохранено');
  };
  return h('div', { class: 'pane' },
    h('div', { class: 'pane-scroll' },
      h('div', { class: 'row' }, h('div', { class: 'field' }, h('label', null, 'Название'), name),
        h('div', { class: 'field' }, h('label', null, 'Группа'), group)),
      h('div', { class: 'field' }, h('label', null, 'Иконка'), iconPicker(inst.hasIcon ? 'custom' : inst.icon, k => { iconName = k; }, customBtn)),
      h('div', { class: 'field', style: { maxWidth: '240px' } }, h('label', null, 'Версия Minecraft'), mcSel),
      lb.el,
      h('div', { class: 'hint' }, 'Смена версии или загрузчика не удаляет моды — проверьте их совместимость.'),
      inst.modpack && inst.modpack.name ? h('div', { class: 'card' }, h('h4', null, icon('box'), 'Модпак'),
        h('div', { class: 'row' }, h('div', { class: 'muted', style: { flex: 1 } }, `${inst.modpack.name} ${inst.modpack.versionName || ''}`, inst.modpack.source ? ` · ${SRC_NAMES[inst.modpack.source]}` : ''),
          inst.modpack.source ? h('button', { class: 'btn sm', onclick: () => openModpackUpdate(inst) }, icon('download'), 'Обновить модпак') : null)) : null),
    h('div', { class: 'modal-f' },
      h('button', { class: 'btn', onclick: () => safe(call('repair', inst.id)).then(id => id && toast('Проверка файлов запущена')) }, icon('wrench'), 'Проверить файлы'),
      h('div', { class: 'spacer' }),
      h('button', { class: 'btn primary', onclick: save }, icon('check'), 'Сохранить')));
}

const CONTENT_INFO = {
  mods: { ptype: 'mod', title: 'Моды', empty: 'Модов пока нет', icon: 'box' },
  resourcepacks: { ptype: 'resourcepack', title: 'Ресурспаки', empty: 'Ресурспаков пока нет', icon: 'image' },
  shaderpacks: { ptype: 'shader', title: 'Шейдеры', empty: 'Шейдеров пока нет', icon: 'sun' },
};
function contentPane(inst, kind, reg) {
  const info = CONTENT_INFO[kind];
  let items = [];
  const list = h('div', { class: 'clist' });
  const scroll = h('div', { class: 'pane-scroll', style: { padding: 0 } }, list);
  const q = h('input', { placeholder: 'Фильтр…', oninput: () => draw() });
  const count = h('span', { class: 'muted' });
  const draw = () => {
    list.innerHTML = '';
    const f = q.value.toLowerCase();
    const shown = items.filter(i => !f || i.title.toLowerCase().includes(f) || i.file.toLowerCase().includes(f));
    count.textContent = `${items.filter(i => i.enabled).length} / ${items.length}`;
    if (!items.length) {
      list.append(h('div', { class: 'list-empty' }, icon(info.icon, 'lg'), info.empty,
        h('button', { class: 'btn primary', onclick: openBrowser }, icon('download'), 'Скачать')));
      return;
    }
    shown.forEach(it => list.append(h('div', { class: 'citem' + (it.enabled ? '' : ' off') },
      sw(it.enabled, async v => { const r = await safe(call('toggle_content', inst.id, kind, it.file, v)); if (r) { items = r; draw(); } }),
      h('div', { class: 'cic', style: it.icon ? { backgroundImage: `url("${it.icon}")` } : null }, it.icon ? null : icon(it.isDir ? 'folder' : info.icon)),
      h('div', { class: 'cmain' }, h('div', { class: 'ct' }, it.title),
        h('div', { class: 'cs' }, [it.version, it.file, it.isDir ? 'папка' : fmtSize(it.size)].filter(Boolean).join(' · '))),
      it.source ? h('span', { class: 'src ' + it.source }, SRC_NAMES[it.source]) : null,
      h('button', { class: 'btn sm icon danger del', title: 'Удалить', onclick: async () => {
        if (!await confirmBox('Удалить?', `«${it.title}» будет удалён.`)) return;
        const r = await safe(call('delete_content', inst.id, kind, [it.file])); if (r) { items = r; draw(); }
      } }, icon('trash')))));
  };
  const load = async () => { const r = await safe(call('list_content', inst.id, kind)); if (r) { items = r; draw(); } };
  const openBrowser = () => {
    const m = modal({ title: `${info.title} для «${inst.name}»`, cls: 'wide',
      body: browser({ source: 'modrinth', ptype: info.ptype, inst, showSourceTabs: true }), onclose: load });
    void m;
  };
  const checkUpdates = async btn => {
    btn.disabled = true;
    const ups = await safe(call('check_updates', inst.id));
    btn.disabled = false;
    if (!ups) return;
    if (!ups.length) { toast('Все моды актуальны (по данным Modrinth)'); return; }
    const sel = new Set(ups.map((_, i) => i));
    const m = modal({ title: `Доступно обновлений: ${ups.length}`, cls: 'mid',
      body: h('div', { class: 'modal-b' }, ups.map((u, i) => h('label', { class: 'check', style: { display: 'flex', padding: '6px 0' } },
        h('input', { type: 'checkbox', checked: true, onchange: e => e.target.checked ? sel.add(i) : sel.delete(i) }),
        h('span', null, h('b', null, u.title), h('span', { class: 'muted' }, ' → ' + u.versionName))))),
      footer: [h('button', { class: 'btn', onclick: () => m.close() }, 'Отмена'),
        h('button', { class: 'btn primary', onclick: async () => {
          m.close();
          await safe(call('apply_updates', inst.id, ups.filter((_, i) => sel.has(i))));
        } }, icon('download'), 'Обновить')] });
  };
  const onTask = ev => { if (ev.done && ev.inst === inst.id) load(); };
  listeners.task.add(onTask);
  reg(() => listeners.task.delete(onTask));
  load();
  const upBtn = kind === 'mods' ? h('button', { class: 'btn', onclick: e => checkUpdates(e.currentTarget) }, icon('refresh'), 'Обновления') : null;
  return h('div', { class: 'pane' },
    h('div', { class: 'pane-bar' },
      h('button', { class: 'btn primary', onclick: openBrowser }, icon('download'), 'Скачать'),
      h('button', { class: 'btn', onclick: async () => { const r = await safe(call('add_content_files', inst.id, kind)); if (r) { items = r; draw(); } } }, icon('plus'), 'Из файла'),
      upBtn,
      kind === 'mods' ? h('button', { class: 'btn', title: 'Sodium, Iris, ModernFix и другие моды оптимизации', onclick: () => openOptimize(inst) }, icon('zap'), 'Ускорить') : null,
      h('button', { class: 'btn icon', title: 'Открыть папку', onclick: () => call('open_folder', 'instance', inst.id, kind) }, icon('folder')),
      h('label', { class: 'tb-search' }, icon('search'), q), count),
    scroll);
}

function logPane(inst, reg, go) {
  const pre = h('pre', { class: 'log' });
  const crashBox = h('div', { style: { display: 'contents' } });
  const showCrash = a => {
    crashBox.innerHTML = '';
    if (a) crashBox.append(crashCard(inst, a, go, () => { crashBox.innerHTML = ''; delete S.crash[inst.id]; }));
  };
  const analyze = async btn => {
    btn.disabled = true;
    const a = await safe(call('analyze_crash', inst.id));
    btn.disabled = false;
    if (a) { S.crash[inst.id] = a; showCrash(a); }
  };
  showCrash(S.crash[inst.id]);
  const onGameEv = ev => { if (ev.inst === inst.id) showCrash(S.crash[inst.id]); };
  listeners.game.add(onGameEv);
  let auto = true;
  pre.addEventListener('scroll', () => { auto = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30; });
  const cls = l => /\b(ERROR|FATAL|Exception|Caused by)\b/.test(l) ? 'e' : /\bWARN/.test(l) ? 'w' : l.startsWith('[Hvoya]') ? 'h' : '';
  const append = lines => {
    const frag = document.createDocumentFragment();
    lines.forEach(l => { const c = cls(l); frag.append(c ? h('span', { class: c }, l + '\n') : l + '\n'); });
    pre.append(frag);
    while (pre.childNodes.length > 6000) pre.firstChild.remove();
    if (auto) pre.scrollTop = pre.scrollHeight;
  };
  call('get_log', inst.id).then(lines => { S.logs[inst.id] = lines; append(lines.length ? lines : ['[Hvoya] Журнал пуст — запустите игру.']); }).catch(() => {});
  const on = ev => { if (ev.inst === inst.id) append(ev.lines); };
  listeners.log.add(on);
  reg(() => { listeners.log.delete(on); listeners.game.delete(onGameEv); });
  return h('div', { class: 'pane' },
    h('div', { class: 'pane-bar' },
      h('button', { class: 'btn', title: 'Найти причину вылета по журналу и краш-репорту', onclick: e => analyze(e.currentTarget) }, icon('alert'), 'Анализ вылета'),
      h('button', { class: 'btn', onclick: () => { navigator.clipboard.writeText(pre.textContent); toast('Скопировано'); } }, icon('copy'), 'Копировать'),
      h('button', { class: 'btn', onclick: () => { pre.innerHTML = ''; } }, icon('x'), 'Очистить'),
      h('button', { class: 'btn', onclick: () => call('open_folder', 'instance', inst.id, 'logs') }, icon('folder'), 'Папка logs'),
      h('button', { class: 'btn', onclick: () => call('open_folder', 'instance', inst.id, 'crash-reports') }, icon('folder'), 'Краш-репорты'),
      h('div', { class: 'spacer' }),
      S.running.has(inst.id) ? h('button', { class: 'btn danger', onclick: () => call('kill', inst.id) }, icon('stop'), 'Остановить') : null),
    crashBox, pre);
}

function ramControl(value, onchange) {
  const max = Math.max(2048, Math.floor(S.ram / 512) * 512);
  const lbl = h('b');
  const hint = h('div', { class: 'mem-hint' });
  const upd = v => {
    lbl.textContent = v >= 1024 ? (v / 1024).toFixed(1).replace('.0', '') + ' ГБ' : v + ' МБ';
    const [cls, text] = memHint(v); hint.className = 'mem-hint ' + cls; hint.textContent = text;
  };
  const r = h('input', { type: 'range', min: 512, max, step: 256, value, oninput: e => { upd(+e.target.value); onchange(+e.target.value); } });
  upd(value);
  return h('div', null, h('div', { class: 'row', style: { justifyContent: 'space-between', marginBottom: '4px' } },
    h('span', { class: 'lbl' }, `Максимум памяти (в системе ${Math.round(S.ram / 1024)} ГБ)`), lbl), r, hint);
}

function instSettingsPane(inst) {
  const v = { ramMax: inst.ramMax, javaPath: inst.javaPath || '', jvmArgs: inst.jvmArgs || '', width: inst.width, height: inst.height, server: inst.server || '' };
  const ramWrap = h('div', { class: v.ramMax ? '' : 'hidden' }, ramControl(v.ramMax || S.settings.ramMax, x => { v.ramMax = x; }));
  const java = h('input', { class: 'input', value: v.javaPath, placeholder: 'Из глобальных настроек' });
  const jvm = h('input', { class: 'input', value: v.jvmArgs, placeholder: 'Из глобальных настроек' });
  const w = h('input', { class: 'input', type: 'number', value: v.width || '', placeholder: String(S.settings.width) });
  const hh = h('input', { class: 'input', type: 'number', value: v.height || '', placeholder: String(S.settings.height) });
  const server = h('input', { class: 'input', value: v.server, placeholder: 'play.example.com:25565' });
  const save = async () => {
    const vals = { ramMax: ramWrap.classList.contains('hidden') ? null : (v.ramMax || S.settings.ramMax),
      javaPath: java.value.trim(), jvmArgs: jvm.value.trim(), width: +w.value || null, height: +hh.value || null, server: server.value.trim() };
    if (await safe(call('update_instance', inst.id, vals))) { await refreshInstances(); toast('Сохранено'); }
  };
  return h('div', { class: 'pane' },
    h('div', { class: 'pane-scroll' },
      h('div', { class: 'field' }, h('label', { class: 'check' },
        h('input', { type: 'checkbox', checked: !!v.ramMax, onchange: e => ramWrap.classList.toggle('hidden', !e.target.checked) }), 'Своё количество памяти для этой сборки')),
      ramWrap,
      h('div', { class: 'field', style: { marginTop: '12px' } }, h('label', null, 'Java'),
        h('div', { class: 'row' }, java, h('button', { class: 'btn', onclick: async () => { const p = await safe(call('pick_java')); if (p) java.value = p; } }, 'Обзор…'))),
      h('div', { class: 'field' }, h('label', null, 'Аргументы JVM'), jvm),
      h('div', { class: 'row' }, h('div', { class: 'field' }, h('label', null, 'Ширина окна'), w), h('div', { class: 'field' }, h('label', null, 'Высота окна'), hh)),
      h('div', { class: 'field' }, h('label', null, 'Автоподключение к серверу'), server),
      h('div', { class: 'hint' }, 'Пустые поля берутся из глобальных настроек лаунчера.')),
    h('div', { class: 'modal-f' }, h('button', { class: 'btn primary', onclick: save }, icon('check'), 'Сохранить')));
}

function notesPane(inst) {
  const ta = h('textarea', { class: 'input', style: { flex: 1, resize: 'none', height: '100%' }, value: inst.notes || '', placeholder: 'Заметки к сборке: сиды, IP серверов, что за моды…' });
  const saveNotes = debounce(() => call('update_instance', inst.id, { notes: ta.value }).then(() => { inst.notes = ta.value; }), 500);
  ta.addEventListener('input', saveNotes);
  return h('div', { class: 'pane' }, h('div', { class: 'pane-scroll', style: { display: 'flex' } }, ta));
}

// ================================================================ accounts
function openAccounts() {
  const body = h('div', { class: 'modal-b' });
  const m = modal({ title: 'Аккаунты', cls: 'mid', body });
  const draw = () => {
    body.innerHTML = '';
    const accs = S.accounts.accounts;
    if (!accs.length) body.append(h('div', { class: 'muted', style: { marginBottom: '6px' } }, 'Аккаунтов пока нет. Добавьте офлайн-ник или войдите через Ely.by.'));
    accs.forEach(a => body.append(h('div', { class: 'acc' + (a.id === S.accounts.selected ? ' on' : ''), onclick: async () => {
      const r = await safe(call('select_account', a.id)); if (r) { S.accounts = r; renderAccountBtn(); renderSide(); draw(); }
    } }, headEl(a, 34), h('div', { class: 'am' }, h('div', { class: 'an' }, a.name),
      h('div', { class: 'at' }, h('span', { class: 'acc-type ' + a.type }, a.type === 'elyby' ? 'Ely.by' : 'Офлайн'),
        a.id === S.accounts.selected ? ' · используется' : '')),
    h('button', { class: 'btn sm', title: 'Скин в 3D', onclick: e => { e.stopPropagation(); openSkin(a); } }, icon('user'), 'Скин'),
    h('button', { class: 'btn sm icon danger', title: 'Удалить', onclick: async e => {
      e.stopPropagation();
      if (!await confirmBox('Удалить аккаунт?', `Аккаунт ${a.name} будет удалён из лаунчера.`)) return;
      const r = await safe(call('remove_account', a.id)); if (r) { S.accounts = r; renderAccountBtn(); renderSide(); draw(); }
    } }, icon('trash')))));

    // офлайн
    const nick = h('input', { class: 'input', placeholder: 'Ник (3–16 символов: A-Z, 0-9, _)', maxLength: 16, onkeydown: e => { if (e.key === 'Enter') addOff(); } });
    const addOff = async () => {
      const r = await safe(call('add_offline', nick.value)); if (r) { S.accounts = r; renderAccountBtn(); renderSide(); draw(); toast('Аккаунт добавлен'); }
    };
    body.append(h('div', { class: 'card' }, h('h4', null, icon('user'), 'Офлайн-аккаунт'),
      h('div', { class: 'row' }, nick, h('button', { class: 'btn primary', onclick: addOff }, icon('plus'), 'Добавить')),
      h('div', { class: 'hint', style: { margin: '8px 0 0' } }, 'Подходит для одиночной игры и серверов с online-mode=false.')));

    // ely.by
    const login = h('input', { class: 'input', placeholder: 'Ник или e-mail' });
    const pass = h('input', { class: 'input', type: 'password', placeholder: 'Пароль', onkeydown: e => { if (e.key === 'Enter') addEly(); } });
    const totp = h('input', { class: 'input', placeholder: 'Код 2FA (6 цифр)', inputMode: 'numeric', maxLength: 6, onkeydown: e => { if (e.key === 'Enter') addEly(); } });
    const totpField = h('div', { class: 'field hidden', style: { marginTop: '8px', marginBottom: 0 } }, h('label', null, 'Двухфакторная аутентификация'), totp);
    const elyBtn = h('button', { class: 'btn primary', onclick: () => addEly() }, icon('key'), 'Войти');
    const addEly = async () => {
      if (!login.value || !pass.value) { toast('Введите логин и пароль', 'warn'); return; }
      elyBtn.disabled = true;
      try {
        S.accounts = await call('add_elyby', login.value, pass.value, totp.value);
        renderAccountBtn(); renderSide(); draw(); toast('Вход через Ely.by выполнен');
      } catch (e) {
        if (e.twofactor) { totpField.classList.remove('hidden'); totp.focus(); toast('Введите код из приложения-аутентификатора', 'warn'); }
        else toast(e.message, 'err');
      } finally { elyBtn.disabled = false; }
    };
    body.append(h('div', { class: 'card' }, h('h4', null, icon('key'), 'Ely.by'),
      h('div', { class: 'row' }, login, pass), totpField,
      h('div', { class: 'row', style: { marginTop: '10px' } },
        h('a', { href: '#', class: 'muted', style: { fontSize: '12px' }, onclick: e => { e.preventDefault(); call('open_url', 'https://account.ely.by/register'); } }, 'Регистрация на ely.by ↗'),
        h('div', { class: 'spacer' }), elyBtn),
      h('div', { class: 'hint', style: { margin: '8px 0 0' } }, 'Скины Ely.by и вход на серверы с их авторизацией (через authlib-injector). Пароль не сохраняется — только токен.')));
  };
  draw();
  void m;
}

// ================================================================ settings
function openSettings() {
  const s = { ...S.settings };
  const java = h('input', { class: 'input', value: s.javaPath, placeholder: 'Автоматически (Java от Mojang скачивается сама)' });
  const javaInfo = h('div', { class: 'hint' });
  const jvm = h('textarea', { class: 'input', rows: 2, value: s.jvmArgs });
  const w = h('input', { class: 'input', type: 'number', value: s.width });
  const hh = h('input', { class: 'input', type: 'number', value: s.height });
  const ramMin = h('input', { class: 'input', type: 'number', value: s.ramMin, step: 256 });
  const cf = h('input', { class: 'input', value: s.cfApiKey, placeholder: 'Необязательно', type: 'password' });
  const body = h('div', { class: 'modal-b' },
    h('div', { class: 'card', style: { marginTop: 0 } }, h('h4', null, icon('sliders'), 'Память'),
      ramControl(s.ramMax, v => { s.ramMax = v; }),
      h('div', { class: 'field', style: { marginTop: '10px', maxWidth: '200px', marginBottom: '10px' } }, h('label', null, 'Минимум (МБ)'), ramMin),
      h('label', { class: 'check', style: { display: 'flex' } }, h('input', { type: 'checkbox', checked: s.ramWarnings !== false, onchange: e => { s.ramWarnings = e.target.checked; } }),
        'Предупреждать перед запуском, если памяти слишком много или мало для модов')),
    h('div', { class: 'card' }, h('h4', null, icon('terminal'), 'Java'),
      h('div', { class: 'row' }, java,
        h('button', { class: 'btn', onclick: async () => { const p = await safe(call('pick_java')); if (p) java.value = p; } }, 'Обзор…'),
        h('button', { class: 'btn', onclick: async () => { javaInfo.textContent = 'Проверка…'; const r = await call('test_java', java.value.trim()).catch(e => 'Ошибка: ' + e.message); javaInfo.textContent = r; } }, 'Проверить')),
      javaInfo,
      h('div', { class: 'field', style: { marginTop: '10px', marginBottom: 0 } }, h('label', null, 'Аргументы JVM'), jvm)),
    h('div', { class: 'card' }, h('h4', null, icon('play'), 'Игра'),
      h('div', { class: 'row' }, h('div', { class: 'field' }, h('label', null, 'Ширина окна'), w), h('div', { class: 'field' }, h('label', null, 'Высота окна'), hh)),
      h('div', { class: 'field' }, h('label', null, 'После запуска игры'),
        seg([['minimize', 'Свернуть лаунчер'], ['keep', 'Ничего не делать']], s.afterLaunch === 'keep' ? 'keep' : 'minimize', v => { s.afterLaunch = v; })),
      h('label', { class: 'check', style: { marginBottom: '8px', display: 'flex' } }, h('input', { type: 'checkbox', checked: s.openLogOnCrash, onchange: e => { s.openLogOnCrash = e.target.checked; } }), 'Открывать журнал при вылете игры'),
      h('label', { class: 'check', style: { display: 'flex' } }, h('input', { type: 'checkbox', checked: s.showSnapshots, onchange: e => { s.showSnapshots = e.target.checked; } }), 'Показывать снапшоты в списках версий')),
    h('div', { class: 'card' }, h('h4', null, icon('globe'), 'CurseForge'),
      h('div', { class: 'field', style: { marginBottom: '6px' } }, h('label', null, 'API-ключ'), cf),
      h('div', { class: 'hint', style: { margin: 0 } }, 'Без ключа поиск идёт через публичный прокси. Свой ключ можно бесплатно получить на console.curseforge.com.')),
    discordCard(s),
    updatesCard(s),
    h('div', { class: 'card' }, h('h4', null, icon('folder'), 'Папки'),
      h('div', { class: 'muted', style: { marginBottom: '8px', wordBreak: 'break-all', userSelect: 'text' } }, S.dataDir),
      h('div', { class: 'row' }, h('button', { class: 'btn', onclick: () => call('open_folder', 'launcher') }, 'Папка лаунчера'),
        h('button', { class: 'btn', onclick: () => call('open_folder', 'instances') }, 'Папка сборок'))),
    h('div', { class: 'muted', style: { textAlign: 'center', marginTop: '14px', fontSize: '12px' } }, `Hvoya Launcher ${S.version}`));
  const m = modal({ title: 'Настройки', cls: 'mid', body,
    footer: [h('button', { class: 'btn', onclick: () => m.close() }, 'Отмена'),
      h('button', { class: 'btn primary', onclick: async () => {
        const vals = { ...s, javaPath: java.value.trim(), jvmArgs: jvm.value.trim(), width: +w.value || 1280, height: +hh.value || 720,
          ramMin: +ramMin.value || 512, cfApiKey: cf.value.trim() };
        const r = await safe(call('save_settings', vals));
        if (r) { S.settings = r; m.close(); renderSide(); toast('Настройки сохранены'); }
      } }, icon('check'), 'Сохранить')] });
}

// ================================================================ init
function bindToolbar() {
  document.querySelector('[data-act=new]').onclick = () => openNewInstance();
  document.querySelector('[data-act=import]').onclick = e => {
    const r = e.currentTarget.getBoundingClientRect();
    menu(r.left, r.bottom + 4, [
      { label: 'Из другого лаунчера…', icon: 'swap', act: () => openNewInstance('other') },
      { label: 'Модпак из файла (.mrpack / .zip)…', icon: 'file', act: async () => {
        const id = await safe(call('import_pack')); if (id) toast('Импорт начат — прогресс внизу');
      } },
    ]);
  };
  document.querySelector('[data-act=storage]').onclick = openStorage;
  document.querySelector('[data-act=settings]').onclick = openSettings;
  document.querySelector('[data-act=folders]').onclick = e => {
    const r = e.currentTarget.getBoundingClientRect();
    menu(r.left, r.bottom + 4, [
      { label: 'Папка лаунчера', icon: 'folder', act: () => call('open_folder', 'launcher') },
      { label: 'Папка сборок', icon: 'folder', act: () => call('open_folder', 'instances') },
      ...(S.selected ? ['-', { label: 'Папка выбранной сборки', icon: 'folder', act: () => call('open_folder', 'instance', S.selected) }] : []),
    ]);
  };
  $('#accountBtn').onclick = e => {
    const r = e.currentTarget.getBoundingClientRect();
    const items = [{ header: 'Аккаунты' }];
    S.accounts.accounts.forEach(a => items.push({ label: a.name + (a.type === 'elyby' ? '  · Ely.by' : ''), icon: a.id === S.accounts.selected ? 'check' : null,
      act: async () => { const res = await safe(call('select_account', a.id)); if (res) { S.accounts = res; renderAccountBtn(); renderSide(); } } }));
    items.push('-', { label: 'Управление аккаунтами…', icon: 'user', act: openAccounts });
    menu(r.right - 220, r.bottom + 4, items);
  };
  $('#instSearch').addEventListener('input', e => { S.filter = e.target.value; renderInstances(); });
  $('#instances').addEventListener('click', e => { if (e.target.id === 'instances') select(null); });
  $('#instances').addEventListener('keydown', e => {
    if (!S.selected) return;
    if (e.key === 'Enter') play(S.selected);
    if (e.key === 'Delete') { const i = S.instances.find(x => x.id === S.selected); if (i) deleteInstance(i); }
  });
  document.addEventListener('contextmenu', e => { if (!e.target.closest('input,textarea,.log,.db')) e.preventDefault(); });
}

async function start() {
  fillIcons();
  $('#logo').style.backgroundImage = `url(${pixUrl(PIX.cone)})`;
  bindToolbar();
  try {
    const d = await call('init');
    window._initData = d;
    Object.assign(S, { settings: d.settings, accounts: d.accounts, instances: d.instances, running: new Set(d.running),
      ram: d.ram, version: d.version, dataDir: d.dataDir });
  } catch (e) { toast('Ошибка инициализации: ' + e.message, 'err'); }
  await loadCustomIcons();
  renderAccountBtn();
  renderInstances();
  renderSide();
  renderTasks();
  if (!S.accounts.accounts.length) setTimeout(openAccounts, 300);
  getVersions().catch(() => {});
  initUpdates(window._initData);
}
if (window.pywebview && window.pywebview.api) start();
else window.addEventListener('pywebviewready', start);
