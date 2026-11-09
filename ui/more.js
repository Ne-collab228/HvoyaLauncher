'use strict';
// Миры и бэкапы, скриншоты, экспорт сборки, анализ вылетов, Discord (использует хелперы из app.js).

S.crash = {};

// ================================================================ worlds
function worldsPane(inst, reg) {
  const list = h('div', { class: 'clist' });
  const bList = h('div', { class: 'clist' });
  const scroll = h('div', { class: 'pane-scroll', style: { padding: 0 } }, list,
    h('div', { class: 'sec-h' }, icon('archive'), 'Резервные копии', h('div', { class: 'spacer' }),
      h('button', { class: 'btn sm', onclick: () => call('open_folder', 'backups', inst.id) }, icon('folder'), 'Папка бэкапов')),
    bList);
  let data = { worlds: [], backups: [] };

  const others = () => S.instances.filter(i => i.id !== inst.id);
  const draw = () => {
    list.innerHTML = '';
    if (!data.worlds.length) {
      list.append(h('div', { class: 'list-empty' }, icon('globe', 'lg'), 'В этой сборке пока нет миров',
        h('button', { class: 'btn', onclick: importZip }, icon('upload'), 'Импортировать мир из .zip')));
    }
    data.worlds.forEach(w => list.append(h('div', { class: 'witem', oncontextmenu: e => { e.preventDefault(); wMenu(w, e.clientX, e.clientY); } },
      h('div', { class: 'wic', style: w.icon ? { backgroundImage: `url(${w.icon})` } : null }, w.icon ? null : icon('globe')),
      h('div', { class: 'cmain' },
        h('div', { class: 'ct' }, w.name, w.broken ? h('span', { class: 'muted' }, '  (level.dat повреждён)') : null),
        h('div', { class: 'cs' }, [w.mode, w.cheats && !w.hardcore ? 'читы' : '', w.version, fmtSize(w.size)].filter(Boolean).join(' · ')),
        h('div', { class: 'cs' }, `Последняя игра: ${fmtDate(w.lastPlayed)}`, w.folder !== w.name ? ` · папка «${w.folder}»` : '')),
      h('button', { class: 'btn sm', title: 'Сохранить копию мира в zip', onclick: () => backup(w) }, icon('archive'), 'Бэкап'),
      h('button', { class: 'btn sm icon', title: 'Ещё', onclick: e => { const r = e.currentTarget.getBoundingClientRect(); wMenu(w, r.left - 150, r.bottom + 4); } }, icon('dots')))));

    bList.innerHTML = '';
    if (!data.backups.length) bList.append(h('div', { class: 'muted', style: { padding: '8px 16px 18px' } },
      'Бэкапов пока нет. Нажмите «Бэкап» у мира — копия сохранится в zip и не пропадёт, даже если удалить сборку.'));
    data.backups.forEach(b => bList.append(h('div', { class: 'citem' },
      h('div', { class: 'cic' }, icon('archive')),
      h('div', { class: 'cmain' }, h('div', { class: 'ct' }, b.world),
        h('div', { class: 'cs' }, `${new Date(b.time * 1000).toLocaleString('ru', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })} · ${fmtSize(b.size)}`)),
      h('button', { class: 'btn sm', onclick: () => restore(b) }, icon('refresh'), 'Восстановить'),
      h('button', { class: 'btn sm icon danger', title: 'Удалить бэкап', onclick: async () => {
        if (!await confirmBox('Удалить бэкап?', `Бэкап мира «${b.world}» от ${fmtDate(b.time)} будет удалён.`)) return;
        const r = await safe(call('backup_delete', inst.id, b.file)); if (r) { data.backups = r; draw(); }
      } }, icon('trash')))));
  };
  const load = async () => { const r = await safe(call('worlds', inst.id)); if (r) { data = r; draw(); } };

  const backup = async w => { if (await safe(call('world_backup', inst.id, w ? w.folder : null))) toast('Бэкап начат — прогресс внизу'); };
  const restore = async b => {
    if (!await confirmBox('Восстановить мир?', `Мир из бэкапа появится рядом с существующими (текущий мир «${b.world}», если он есть, не изменится).`, 'Восстановить', false)) return;
    await safe(call('backup_restore', inst.id, b.file));
  };
  const importZip = () => safe(call('world_import', inst.id));
  function wMenu(w, x, y) {
    const items = [
      { label: 'Сделать бэкап', icon: 'archive', act: () => backup(w) },
      { label: 'Открыть папку мира', icon: 'folder', act: () => call('open_folder', 'instance', inst.id, 'saves/' + w.folder) },
      w.seed ? { label: 'Скопировать сид', icon: 'copy', act: () => { navigator.clipboard.writeText(w.seed); toast('Сид скопирован: ' + w.seed); } } : null,
    ].filter(Boolean);
    const o = others();
    if (o.length) {
      items.push('-', { header: 'Копировать в сборку' });
      o.slice(0, 12).forEach(t => items.push({ label: t.name, icon: 'swap', act: async () => {
        const r = await safe(call('world_copy', inst.id, w.folder, t.id));
        if (r) toast(`Мир скопирован в «${t.name}»`);
      } }));
    }
    items.push('-', { label: 'Удалить в Корзину', icon: 'trash', danger: true, act: async () => {
      if (S.running.has(inst.id)) { toast('Сначала закройте игру', 'warn'); return; }
      if (!await confirmBox('Удалить мир?', `Мир «${w.name}» будет перемещён в Корзину Windows.`)) return;
      const r = await safe(call('world_delete', inst.id, w.folder)); if (r) { data.worlds = r; draw(); toast('Мир перемещён в Корзину'); }
    } });
    menu(x, y, items);
  }

  const onTask = ev => { if (ev.done && ev.inst === inst.id) load(); };
  listeners.task.add(onTask);
  reg(() => listeners.task.delete(onTask));
  list.append(spinner());
  load();
  return h('div', { class: 'pane' },
    h('div', { class: 'pane-bar' },
      h('button', { class: 'btn primary', onclick: () => backup(null) }, icon('archive'), 'Бэкап всех миров'),
      h('button', { class: 'btn', onclick: importZip }, icon('upload'), 'Импорт из .zip'),
      h('button', { class: 'btn icon', title: 'Обновить', onclick: load }, icon('refresh')),
      h('div', { class: 'spacer' }),
      h('button', { class: 'btn', onclick: () => call('open_folder', 'instance', inst.id, 'saves') }, icon('folder'), 'Папка saves')),
    scroll);
}

