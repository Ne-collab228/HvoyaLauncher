'use strict';
// v2.1: серверы сборки, проверка папки модов, ярлык на рабочий стол, запуск по запросу из ярлыка.

// ================================================================ серверы
function serversPane(inst, reg) {
  let list = [];
  let pings = [];
  const box = h('div', { class: 'clist' });
  const draw = () => {
    box.innerHTML = '';
    if (!list.length) {
      box.append(h('div', { class: 'list-empty' }, icon('server', 'lg'), 'В этой сборке пока нет серверов',
        h('div', { style: { fontSize: '12px' } }, 'Добавьте адрес — сервер появится и в игре, в списке «Сетевая игра».'),
        h('button', { class: 'btn primary', onclick: () => edit(null) }, icon('plus'), 'Добавить сервер')));
      return;
    }
    list.forEach((s, i) => {
      const p = pings[i];
      const st = !p ? h('span', { class: 'muted' }, 'проверка…')
        : p.ok ? h('span', { style: { color: '#5fd38d' } }, `${p.online}/${p.max}`, p.ping != null ? ` · ${p.ping} мс` : '')
          : h('span', { class: 'muted', title: p.error }, 'не отвечает');
      const ic = (p && p.favicon) || s.icon;
      box.append(h('div', { class: 'citem', oncontextmenu: e => { e.preventDefault(); sMenu(i, e.clientX, e.clientY); } },
        h('div', { class: 'cic', style: ic ? { backgroundImage: `url(${ic})`, backgroundSize: 'cover', imageRendering: 'pixelated' } : null }, ic ? null : icon('server')),
        h('div', { class: 'cmain' },
          h('div', { class: 'ct' }, s.name, '  ', st),
          h('div', { class: 'cs' }, s.ip + (p && p.ok && p.version ? ' · ' + p.version : '')),
          p && p.ok && p.motd ? h('div', { class: 'cs', style: { whiteSpace: 'pre-line' } }, p.motd) : null),
        h('button', { class: 'btn sm primary', title: 'Запустить сборку и сразу зайти на сервер', onclick: () => play(inst.id, s.ip) }, icon('play'), 'Играть'),
        h('button', { class: 'btn sm icon', title: 'Ещё', onclick: e => { const r = e.currentTarget.getBoundingClientRect(); sMenu(i, r.left - 150, r.bottom + 4); } }, icon('dots'))));
    });
  };
  const guard = () => {
    if (S.running.has(inst.id)) { toast('Сначала закройте игру — иначе она перезапишет список серверов', 'warn'); return false; }
    return true;
  };
  function sMenu(i, x, y) {
    menu(x, y, [
      { label: 'Играть и зайти', icon: 'play', act: () => play(inst.id, list[i].ip) },
      { label: 'Изменить', icon: 'edit', act: () => edit(i) },
      { label: 'Скопировать адрес', icon: 'copy', act: () => { navigator.clipboard.writeText(list[i].ip); toast('Адрес скопирован'); } },
      i > 0 ? { label: 'Выше', icon: 'chev', act: () => move(i, -1) } : null,
      i < list.length - 1 ? { label: 'Ниже', icon: 'chev', act: () => move(i, 1) } : null,
      '-',
      { label: 'Удалить', icon: 'trash', danger: true, act: async () => {
        if (!guard()) return;
        const r = await safe(call('servers_remove', inst.id, i)); if (r) { list = r; pings = []; draw(); refreshPings(); }
      } },
    ].filter(Boolean));
  }
  const move = async (i, d) => { if (!guard()) return; const r = await safe(call('servers_move', inst.id, i, d)); if (r) { list = r; pings = []; draw(); refreshPings(); } };
  const edit = i => {
    const cur = i == null ? { name: '', ip: '' } : list[i];
    const name = h('input', { class: 'input', value: cur.name, placeholder: 'Название' });
    const ip = h('input', { class: 'input', value: cur.ip, placeholder: 'play.example.com или адрес:порт' });
    const m = modal({ title: i == null ? 'Новый сервер' : 'Изменить сервер', cls: 'mid',
      body: h('div', { class: 'modal-b' }, h('div', { class: 'field' }, h('label', null, 'Название'), name), h('div', { class: 'field' }, h('label', null, 'Адрес'), ip)),
      footer: [h('button', { class: 'btn', onclick: () => m.close() }, 'Отмена'),
        h('button', { class: 'btn primary', onclick: async () => {
          if (!guard()) return;
          const r = await safe(i == null ? call('servers_add', inst.id, name.value, ip.value) : call('servers_edit', inst.id, i, name.value, ip.value));
          if (r) { list = r; pings = []; m.close(); draw(); refreshPings(); }
        } }, icon('check'), 'Сохранить')] });
    setTimeout(() => (i == null ? name : ip).focus(), 50);
  };
  let alive = true;
  reg(() => { alive = false; });
  const refreshPings = async () => {
    if (!list.length) return;
    const r = await call('servers_ping', inst.id).catch(() => null);
    if (alive && r && r.length === list.length) { pings = r; draw(); }
  };
  const load = async () => { const r = await safe(call('servers_list', inst.id)); if (r) { list = r; pings = []; draw(); refreshPings(); } };
  box.append(spinner());
  load();
  return h('div', { class: 'pane' },
    h('div', { class: 'pane-bar' },
      h('button', { class: 'btn primary', onclick: () => edit(null) }, icon('plus'), 'Добавить сервер'),
      h('button', { class: 'btn icon', title: 'Обновить', onclick: () => { pings = []; draw(); refreshPings(); } }, icon('refresh')),
      h('div', { class: 'spacer' }),
      h('span', { class: 'muted' }, 'Список общий с игрой (servers.dat)')),
    h('div', { class: 'pane-scroll', style: { padding: 0 } }, box));
}

