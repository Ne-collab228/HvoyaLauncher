'use strict';
// 1.6: время в игре (живой счётчик, статистика по дням), обновления модов/ресурспаков/шейдеров, сортировка сборок.

// ================================================================ время в игре
S.live = {};      // inst_id -> unix-время последнего сохранения playtime на диск
S.updates = {};   // inst_id -> список обновлений | 'pending'

const _origEvent = window.hvEvent;
window.hvEvent = ev => {
  if (ev.type === 'playtime') {
    const inst = S.instances.find(i => i.id === ev.inst);
    if (inst) inst.playtime = ev.playtime;
    S.live[ev.inst] = ev.last;
    tickLive();
    return;
  }
  if (ev.type === 'game') {
    if (ev.state === 'running') S.live[ev.inst] = Date.now() / 1000;
    else delete S.live[ev.inst];
  }
  _origEvent(ev);
};

/** Наигранное время с учётом идущей сейчас игры. */
function livePlaytime(inst) {
  const last = S.live[inst.id];
  const extra = last && S.running.has(inst.id) ? Math.max(0, Date.now() / 1000 - last) : 0;
  return (inst.playtime || 0) + extra;
}
function totalPlaytime() { return S.instances.reduce((a, i) => a + livePlaytime(i), 0); }

function playtimeRows(inst) {
  const rows = [h('div', { class: 'pt-link', title: 'Статистика', onclick: () => openPlaytime(inst.id) },
    'В игре', h('b', { 'data-live': inst.id }, fmtTime(livePlaytime(inst))))];
  if (S.running.has(inst.id) && S.live[inst.id]) {
    rows.push(h('div', null, 'Эта сессия', h('b', { 'data-sess': inst.id }, '…')));
  }
  return rows;
}

let _sessStart = {};
async function syncLive() {
  const r = await call('live_sessions').catch(() => null);
  if (!r) return;
  for (const [id, s] of Object.entries(r)) { S.live[id] = s.last; _sessStart[id] = s.started; }
  tickLive();
}
listeners.game.add(ev => {
  if (ev.state === 'running') _sessStart[ev.inst] = Date.now() / 1000;
  else delete _sessStart[ev.inst];
});

function tickLive() {
  document.querySelectorAll('[data-live]').forEach(el => {
    const inst = S.instances.find(i => i.id === el.dataset.live);
    if (inst) el.textContent = fmtTime(livePlaytime(inst));
  });
  document.querySelectorAll('[data-sess]').forEach(el => {
    const st = _sessStart[el.dataset.sess];
    el.textContent = st ? fmtTime(Math.max(1, Math.round(Date.now() / 1000 - st))) : '—';
  });
  const tt = $('#totalTime');
  if (tt) tt.textContent = fmtTime(totalPlaytime());
}
setInterval(() => { if (S.running.size) tickLive(); }, 5000);

const DAY = 86400;
function dayKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

