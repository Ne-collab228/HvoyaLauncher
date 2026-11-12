'use strict';
// Хранилище и импорт из других лаунчеров (использует хелперы из app.js).

// ================================================================ storage
const ST_COLORS = { instances: '#4caf6a', assets: '#3d8fe0', versions: '#c58b4a', libraries: '#9b6cd6', runtime: '#e0a541', cache: '#6c757d' };
const ST_LABELS = { instances: 'Сборки', assets: 'Ресурсы игры', versions: 'Версии', libraries: 'Библиотеки', runtime: 'Java', cache: 'Кэш' };
const JAVA_NAMES = { 'jre-legacy': 'Java 8', 'java-runtime-alpha': 'Java 16', 'java-runtime-beta': 'Java 17',
  'java-runtime-gamma': 'Java 17', 'java-runtime-delta': 'Java 21', 'java-runtime-epsilon': 'Java 25' };

function openStorage() {
  const body = h('div', { class: 'modal-b' }, spinner('Подсчёт места…'));
  const m = modal({ title: 'Хранилище', cls: 'mid', body });
  m.el.style.width = '760px';
  const expanded = new Set();

  async function clean(what, arg, confirmText) {
    if (confirmText && !await confirmBox('Удалить?', confirmText, 'Удалить')) return;
    const r = await safe(call('storage_clean', what, arg));
    if (r) { toast(`Освобождено ${fmtSize(r.freed || 0)}`); load(); }
  }
  function row({ title, sub, size, max, acts = [], onclick }) {
    return h('div', { class: 'srow' + (onclick ? ' click' : ''), onclick },
      h('div', { class: 'sn' }, h('div', { class: 't' }, title), sub ? h('div', { class: 's' }, sub) : null),
      h('div', { class: 'sbar' }, h('div', { style: { width: (max && size ? Math.max(1, size / max * 100) : 0) + '%' } })),
      h('div', { class: 'sz' }, size ? fmtSize(size) : '—'),
      h('div', { class: 'acts' }, acts));
  }
  const actBtn = (ic, title, fn, danger) => h('button', {
    class: 'btn sm icon' + (danger ? ' danger' : ''), title, onclick: e => { e.stopPropagation(); fn(); } }, icon(ic));
  const none = text => h('div', { class: 'muted', style: { padding: '6px 10px' } }, text);

  async function load() {
    let d;
    try { d = await call('storage_scan'); } catch (e) {
      body.innerHTML = ''; body.append(h('div', { class: 'list-empty' }, e.message)); return;
    }
    const scrollTop = body.scrollTop;
    body.innerHTML = '';
    const segs = { instances: d.instancesTotal, ...d.shared };
    const total = d.total || 1;

    body.append(
      h('div', { class: 'st-top' },
        h('div', null, h('div', { class: 'lbl' }, 'Всего занято'), h('div', { class: 'st-total' }, d.total ? fmtSize(d.total) : '0 МБ')),
        h('div', { class: 'spacer' }),
        h('div', { style: { textAlign: 'right' } },
          h('div', { class: 'lbl' }, 'Можно освободить'),
          h('div', { class: d.reclaimable ? 'unused' : '', style: { fontSize: '16px', fontWeight: 600, marginBottom: '6px' } }, d.reclaimable ? fmtSize(d.reclaimable) : '0 МБ'),
          h('button', { class: 'btn primary sm', disabled: !d.reclaimable || S.tasks.size > 0,
            onclick: () => clean('unused', null, `Будут удалены версии, Java и ресурсы, которые не нужны ни одной сборке, и кэш (${fmtSize(d.reclaimable)}). Сборки, миры и моды не пострадают.`) },
          icon('trash'), 'Очистить неиспользуемое'))),
      h('div', { class: 'stack' }, Object.entries(segs).filter(([, v]) => v > 0).map(([k, v]) =>
        h('div', { title: `${ST_LABELS[k]}: ${fmtSize(v)}`, style: { width: v / total * 100 + '%', background: ST_COLORS[k] } }))),
      h('div', { class: 'legend' }, Object.entries(segs).map(([k, v]) =>
        h('span', null, h('i', { class: 'dot', style: { background: ST_COLORS[k] } }), ST_LABELS[k], h('b', null, v ? fmtSize(v) : '0')))));

    // сборки
    const maxI = Math.max(1, ...d.instances.map(i => i.size));
    const secI = h('div', { class: 'st-sec' }, h('h4', null, 'Сборки', h('span', { class: 'spacer' }), h('span', null, fmtSize(d.instancesTotal || 0))));
    if (!d.instances.length) secI.append(none('Сборок нет'));
    d.instances.forEach(i => {
      const open = expanded.has(i.id);
      const logs = (i.parts.find(p => p.key === 'logs') || {}).size || 0;
      const top = i.parts.slice(0, 3).map(p => `${p.label.toLowerCase()} ${fmtSize(p.size)}`).join(', ');
      secI.append(row({
        title: [icon('chev', 'sm'), ' ', i.name],
        sub: `${LOADER_NAMES[i.loader]} ${i.mc}${top ? ' · ' + top : ''}`,
        size: i.size, max: maxI,
        onclick: () => { open ? expanded.delete(i.id) : expanded.add(i.id); load(); },
        acts: [actBtn('folder', 'Открыть папку', () => call('open_folder', 'instance', i.id)),
          logs ? actBtn('trash', `Удалить логи и краш-репорты (${fmtSize(logs)})`, () => clean('logs', i.id)) : null],
      }));
      if (open) {
        secI.append(h('div', { class: 'sparts' }, i.parts.length
          ? i.parts.map(p => h('div', null, h('span', null, p.label), h('span', null, fmtSize(p.size))))
          : h('div', null, 'Пусто — файлы появятся после первого запуска')));
      }
    });
    body.append(secI);

    // версии
    const maxV = Math.max(1, ...d.versions.map(v => v.size));
    const secV = h('div', { class: 'st-sec' }, h('h4', null, 'Версии игры и загрузчики', h('span', { class: 'spacer' }), h('span', null, fmtSize(d.shared.versions || 0))));
    if (!d.versions.length) secV.append(none('Ничего не скачано'));
    d.versions.forEach(v => secV.append(row({
      title: v.id,
      sub: v.usedBy.length ? 'Используется: ' + v.usedBy.join(', ') : h('span', { class: 'unused' }, 'Не используется ни одной сборкой'),
      size: v.size, max: maxV,
      acts: [v.usedBy.length ? null : actBtn('trash', 'Удалить', () => clean('version', v.id), true)],
    })));
    body.append(secV);

    // java
    const secJ = h('div', { class: 'st-sec' }, h('h4', null, 'Java', h('span', { class: 'spacer' }), h('span', null, fmtSize(d.shared.runtime || 0))));
    if (!d.runtimes.length) secJ.append(none('Java ещё не скачивалась — она загрузится при первом запуске'));
    d.runtimes.forEach(r => secJ.append(row({
      title: `${JAVA_NAMES[r.id] || 'Java'} (${r.id})`,
      sub: r.used ? 'Нужна установленным сборкам' : h('span', { class: 'unused' }, 'Не используется'),
      size: r.size, max: d.shared.runtime,
      acts: [r.used ? null : actBtn('trash', 'Удалить', () => clean('runtime', r.id), true)],
    })));
    body.append(secJ);

    // общие
    body.append(h('div', { class: 'st-sec' }, h('h4', null, 'Общие файлы'),
      row({ title: 'Ресурсы игры (звуки, языки)', size: d.shared.assets, max: total,
        sub: d.assetsUnused ? h('span', { class: 'unused' }, `Не используется: ${fmtSize(d.assetsUnused)}`) : 'Общие для всех сборок' }),
      row({ title: 'Библиотеки', sub: 'Общие для всех сборок, нужны для запуска', size: d.shared.libraries, max: total }),
      row({ title: 'Кэш загрузок', sub: 'Временные файлы модпаков', size: d.shared.cache, max: total,
        acts: [d.shared.cache ? actBtn('trash', 'Очистить кэш', () => clean('cache')) : null] }),
      h('div', { class: 'row', style: { marginTop: '10px' } },
        h('span', { class: 'muted', style: { fontSize: '12px', wordBreak: 'break-all', flex: 1, userSelect: 'text' } }, d.dataDir),
        h('button', { class: 'btn sm', onclick: () => call('open_folder', 'launcher') }, icon('folder'), 'Открыть'),
        h('button', { class: 'btn sm', onclick: load }, icon('refresh'), 'Обновить'))));
    body.scrollTop = scrollTop;
  }
  load();
}