// ================================================================ проверка модов
function modcheckPane(inst, reg) {
  const box = h('div', { class: 'pane-scroll' });
  const sum = h('span', { class: 'muted' });
  let alive = true;
  const fileRow = f => h('div', { class: 'row', style: { gap: '6px', margin: '3px 0' } },
    h('span', { style: { flex: 1, wordBreak: 'break-all' } }, f),
    f.endsWith('.disabled') ? null : h('button', { class: 'btn sm', onclick: async () => {
      if (await safe(call('toggle_content', inst.id, 'mods', f, false))) run();
    } }, 'Отключить'),
    h('button', { class: 'btn sm danger', title: 'Удалить файл', onclick: async () => {
      if (!await confirmBox('Удалить файл?', `«${f}» будет удалён из папки mods.`)) return;
      if (await safe(call('delete_content', inst.id, 'mods', [f]))) run();
    } }, icon('trash')));
  const draw = r => {
    box.innerHTML = '';
    sum.textContent = `${r.stats.jars} файлов · ${r.stats.mods} модов` + (r.stats.disabled ? ` · отключено ${r.stats.disabled}` : '');
    if (!r.issues.some(i => i.level !== 'info')) box.append(h('div', { class: 'list-empty' }, icon('check', 'lg'), 'Проблем не найдено',
      h('div', { style: { fontSize: '12px' } }, 'Дубликатов, чужих и повреждённых модов, недостающих зависимостей нет.')));
    r.issues.forEach(i => box.append(h('div', { class: 'opt-note ' + (i.level === 'error' ? 'bad' : 'warn'), style: { display: 'block', margin: '10px 16px' } },
      h('div', { class: 'row', style: { gap: '8px' } }, icon(i.level === 'info' ? 'info' : 'alert'), h('b', { style: { flex: 1 } }, i.title),
        i.dep ? h('button', { class: 'btn sm primary', title: 'Найти на Modrinth и поставить', onclick: async e => {
          const b = e.currentTarget; b.disabled = true;
          if (await safe(call('modcheck_install', inst.id, i.dep))) toast('Установка начата — прогресс внизу');
          b.disabled = false;
        } }, icon('download'), 'Установить') : null,
        i.dep ? h('button', { class: 'btn sm', onclick: () => call('open_url', 'https://modrinth.com/mods?q=' + encodeURIComponent(i.dep)) }, icon('ext'), 'Искать') : null),
      h('div', { class: 'muted', style: { margin: '4px 0 2px', whiteSpace: 'pre-line' } }, i.text),
      ...i.files.map(fileRow))));
  };
  const run = async () => {
    box.innerHTML = ''; box.append(spinner());
    const r = await safe(call('modcheck', inst.id));
    if (alive && r) draw(r);
  };
  const onTask = ev => { if (ev.done && ev.inst === inst.id) run(); };
  listeners.task.add(onTask);
  reg(() => { alive = false; listeners.task.delete(onTask); });
  run();
  return h('div', { class: 'pane' },
    h('div', { class: 'pane-bar' },
      h('button', { class: 'btn primary', onclick: run }, icon('refresh'), 'Проверить снова'), sum,
      h('div', { class: 'spacer' }),
      h('button', { class: 'btn', onclick: () => call('open_folder', 'instance', inst.id, 'mods') }, icon('folder'), 'Папка mods')),
    box);
}

// ================================================================ ярлык на рабочий стол
async function makeShortcut(inst) {
  let png = '';
  try {
    const img = new Image();
    img.src = instIconUrl(inst);
    await img.decode();
    const c = document.createElement('canvas'); c.width = c.height = 256;
    const x = c.getContext('2d'); x.imageSmoothingEnabled = false;
    const k = Math.min(256 / img.naturalWidth, 256 / img.naturalHeight);
    const w = img.naturalWidth * k, hh = img.naturalHeight * k;
    x.drawImage(img, (256 - w) / 2, (256 - hh) / 2, w, hh);
    png = c.toDataURL('image/png');
  } catch { /* без иконки */ }
  if (await safe(call('create_shortcut', inst.id, png))) toast(`Ярлык «${inst.name}» создан на рабочем столе`);
}

// ================================================================ запуск по запросу (ярлык / вторая копия)
function autoLaunch(id) {
  if (!id) return;
  if (!S.instances.some(i => i.id === id)) { toast('Сборка из ярлыка не найдена', 'warn'); return; }
  select(id);
  play(id);
}
setInterval(async () => {
  if (!window.pywebview || !window.pywebview.api || !window._initData) return;
  const id = await call('poll_launch_request').catch(() => null);
  if (id) autoLaunch(id);
}, 1500);
// запуск из ярлыка при старте лаунчера: ждём, пока start() загрузит данные
(function waitInit(n) {
  if (window._initData && S.instances && S.instances.length) { autoLaunch(window._initData.autoLaunch); return; }
  if (n < 40) setTimeout(() => waitInit(n + 1), 250);
})(0);