// ================================================================ screenshots
function shotsPane(inst, reg) {
  let shots = [];
  const grid = h('div', { class: 'shots' });
  const count = h('span', { class: 'muted' });
  const draw = () => {
    grid.innerHTML = '';
    count.textContent = shots.length ? `${shots.length} шт. · ${fmtSize(shots.reduce((a, s) => a + s.size, 0))}` : '';
    if (!shots.length) {
      grid.append(h('div', { class: 'list-empty', style: { gridColumn: '1 / -1' } }, icon('camera', 'lg'),
        'Скриншотов пока нет', h('div', { style: { fontSize: '12px' } }, 'В игре нажмите F2 — снимок появится здесь.')));
      return;
    }
    shots.forEach((s, i) => grid.append(h('div', { class: 'shot', title: s.name,
      onclick: () => viewer(i), oncontextmenu: e => { e.preventDefault(); sMenu(s, e.clientX, e.clientY); } },
    h('img', { src: s.url, loading: 'lazy', decoding: 'async', draggable: false }),
    h('span', null, fmtDate(s.time)))));
  };
  const load = async () => { const r = await safe(call('screenshots', inst.id)); if (r) { shots = r; draw(); } };
  const copy = async s => { if (await safe(call('screenshot_copy', inst.id, s.name))) toast('Скриншот скопирован в буфер обмена'); };
  const del = async (s, after) => {
    const r = await safe(call('screenshots_delete', inst.id, [s.name]));
    if (r) { shots = r; draw(); toast('Перемещён в Корзину'); after && after(); }
  };
  function sMenu(s, x, y) {
    menu(x, y, [
      { label: 'Открыть', icon: 'image', act: () => viewer(shots.indexOf(s)) },
      { label: 'Копировать', icon: 'copy', act: () => copy(s) },
      { label: 'Показать в папке', icon: 'folder', act: () => call('screenshot_reveal', inst.id, s.name) },
      '-',
      { label: 'Удалить в Корзину', icon: 'trash', danger: true, act: () => del(s) },
    ]);
  }
  function viewer(idx) {
    const img = h('img', { draggable: false });
    const cap = h('div', { class: 'lb-cap' });
    const go = d => { if (!shots.length) { close(); return; } idx = (idx + d + shots.length) % shots.length; show(); };
    const show = () => {
      const s = shots[idx];
      img.src = s.url;
      cap.textContent = `${s.name} · ${fmtSize(s.size)} · ${idx + 1} / ${shots.length}`;
    };
    const key = e => {
      if (e.key === 'Escape') { e.stopPropagation(); close(); } else if (e.key === 'ArrowLeft') go(-1); else if (e.key === 'ArrowRight') go(1);
    };
    const close = () => { lb.remove(); document.removeEventListener('keydown', key, true); };
    const btn = (ic, title, fn) => h('button', { class: 'lb-btn', title, onclick: e => { e.stopPropagation(); fn(); } }, icon(ic));
    const lb = h('div', { class: 'lightbox', onclick: e => { if (e.target === lb || e.target.classList.contains('lb-stage')) close(); } },
      h('div', { class: 'lb-top' }, cap, h('div', { class: 'spacer' }),
        btn('copy', 'Копировать', () => copy(shots[idx])),
        btn('folder', 'Показать в папке', () => call('screenshot_reveal', inst.id, shots[idx].name)),
        btn('trash', 'Удалить в Корзину', () => del(shots[idx], () => { idx = Math.min(idx, shots.length - 1); if (shots.length) show(); else close(); })),
        btn('x', 'Закрыть (Esc)', close)),
      h('div', { class: 'lb-stage' }, img),
      shots.length > 1 ? [h('button', { class: 'lb-nav l', onclick: e => { e.stopPropagation(); go(-1); } }, icon('chev')),
        h('button', { class: 'lb-nav r', onclick: e => { e.stopPropagation(); go(1); } }, icon('chev'))] : null);
    document.addEventListener('keydown', key, true);
    document.body.append(lb);
    show();
  }
  reg(() => {});
  grid.append(spinner());
  load();
  return h('div', { class: 'pane' },
    h('div', { class: 'pane-bar' },
      h('button', { class: 'btn icon', title: 'Обновить', onclick: load }, icon('refresh')), count,
      h('div', { class: 'spacer' }),
      h('button', { class: 'btn', onclick: () => call('open_folder', 'instance', inst.id, 'screenshots') }, icon('folder'), 'Папка скриншотов')),
    h('div', { class: 'pane-scroll' }, grid));
}