async function openPlaytime(focusId) {
  const stats = await safe(call('playtime_stats'));
  if (!stats) return;
  let filter = focusId || '';
  let range = 30;
  const body = h('div', { class: 'modal-b pt' });
  const m = modal({ title: 'Время в игре', cls: 'mid', body });

  const draw = () => {
    body.innerHTML = '';
    const days = stats.days || {};
    const secsOn = key => {
      const d = days[key] || {};
      return filter ? (d[filter] || 0) : Object.values(d).reduce((a, b) => a + b, 0);
    };
    const today = new Date();
    const keys = [];
    for (let i = range - 1; i >= 0; i--) keys.push(dayKey(new Date(today.getFullYear(), today.getMonth(), today.getDate() - i)));
    const sumLast = n => keys.slice(-n).reduce((a, k) => a + secsOn(k), 0);
    // если в выбранном диапазоне меньше 7 дней — для «за неделю/месяц» считаем отдельно
    const sumDays = n => {
      let s = 0;
      for (let i = 0; i < n; i++) s += secsOn(dayKey(new Date(today.getFullYear(), today.getMonth(), today.getDate() - i)));
      return s;
    };
    const liveNow = filter ? (S.running.has(filter) && S.live[filter] ? Date.now() / 1000 - S.live[filter] : 0)
      : [...S.running].reduce((a, id) => a + (S.live[id] ? Date.now() / 1000 - S.live[id] : 0), 0);
    const inst = filter && S.instances.find(i => i.id === filter);
    const total = inst ? livePlaytime(inst) : totalPlaytime();
    const sessions = inst ? (inst.sessions || 0) : S.instances.reduce((a, i) => a + (i.sessions || 0), 0);
    const playedDays = Object.keys(days).filter(k => secsOn(k) > 0).length;

    const sel = h('select', { class: 'input', onchange: e => { filter = e.target.value; draw(); } },
      h('option', { value: '' }, 'Все сборки'),
      [...S.instances].sort((a, b) => (b.playtime || 0) - (a.playtime || 0))
        .map(i => h('option', { value: i.id, selected: i.id === filter }, i.name)));
    body.append(h('div', { class: 'pt-bar' }, sel,
      seg([[7, '7 дней'], [30, '30 дней'], [90, '90 дней']], range, v => { range = v; draw(); })));

    const tilesEl = h('div', { class: 'pt-tiles' },
      ptTile('Всего', fmtTime(total)),
      ptTile('Сегодня', fmtTime(sumDays(1) + liveNow)),
      ptTile('За 7 дней', fmtTime(sumDays(7) + liveNow)),
      ptTile('За 30 дней', fmtTime(sumDays(30) + liveNow)),
      ptTile('Запусков', sessions ? String(sessions) : '—'),
      ptTile('В среднем за игровой день', playedDays ? fmtTime(Math.round(Object.keys(days).reduce((a, k) => a + secsOn(k), 0) / playedDays)) : '—'));
    body.append(tilesEl);

    // ---- столбики по дням
    const vals = keys.map((k, i) => secsOn(k) + (i === keys.length - 1 ? liveNow : 0));
    const max = Math.max(...vals, 60);
    const chart = h('div', { class: 'pt-chart' + (range > 30 ? ' dense' : '') });
    const tip = h('div', { class: 'pt-tip' });
    const ticks = niceTicks(max);
    const grid = h('div', { class: 'pt-grid' }, ticks.map(t => h('div', { style: { bottom: (t / ticks[ticks.length - 1] * 100) + '%' } },
      h('span', null, t ? fmtHours(t) : '0'))));
    const top = ticks[ticks.length - 1];
    const bars = h('div', { class: 'pt-bars' }, keys.map((k, i) => {
      const d = new Date(k + 'T00:00:00');
      const v = vals[i];
      const col = h('div', { class: 'pt-col', onmouseenter: () => {
        const per = days[k] && !filter ? Object.entries(days[k]).filter(([, s]) => s >= 60).sort((a, b) => b[1] - a[1]).slice(0, 4) : [];
        tip.innerHTML = '';
        tip.append(h('b', null, d.toLocaleDateString('ru', { weekday: 'short', day: 'numeric', month: 'long' })),
          h('div', null, v ? fmtTime(Math.round(v)) : 'не играли'),
          ...per.map(([id, s]) => h('div', { class: 'muted' }, `${(S.instances.find(x => x.id === id) || { name: 'удалённая сборка' }).name}: ${fmtTime(s)}`)));
        tip.style.display = 'block';
        const r = col.getBoundingClientRect(), cr = chart.getBoundingClientRect();
        tip.style.left = Math.min(Math.max(0, r.left - cr.left + r.width / 2 - 90), cr.width - 180) + 'px';
      }, onmouseleave: () => { tip.style.display = 'none'; } },
      h('div', { class: 'pt-fill' + (v ? '' : ' zero'), style: { height: v ? Math.max(2, v / top * 100) + '%' : '0' } }));
      return col;
    }));
    const labels = h('div', { class: 'pt-labels' }, keys.map((k, i) => {
      const d = new Date(k + 'T00:00:00');
      const step = range <= 7 ? 1 : range <= 30 ? 5 : 15;
      const show = (keys.length - 1 - i) % step === 0;
      return h('span', null, show ? (range <= 7 ? d.toLocaleDateString('ru', { weekday: 'short' }) : `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}`) : '');
    }));
    chart.append(grid, bars, tip);
    const anyDays = vals.some(v => v > 0);
    body.append(h('div', { class: 'card pt-card' },
      h('h4', null, icon('clock'), filter ? `По дням — ${inst ? inst.name : ''}` : 'По дням'),
      chart, labels,
      anyDays ? null : h('div', { class: 'hint' }, 'Время по дням считается с версии 2.0 — сыграйте, и здесь появятся столбики.')));

    // ---- по сборкам
    if (!filter) {
      const list = [...S.instances].map(i => ({ i, t: livePlaytime(i) })).filter(x => x.t > 0).sort((a, b) => b.t - a.t);
      const sum = list.reduce((a, x) => a + x.t, 0) || 1;
      body.append(h('div', { class: 'card pt-card' }, h('h4', null, icon('layers'), 'По сборкам'),
        list.length ? list.map(({ i, t }) => h('div', { class: 'pt-row', onclick: () => { filter = i.id; draw(); }, title: 'Показать по дням' },
          h('div', { class: 'pt-ico', style: { backgroundImage: `url(${instIconUrl(i)})` } }),
          h('div', { class: 'pt-main' },
            h('div', { class: 'pt-name' }, h('span', null, i.name), h('b', null, fmtTime(Math.round(t)))),
            h('div', { class: 'pt-track' }, h('div', { style: { width: Math.max(1, t / list[0].t * 100) + '%' } })),
            h('div', { class: 'pt-sub' }, [`${Math.round(t / sum * 100)}%`, i.sessions ? `запусков: ${i.sessions}` : '', i.lastPlayed ? `последний: ${fmtDate(i.lastPlayed)}` : ''].filter(Boolean).join(' · ')))))
          : h('div', { class: 'muted' }, 'Ещё ни одна сборка не запускалась.')));
    } else {
      body.append(h('button', { class: 'btn sm', onclick: () => { filter = ''; draw(); } }, icon('layers'), 'Все сборки'));
    }
  };
  draw();
  void m;
}
function ptTile(label, value) { return h('div', { class: 'pt-tile' }, h('div', { class: 'pt-v' }, value), h('div', { class: 'pt-l' }, label)); }
function fmtHours(s) { return s >= 3600 ? `${+(s / 3600).toFixed(1)} ч` : `${Math.round(s / 60)} мин`; }
function niceTicks(max) {
  const steps = [600, 900, 1800, 3600, 7200, 10800, 14400, 21600];
  const step = steps.find(s => max / s <= 4) || 21600;
  const out = [];
  for (let v = 0; v <= max + step - 1; v += step) out.push(v);
  if (out.length < 2) out.push(step);
  return out;
}