// ================================================================ import from other launchers
function importOtherPane(m) {
  const list = h('div', { class: 'clist' });
  const scroll = h('div', { class: 'pane-scroll', style: { padding: 0 } }, list);

  function item(it) {
    const name = h('input', { class: 'input', value: it.name, style: { width: '190px' }, title: 'Название новой сборки' });
    const mcSel = h('select', { class: 'input', style: { width: '105px' } });
    const fillMc = vs => {
      mcSel.innerHTML = '';
      if (!it.mc) mcSel.append(h('option', { value: '' }, 'Версия?'));
      const ids = vs.filter(v => v.type === 'release' || v.id === it.mc).map(v => v.id);
      if (it.mc && !ids.includes(it.mc)) ids.unshift(it.mc);
      ids.forEach(id => mcSel.append(h('option', { value: id, selected: id === it.mc }, id)));
    };
    fillMc([]);
    getVersions().then(fillMc).catch(() => {});
    const ldSel = h('select', { class: 'input', style: { width: '100px' } },
      LOADER_OPTS.map(([v, l]) => h('option', { value: v, selected: v === it.loader }, v === 'vanilla' ? 'Vanilla' : l)));
    const btn = h('button', { class: 'btn primary sm' }, icon('download'), 'Импорт');
    btn.onclick = async () => {
      if (!mcSel.value) { toast('Выберите версию Minecraft', 'warn'); return; }
      const changed = ldSel.value !== it.loader || mcSel.value !== it.mc;
      const data = { ...it, name: name.value.trim() || it.name, mc: mcSel.value, loader: ldSel.value,
        loaderVersion: changed ? '' : it.loaderVersion };
      btn.disabled = true;
      const id = await safe(call('import_instance', data));
      if (id) { toast('Импорт начат — файлы копируются, прогресс внизу'); m.close(); } else btn.disabled = false;
    };
    const loaderTxt = it.loader !== 'vanilla' ? `${LOADER_NAMES[it.loader]} ${it.loaderVersion || ''} · ` : '';
    return h('div', { class: 'imp-item' },
      h('div', { class: 'cic', style: { width: '34px', height: '34px', borderRadius: '6px', background: 'var(--panel3)', display: 'flex',
        alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', flex: 'none' } }, icon('swap')),
      h('div', { class: 'im' }, h('div', { class: 'it' }, it.name),
        h('div', { class: 'is', title: it.gameDir }, `${it.source} · ${loaderTxt}${it.mc || 'версия не определена'}`)),
      name, mcSel, ldSel, btn);
  }
  function show(items, emptyText) {
    list.innerHTML = '';
    if (!items.length) { list.append(h('div', { class: 'list-empty' }, icon('swap', 'lg'), emptyText)); return; }
    items.forEach(it => list.append(item(it)));
  }
  async function scan() {
    list.innerHTML = '';
    list.append(spinner('Ищу сборки других лаунчеров…'));
    const items = await call('import_scan').catch(e => { toast(e.message, 'err'); return []; });
    show(items, 'Автоматически ничего не найдено. Нажмите «Выбрать папку» и укажите папку сборки или лаунчера.');
  }
  scan();
  return h('div', { class: 'pane' },
    h('div', { class: 'pane-bar' },
      h('div', { class: 'muted', style: { flex: 1, fontSize: '12px', minWidth: '200px' } },
        'Prism / MultiMC / PineconeMC, CurseForge, Modrinth App, ATLauncher, TLauncher и любая папка .minecraft. Файлы копируются — исходная сборка не изменится.'),
      h('button', { class: 'btn', onclick: scan }, icon('refresh'), 'Обновить'),
      h('button', { class: 'btn primary', onclick: async () => {
        const items = await safe(call('import_pick_folder'));
        if (items) show(items, 'В этой папке не найдено сборок Minecraft');
      } }, icon('folder'), 'Выбрать папку…')),
    scroll);
}

// ================================================================ self-update
function showUpdateBadge(info) {
  const right = $('#statusRight');
  let b = $('#updBadge');
  if (!b) {
    b = h('button', { id: 'updBadge', class: 'upd-badge', onclick: () => openUpdate(info) });
    right.parentNode.insertBefore(b, right.nextSibling);
  }
  b.textContent = `Доступна версия ${info.latest} — обновить`;
}

function openUpdate(info) {
  const notes = h('div', { class: 'upd-notes' }, info.notes ? cleanMd(info.notes) : 'Список изменений — на странице релиза.');
  const btn = h('button', { class: 'btn primary', disabled: !info.canAuto }, icon('download'), 'Обновить и перезапустить');
  const m = modal({
    title: `Обновление ${info.current} → ${info.latest}`, cls: 'mid',
    body: h('div', { class: 'modal-b' }, notes,
      info.canAuto ? h('div', { class: 'hint', style: { marginTop: '12px', marginBottom: 0 } },
        'Лаунчер скачает новую версию, закроется и откроется уже обновлённым. Сборки, миры и аккаунты останутся на месте.')
        : h('div', { class: 'hint', style: { marginTop: '12px', marginBottom: 0 } }, 'Автообновление недоступно в этом режиме — скачайте новую версию со страницы релиза.')),
    footer: [
      h('button', { class: 'btn', onclick: () => call('open_url', info.url) }, icon('ext'), 'Страница релиза'),
      h('div', { class: 'spacer' }),
      btn],
  });
  btn.onclick = async () => {
    if (S.running.size) { toast('Сначала закройте игру', 'warn'); return; }
    btn.disabled = true;
    btn.lastChild.textContent = 'Загрузка…';
    const id = await safe(call('apply_update'));
    if (!id) { btn.disabled = false; btn.lastChild.textContent = 'Обновить и перезапустить'; return; }
    const onTask = ev => {
      if (ev.id !== id) return;
      if (ev.done) {
        listeners.task.delete(onTask);
        if (ev.error) { btn.disabled = false; btn.lastChild.textContent = 'Повторить'; }
        else btn.lastChild.textContent = 'Перезапуск…';
      } else if (ev.max) btn.lastChild.textContent = `Загрузка ${Math.round(ev.progress / ev.max * 100)}%`;
    };
    listeners.task.add(onTask);
  };
  void m;
}

async function checkUpdates(manual) {
  let info;
  try { info = await call('check_update'); } catch (e) {
    if (manual) toast('Не удалось проверить обновления: ' + e.message, 'err');
    return null;
  }
  S.update = info;
  if (info.available) {
    showUpdateBadge(info);
    if (!manual) toast(`Вышла новая версия лаунчера: ${info.latest}`);
    else openUpdate(info);
  } else if (manual) toast(`У вас последняя версия (${info.current})`);
  return info;
}

function initUpdates(d) {
  if (d && d.justUpdated) toast(`Лаунчер обновлён до версии ${d.version}`);
  // при запуске и дальше каждые 5 минут, пока лаунчер открыт
  let installing = false;
  const autoInstall = async () => {
    if (installing || S.settings.autoInstallUpdates !== true) return;
    if (!(S.update && S.update.available && S.update.canAuto)) return;
    if (S.running.size) return;            // во время игры не обновляемся — попробуем на следующей проверке
    installing = true;
    toast(`Устанавливаю обновление лаунчера ${S.update.latest}…`);
    const id = await call('apply_update').catch(() => null);
    if (!id) { installing = false; return; }
    const onTask = ev => {
      if (ev.id !== id || !ev.done) return;
      listeners.task.delete(onTask);
      if (ev.error) installing = false;    // например, игра запустилась во время загрузки
    };
    listeners.task.add(onTask);
  };
  const auto = async () => {
    if (S.settings.checkUpdates === false) return;
    if (!(S.update && S.update.available)) await checkUpdates(false);
    await autoInstall();
  };
  setTimeout(auto, 2500);
  setInterval(auto, 5 * 60 * 1000);
}

function updatesCard(s) {
  const status = h('span', { class: 'muted' }, S.update && S.update.available ? `доступна ${S.update.latest}` : '');
  return h('div', { class: 'card' }, h('h4', null, icon('refresh'), 'Обновления'),
    h('div', { class: 'row', style: { marginBottom: '8px' } },
      h('span', null, `Версия ${S.version}`), status, h('div', { class: 'spacer' }),
      h('button', { class: 'btn sm', onclick: async e => {
        const b = e.currentTarget; b.disabled = true;
        const info = await checkUpdates(true); b.disabled = false;
        if (info) status.textContent = info.available ? `доступна ${info.latest}` : 'последняя версия';
      } }, icon('refresh'), 'Проверить')),
    h('label', { class: 'check', style: { display: 'flex' } },
      h('input', { type: 'checkbox', checked: s.checkUpdates !== false, onchange: e => { s.checkUpdates = e.target.checked; } }),
      'Проверять обновления автоматически (при запуске и каждые 5 минут)'),
    h('label', { class: 'check', style: { display: 'flex' } },
      h('input', { type: 'checkbox', checked: s.autoInstallUpdates === true, onchange: e => { s.autoInstallUpdates = e.target.checked; } }),
      'Загружать и устанавливать обновления автоматически (не во время игры)'));
}