// ================================================================ export
async function openExport(inst) {
  let fmt = 'mrpack';
  const name = h('input', { class: 'input', value: inst.name });
  const ver = h('input', { class: 'input', value: '1.0', style: { width: '110px' } });
  const summary = h('input', { class: 'input', placeholder: 'Необязательно' });
  const list = h('div', { class: 'exp-list' }, spinner());
  const hint = h('div', { class: 'hint', style: { marginTop: '6px' } });
  const total = h('span', { class: 'muted' });
  let entries = [];
  const fmtHint = () => {
    hint.textContent = fmt === 'mrpack'
      ? 'Моды, ресурспаки и шейдеры, которые есть на Modrinth, попадут в файл ссылками — модпак будет весить килобайты. Остальное кладётся внутрь. Открывается в Hvoya, Prism, Modrinth App.'
      : 'Всё кладётся внутрь архива: большой файл, зато ставится без интернета. Импортируется в Hvoya («Импорт → Модпак из файла»).';
  };
  const drawTotal = () => { total.textContent = 'Выбрано: ' + fmtSize(entries.filter(e => e.on).reduce((a, e) => a + e.size, 0)); };
  const m = modal({ title: `Экспорт «${inst.name}»`, cls: 'mid',
    body: h('div', { class: 'modal-b' },
      h('div', { class: 'field' }, h('label', null, 'Формат'),
        seg([['mrpack', 'Модпак .mrpack'], ['zip', 'Полный архив .zip']], fmt, v => { fmt = v; fmtHint(); })),
      hint,
      h('div', { class: 'row', style: { alignItems: 'flex-start' } },
        h('div', { class: 'field' }, h('label', null, 'Название'), name),
        h('div', { class: 'field', style: { flex: 'none' } }, h('label', null, 'Версия'), ver)),
      h('div', { class: 'field' }, h('label', null, 'Описание'), summary),
      h('div', { class: 'field', style: { marginBottom: 0 } }, h('label', null, 'Что включить'), list)),
    footer: [total, h('div', { class: 'spacer' }), h('button', { class: 'btn', onclick: () => m.close() }, 'Отмена'),
      h('button', { class: 'btn primary', onclick: async () => {
        const include = entries.filter(e => e.on).map(e => e.name);
        if (!include.length) { toast('Выберите, что включить', 'warn'); return; }
        const id = await safe(call('export_instance', inst.id, { format: fmt, name: name.value.trim(), version: ver.value.trim(), summary: summary.value.trim(), include }));
        if (!id) return;
        m.close();
        toast('Экспорт начат — прогресс внизу');
        const on = ev => {
          if (ev.id !== id || !ev.done) return;
          listeners.task.delete(on);
          if (ev.result && ev.result.path) {
            const r = ev.result;
            toast(`Готово: ${fmtSize(r.size)}` + (r.remote ? ` · ${r.remote} файлов ссылками на Modrinth` : ''));
            call('reveal_file', r.path);
          }
        };
        listeners.task.add(on);
      } }, icon('upload'), 'Экспортировать')] });
  fmtHint();
  try { entries = await call('export_entries', inst.id); } catch (e) { list.innerHTML = ''; list.append(h('div', { class: 'muted' }, e.message)); return; }
  list.innerHTML = '';
  if (!entries.length) list.append(h('div', { class: 'muted', style: { padding: '10px' } }, 'Сборка пустая'));
  entries.forEach(e => list.append(h('label', { class: 'exp-item' },
    h('input', { type: 'checkbox', checked: e.on, onchange: ev => { e.on = ev.target.checked; drawTotal(); } }),
    icon(e.dir ? 'folder' : 'file'),
    h('span', { class: 'en' }, e.name), e.label ? h('span', { class: 'muted' }, e.label) : null,
    h('span', { class: 'spacer' }), h('span', { class: 'muted' }, fmtSize(e.size)))));
  drawTotal();
  void m;
}