// ================================================================ обновления контента
const KIND_NAMES = { mods: 'Моды', resourcepacks: 'Ресурспаки', shaderpacks: 'Шейдеры' };

/** Фоновая проверка (кэш на стороне Python 6 часов, пока не менялись файлы). */
async function loadUpdates(instId, force) {
  if (!force && S.updates[instId] !== undefined) return S.updates[instId];
  S.updates[instId] = 'pending';
  const r = await call('check_updates', instId, null, !force).catch(() => null);
  S.updates[instId] = r || [];
  if (S.selected === instId) renderSide();
  listeners.instances.forEach(fn => fn());
  return S.updates[instId];
}
function updatesOf(instId, kind) {
  const u = S.updates[instId];
  if (!Array.isArray(u)) return [];
  return kind ? u.filter(x => x.kind === kind) : u;
}
function sideUpdates(inst) {
  const u = S.updates[inst.id];
  if (u === undefined && !taskFor(inst.id)) setTimeout(() => loadUpdates(inst.id), 400);
  if (!Array.isArray(u) || !u.length) return null;
  return h('button', { class: 'sa upd', onclick: () => openUpdates(inst, null) }, icon('refresh'), 'Обновления',
    h('span', { class: 'sa-count' }, u.length));
}
function sideBadge(inst, kind) {
  const n = updatesOf(inst.id, kind).length;
  return n ? h('span', { class: 'sa-count', title: `Обновлений: ${n}` }, n) : null;
}

/** Окно выбора обновлений. kind = null — всё сразу. */
async function openUpdates(inst, kind, btn) {
  if (btn) btn.disabled = true;
  const kinds = kind ? [kind] : null;
  let ups = await safe(call('check_updates', inst.id, kinds, false));
  if (btn) btn.disabled = false;
  if (!ups) return;
  if (!kind) S.updates[inst.id] = ups;
  else S.updates[inst.id] = [...updatesOf(inst.id).filter(x => x.kind !== kind), ...ups];
  if (S.selected === inst.id) renderSide();
  if (!ups.length) {
    toast(kind ? `${KIND_NAMES[kind]}: всё актуально` : 'Всё актуально');
    return;
  }
  const sel = new Set(ups.map((_, i) => i));
  const btnOk = h('button', { class: 'btn primary' }, icon('download'), h('span'));
  const all = h('input', { type: 'checkbox', checked: true });
  const boxes = [];
  const sync = () => {
    btnOk.lastChild.textContent = `Обновить (${sel.size})`;
    btnOk.disabled = !sel.size;
    all.checked = sel.size === ups.length;
    all.indeterminate = sel.size > 0 && sel.size < ups.length;
  };
  all.onchange = () => {
    ups.forEach((_, i) => all.checked ? sel.add(i) : sel.delete(i));
    boxes.forEach(b => { b.checked = all.checked; });
    sync();
  };
  const rows = [];
  let lastKind = null;
  ups.forEach((u, i) => {
    if (!kind && u.kind !== lastKind) { rows.push(h('div', { class: 'upd-h' }, KIND_NAMES[u.kind])); lastKind = u.kind; }
    const cb = h('input', { type: 'checkbox', checked: true, onchange: e => { e.target.checked ? sel.add(i) : sel.delete(i); sync(); } });
    boxes.push(cb);
    rows.push(h('label', { class: 'upd-row' }, cb,
      h('div', { class: 'cic', style: u.icon ? { backgroundImage: `url("${u.icon}")` } : null }, u.icon ? null : icon('box')),
      h('div', { class: 'cmain' }, h('div', { class: 'ct' }, u.title),
        h('div', { class: 'cs' }, u.oldVersion && u.oldVersion !== u.versionName ? h('span', null, u.oldVersion, ' → ') : null,
          h('b', null, u.versionName), u.oldVersion === u.versionName ? h('span', { class: 'muted' }, ` · ${u.newFile}`) : null)),
      h('span', { class: 'src ' + u.source }, SRC_NAMES[u.source])));
  });
  const m = modal({ title: `Доступно обновлений: ${ups.length}`, cls: 'mid',
    body: h('div', { class: 'modal-b upd-list' },
      h('label', { class: 'check upd-all' }, all, 'Выбрать все'),
      rows,
      S.running.has(inst.id) ? h('div', { class: 'hint warn' }, 'Сборка запущена — изменения подхватятся после перезапуска игры.') : null),
    footer: [h('button', { class: 'btn', onclick: () => m.close() }, 'Отмена'), btnOk] });
  btnOk.onclick = async () => {
    const chosen = ups.filter((_, i) => sel.has(i));
    m.close();
    if (await safe(call('apply_updates', inst.id, chosen))) {
      const done = new Set(chosen.map(u => u.kind + '/' + u.file));
      S.updates[inst.id] = updatesOf(inst.id).filter(u => !done.has(u.kind + '/' + u.file));
      if (S.selected === inst.id) renderSide();
    }
  };
  sync();
}

// после обновления/установки контента — проверить заново (файлы изменились)
listeners.task.add(ev => {
  if (ev.done && ev.inst && S.updates[ev.inst] !== undefined && S.updates[ev.inst] !== 'pending') {
    delete S.updates[ev.inst];
    if (S.selected === ev.inst) setTimeout(() => loadUpdates(ev.inst), 500);
  }
});

// ================================================================ сортировка сборок
const SORTS = [['name', 'По названию'], ['recent', 'Недавние'], ['playtime', 'Больше всего играл'], ['created', 'Новые']];
function sortInstances(list) {
  const mode = S.settings.instSort || 'name';
  const by = {
    name: (a, b) => a.name.localeCompare(b.name, 'ru'),
    recent: (a, b) => (b.lastPlayed || 0) - (a.lastPlayed || 0) || a.name.localeCompare(b.name, 'ru'),
    playtime: (a, b) => livePlaytime(b) - livePlaytime(a) || a.name.localeCompare(b.name, 'ru'),
    created: (a, b) => (b.created || 0) - (a.created || 0),
  }[mode] || (() => 0);
  return [...list].sort(by);
}
function bindSort() {
  const btn = $('#sortBtn');
  if (!btn) return;
  const label = () => { btn.querySelector('span').textContent = (SORTS.find(s => s[0] === (S.settings.instSort || 'name')) || SORTS[0])[1]; };
  label();
  btn.onclick = e => {
    const r = e.currentTarget.getBoundingClientRect();
    menu(r.left, r.bottom + 4, [{ header: 'Сортировка' }, ...SORTS.map(([k, t]) => ({
      label: t, icon: (S.settings.instSort || 'name') === k ? 'check' : null,
      act: async () => {
        S.settings.instSort = k; label(); renderInstances();
        const res = await call('save_settings', { instSort: k }).catch(() => null);
        if (res) S.settings = res;
      } }))]);
  };
}