// ================================================================ crash analysis
const CRASH_ACTIONS = {
  ram: ['sliders', 'Настройки памяти', 'settings'], settings: ['sliders', 'Настройки сборки', 'settings'],
  mods: ['box', 'Открыть моды', 'mods'], version: ['layers', 'Версия и загрузчик', 'version'],
  repair: ['wrench', 'Проверить файлы', null],
};
function crashText(inst, a) {
  const lines = [`Вылет «${inst.name}» (Minecraft ${inst.mc} ${LOADER_NAMES[inst.loader]} ${inst.loaderVersion || ''})`.trim()];
  a.problems.forEach(p => { lines.push('', '• ' + p.title, '  ' + p.text); (p.mods || []).forEach(x => lines.push('    - ' + x)); });
  if (a.description) lines.push('', 'Краш-репорт: ' + a.description);
  if (a.cause) lines.push('Ошибка: ' + a.cause);
  return lines.join('\n');
}
function crashCard(inst, a, go, onclose) {
  const errs = a.problems.filter(p => p.level === 'error').length;
  const card = h('div', { class: 'crash' + (errs ? '' : ' ok') },
    h('div', { class: 'crash-h' }, icon(errs ? 'alert' : 'info'),
      h('b', null, errs ? 'Анализ вылета' : 'Анализ журнала'),
      a.description ? h('span', { class: 'muted' }, ' — ' + a.description) : null,
      h('div', { class: 'spacer' }),
      a.crashReport ? h('button', { class: 'btn sm', onclick: () => showReport(inst, a.crashReport) }, icon('file'), 'Краш-репорт') : null,
      h('button', { class: 'btn sm', onclick: () => { navigator.clipboard.writeText(crashText(inst, a)); toast('Отчёт скопирован'); } }, icon('copy'), 'Копировать'),
      onclose ? h('button', { class: 'xbtn', title: 'Скрыть', onclick: onclose }, icon('x')) : null),
    a.problems.map(p => h('div', { class: 'cp ' + p.level },
      h('div', { class: 'cpt' }, p.title),
      h('div', { class: 'cpx' }, p.text),
      p.mods && p.mods.length ? h('ul', null, p.mods.map(x => h('li', null, x))) : null,
      p.action && CRASH_ACTIONS[p.action] ? h('button', { class: 'btn sm', style: { marginTop: '6px' }, onclick: () => {
        const [, , tab] = CRASH_ACTIONS[p.action];
        if (tab) go(tab); else safe(call('repair', inst.id)).then(id => id && toast('Проверка файлов запущена'));
      } }, icon(CRASH_ACTIONS[p.action][0]), CRASH_ACTIONS[p.action][1]) : null)),
    a.cause ? h('div', { class: 'crash-cause' }, a.cause) : null);
  return card;
}
async function showReport(inst, name) {
  const pre = h('pre', { class: 'log', style: { maxHeight: '60vh' } }, 'Загрузка…');
  const m = modal({ title: name, cls: 'wide', body: h('div', { class: 'pane', style: { borderRadius: '0 0 12px 12px' } }, pre),
    footer: [h('button', { class: 'btn', onclick: () => { navigator.clipboard.writeText(pre.textContent); toast('Скопировано'); } }, icon('copy'), 'Копировать'),
      h('button', { class: 'btn', onclick: () => call('open_folder', 'instance', inst.id, 'crash-reports') }, icon('folder'), 'Папка'),
      h('button', { class: 'btn primary', onclick: () => m.close() }, 'Закрыть')] });
  pre.textContent = await call('crash_report', inst.id, name).catch(e => 'Ошибка: ' + e.message);
}

// ================================================================ discord (карточка в настройках)
function discordCard(s) {
  return h('div', { class: 'card' }, h('h4', null, icon('chat'), 'Discord'),
    h('label', { class: 'check', style: { display: 'flex' } },
      h('input', { type: 'checkbox', checked: s.discordRpc, onchange: e => { s.discordRpc = e.target.checked; } }),
      'Показывать в Discord, во что я играю (название сборки, версия, время в игре)'),
    h('div', { class: 'hint', style: { margin: '8px 0 0' } }, 'Работает, если на компьютере запущено приложение Discord.'));
}
