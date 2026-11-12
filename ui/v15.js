'use strict';
// 1.5: «Ускорить игру», обновление модпака, 3D-скины, предупреждения о памяти (хелперы из app.js).

// ================================================================ ускорить игру
async function openOptimize(inst) {
  const body = h('div', { class: 'modal-b' }, spinner('Подбираю моды под Minecraft ' + inst.mc + '…'));
  const go = h('button', { class: 'btn primary', disabled: true }, icon('zap'), 'Установить');
  const m = modal({ title: `Ускорить «${inst.name}»`, cls: 'mid', body,
    footer: [h('button', { class: 'btn', onclick: () => m.close() }, 'Отмена'), go] });
  let plan;
  try { plan = await call('optimize_plan', inst.id); } catch (e) { body.innerHTML = ''; body.append(h('div', { class: 'muted' }, e.message)); return; }
  body.innerHTML = '';
  if (plan.needLoader) {
    body.append(h('div', { class: 'opt-note' }, icon('info'),
      h('div', null, 'Моды оптимизации работают только с загрузчиком. Откройте «Редактировать» → «Версия» и выберите ',
        h('b', null, 'Fabric'), ' (лучший выбор для FPS) или Forge — потом вернитесь сюда.')),
      h('button', { class: 'btn', style: { marginTop: '10px' }, onclick: () => { m.close(); openInstance(inst.id, 'version'); } }, icon('layers'), 'Выбрать загрузчик'));
    return;
  }
  const sel = new Set();
  const STATUS = { installed: ['ok', 'Уже стоит'], conflict: ['bad', 'Конфликт'], unavailable: ['muted', 'Нет версии'] };
  const upd = () => { go.disabled = !sel.size; go.lastChild.textContent = sel.size ? `Установить (${sel.size})` : 'Установить'; };
  plan.items.forEach(it => {
    const can = it.status === 'install';
    if (can) sel.add(it);
    body.append(h('label', { class: 'opt-item' + (can ? '' : ' dim') },
      h('input', { type: 'checkbox', checked: can, disabled: !can, onchange: e => { e.target.checked ? sel.add(it) : sel.delete(it); upd(); } }),
      h('div', { class: 'cic', style: it.icon ? { backgroundImage: `url("${rimg(it.icon)}")` } : null }, it.icon ? null : icon('box')),
      h('div', { class: 'cmain' },
        h('div', { class: 'ct' }, it.label, it.title ? h('span', { class: 'muted' }, ' — ' + it.title + (it.version ? ' ' + it.version.number : '')) : null,
          it.core ? h('span', { class: 'opt-core' }, 'главное') : null),
        h('div', { class: 'cs' }, it.reason || it.desc)),
      STATUS[it.status] ? h('span', { class: 'opt-st ' + STATUS[it.status][0] }, STATUS[it.status][1]) : null));
  });
  body.append(h('div', { class: 'hint', style: { margin: '10px 0 0' } },
    'Всё ставится с Modrinth вместе с нужными зависимостями (например, Fabric API). Мир и настройки не меняются. ',
    'Шейдерпаки после этого кладите во вкладку «Шейдеры».'));
  upd();
  go.onclick = async () => {
    const items = [...sel].map(it => ({ project: it.project, version: it.version.id, title: it.title || it.label }));
    if (!await safe(call('optimize_install', inst.id, items))) return;
    m.close();
    toast('Ставлю моды оптимизации — прогресс внизу');
  };
}

// ================================================================ обновление модпака
async function openModpackUpdate(inst) {
  const mp = inst.modpack || {};
  const body = h('div', { class: 'modal-b' }, spinner('Проверяю версии модпака…'));
  const go = h('button', { class: 'btn primary', disabled: true }, icon('download'), 'Обновить');
  const m = modal({ title: `Модпак «${mp.name || inst.name}»`, cls: 'mid', body,
    footer: [h('button', { class: 'btn', onclick: () => m.close() }, 'Отмена'), go] });
  let r;
  try { r = await call('modpack_versions', inst.id); } catch (e) { body.innerHTML = ''; body.append(h('div', { class: 'muted' }, e.message)); return; }
  body.innerHTML = '';
  let chosen = r.versions.find(v => v.newer && v.sameMc && v.type === 'release') || r.versions.find(v => v.newer && v.sameMc) || null;
  let backup = true, allMc = false;
  body.append(h('div', { class: 'opt-note' + (r.hasUpdate ? ' good' : '') }, icon(r.hasUpdate ? 'download' : 'check'),
    h('div', null, `Установлена версия ${r.current || '?'}. `, r.hasUpdate ? 'Есть обновление!' : 'Это последняя версия — можно поставить другую из списка.')));
  const list = h('div', { class: 'mp-vers' });
  const draw = () => {
    list.innerHTML = '';
    const shown = r.versions.filter(v => allMc || v.sameMc || v.current);
    if (!shown.length) list.append(h('div', { class: 'muted', style: { padding: '10px 12px' } }, 'Нет версий для Minecraft ' + r.mc));
    shown.slice(0, 60).forEach(v => list.append(h('label', { class: 'mp-v' + (v.current ? ' cur' : '') },
      h('input', { type: 'radio', name: 'mpv', checked: chosen === v, disabled: v.current, onchange: () => { chosen = v; go.disabled = false; } }),
      h('b', null, v.number), v.type !== 'release' ? h('span', { class: 'opt-st muted' }, v.type) : null,
      h('span', { class: v.sameMc ? 'muted' : 'mp-other' }, (v.mc || []).join(', ')), h('div', { class: 'spacer' }),
      v.current ? h('span', { class: 'opt-st ok' }, 'установлена') : h('span', { class: 'muted' }, v.date ? fmtDate(Date.parse(v.date) / 1000) : ''))));
  };
  draw();
  go.disabled = !chosen;
  body.append(list,
    h('label', { class: 'check', style: { display: 'flex', marginTop: '10px', fontSize: '12px' } },
      h('input', { type: 'checkbox', onchange: e => { allMc = e.target.checked; draw(); } }),
      `Показать версии для других версий Minecraft (сейчас ${r.mc}; при смене версии миры могут сломаться — сделайте бэкап)`),
    h('label', { class: 'check', style: { display: 'flex', marginTop: '8px' } },
      h('input', { type: 'checkbox', checked: true, onchange: e => { backup = e.target.checked; } }), 'Сначала сделать бэкап всех миров'),
    h('div', { class: 'hint', style: { margin: '8px 0 0' } },
      'Моды модпака заменятся на новые. Миры, options.txt, список серверов и отключённые вами моды сохранятся; ',
      'моды, добавленные вами вручную, не удаляются.'));
  go.onclick = async () => {
    if (!chosen) return;
    if (S.running.has(inst.id)) { toast('Сначала закройте игру', 'warn'); return; }
    const id = await safe(call('update_modpack', inst.id, chosen.id, backup));
    if (!id) return;
    m.close();
    toast('Обновление модпака началось — прогресс внизу');
    const on = ev => {
      if (ev.id !== id || !ev.done) return;
      listeners.task.delete(on);
      refreshInstances();
      if (ev.result) toast(`Модпак обновлён до ${ev.result.version}` + (ev.result.warning ? '. ' + ev.result.warning : ''), ev.result.warning ? 'warn' : '');
    };
    listeners.task.add(on);
  };
}

// ================================================================ скины
function skinViewer(w, hgt) {
  const canvas = h('canvas');
  let viewer = null;
  try {
    viewer = new skinview3d.SkinViewer({ canvas, width: w, height: hgt, zoom: 0.85 });
    viewer.autoRotate = true;
    viewer.autoRotateSpeed = 0.6;
    viewer.animation = new skinview3d.WalkingAnimation();
    viewer.animation.speed = 0.6;
    viewer.controls.enableZoom = false;
  } catch (e) { console.warn('skinview3d', e); }
  return {
    el: h('div', { class: 'skin-3d' }, canvas),
    set(url, slim) {
      if (!viewer) return;
      if (url) viewer.loadSkin(url, { model: slim ? 'slim' : 'default' }); else viewer.loadSkin(null);
    },
    dispose() { if (viewer) viewer.dispose(); },
  };
}

async function openSkin(acc) {
  const v = skinViewer(260, 340);
  const info = h('div', { class: 'skin-side' });
  const m = modal({ title: `Скин ${acc.name}`, cls: 'mid', body: h('div', { class: 'modal-b skin-wrap' }, v.el, info),
    onclose: () => v.dispose(), footer: [h('button', { class: 'btn primary', onclick: () => m.close() }, 'Готово')] });
  let st = { skin: null, slim: false };
  const applyHeads = async () => {
    S.accounts = await call('accounts');
    renderAccountBtn(); renderSide();
  };
  const draw = async () => {
    v.set(st.skin || pixSteve(), st.slim);
    info.innerHTML = '';
    if (acc.type === 'elyby') {
      info.append(h('div', { class: 'muted' }, st.skin ? 'Скин с Ely.by. Его видно в игре и на серверах с авторизацией Ely.by.' : 'У аккаунта на Ely.by нет скина — показан стандартный.'),
        h('button', { class: 'btn', style: { marginTop: '12px' }, onclick: () => call('open_url', 'https://ely.by/skins') }, icon('ext'), 'Сменить скин на ely.by'),
        h('button', { class: 'btn', style: { marginTop: '8px' }, onclick: async () => { st = await call('skin', acc.id).catch(() => st); draw(); } }, icon('refresh'), 'Обновить'));
      return;
    }
    info.append(
      h('button', { class: 'btn primary', onclick: async () => {
        const r = await safe(call('skin_pick', acc.id, st.slim)); if (r) { st = r; draw(); applyHeads(); toast('Скин сохранён'); }
      } }, icon('upload'), st.custom ? 'Выбрать другой файл' : 'Выбрать файл скина'),
      h('div', { class: 'field', style: { marginTop: '12px' } }, h('label', null, 'Модель рук'),
        seg([['classic', 'Обычные (Стив)'], ['slim', 'Тонкие (Алекс)']], st.slim ? 'slim' : 'classic', async val => {
          const r = await safe(call('skin_model', acc.id, val === 'slim')); if (r) { st = r; draw(); }
        })),
      st.custom ? h('button', { class: 'btn danger', onclick: async () => {
        if (await safe(call('skin_remove', acc.id))) { st = { skin: null, slim: false }; draw(); applyHeads(); }
      } }, icon('trash'), 'Убрать скин') : null,
      h('div', { class: 'hint', style: { margin: '14px 0 8px' } },
        'PNG 64×64 — например, скачанный с namemc.com или minecraftskins.com. ',
        'В офлайн-режиме игра сама скины не грузит, поэтому нужен мод ', h('b', null, 'CustomSkinLoader'),
        ' — лаунчер положит ему скин при запуске. Другие игроки на сервере увидят его, только если у них тоже стоит этот мод.'),
      cslBlock());
  };
  const cslBlock = () => {
    const box = h('div', { class: 'csl' }, spinner('Проверяю сборки…'));
    call('csl_status').then(list => {
      box.innerHTML = '';
      if (!list.length) { box.append(h('div', { class: 'muted' }, 'Нет сборок с Fabric/Forge — мод можно поставить только в них.')); return; }
      list.forEach(i => box.append(h('div', { class: 'csl-i' }, h('span', null, i.name), h('div', { class: 'spacer' }),
        i.has ? h('span', { class: 'opt-st ok' }, 'мод есть') : h('button', { class: 'btn sm', onclick: async e => {
          e.currentTarget.disabled = true;
          if (await safe(call('csl_install', i.id))) toast(`Ставлю CustomSkinLoader в «${i.name}»`);
        } }, icon('download'), 'Установить'))));
    }).catch(e => { box.innerHTML = ''; box.append(h('div', { class: 'muted' }, e.message)); });
    return box;
  };
  v.set(pixSteve(), false);
  info.append(spinner('Загрузка скина…'));
  st = await call('skin', acc.id).catch(() => st);
  draw();
  void m;
}

// стандартный скин (если своего нет): рисуем простого «Стива» в canvas 64×64
let _steve = null;
function pixSteve() {
  if (_steve) return _steve;
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d');
  const r = (x, y, w, hh, col) => { g.fillStyle = col; g.fillRect(x, y, w, hh); };
  r(0, 0, 32, 16, '#b4846c'); r(8, 0, 16, 8, '#4a2f1d'); r(0, 8, 32, 3, '#4a2f1d');  // голова и волосы
  r(8, 8, 8, 8, '#b4846c'); r(8, 8, 8, 2, '#4a2f1d'); r(9, 12, 2, 1, '#fff'); r(10, 12, 1, 1, '#4b3b8f');
  r(13, 12, 2, 1, '#fff'); r(13, 12, 1, 1, '#4b3b8f'); r(11, 14, 2, 1, '#6b4232');
  r(16, 16, 24, 16, '#2fa8b5');            // торс
  r(40, 16, 16, 16, '#2fa8b5'); r(44, 28, 8, 4, '#b4846c'); r(40, 20, 16, 12, '#b4846c'); r(40, 16, 16, 4, '#2fa8b5');  // рука
  r(0, 16, 16, 16, '#3c3fa0'); r(0, 28, 16, 4, '#555');  // нога
  r(16, 48, 16, 16, '#3c3fa0'); r(32, 48, 16, 16, '#b4846c'); r(32, 48, 16, 4, '#2fa8b5');  // левые нога и рука
  _steve = c.toDataURL();
  return _steve;
}

// ================================================================ память
async function memoryGate(id) {
  if (S.settings.ramWarnings === false) return true;
  let r;
  try { r = await call('memory_check', id); } catch { return true; }
  const bad = r.issues.filter(i => i.level === 'bad');
  r.issues.filter(i => i.level !== 'bad').forEach(i => toast(i.text, 'warn'));
  if (!bad.length) return true;
  const inst = S.instances.find(i => i.id === id);
  return new Promise(resolve => {
    let done = false;
    const fin = v => { if (!done) { done = true; resolve(v); } };
    const fix = Math.max(512, Math.min(r.recommended, r.limit));
    const m = modal({ title: 'Проверьте память', cls: 'mid', onclose: () => fin(false),
      body: h('div', { class: 'modal-b' }, bad.map(i => h('div', { class: 'opt-note warn' }, icon('alert'), h('div', null, i.text))),
        h('div', { class: 'muted', style: { marginTop: '10px' } },
          `Сейчас: ${memGb(r.ram)} · модов: ${r.mods} · в компьютере ${memGb(r.total)}, свободно ${memGb(r.avail)}.`)),
      footer: [
        h('label', { class: 'check', style: { fontSize: '12px' } }, h('input', { type: 'checkbox', onchange: e => {
          S.settings.ramWarnings = !e.target.checked; call('save_settings', { ramWarnings: !e.target.checked });
        } }), 'Больше не предупреждать'),
        h('div', { class: 'spacer' }),
        h('button', { class: 'btn', onclick: () => { fin(true); m.close(); } }, 'Запустить так'),
        h('button', { class: 'btn primary', onclick: async () => {
          const ok = await safe(call('update_instance', id, { ramMax: fix }));
          if (ok) { await refreshInstances(); toast(`Для «${inst ? inst.name : ''}» выставлено ${memGb(fix)}`); }
          fin(!!ok); m.close();
        } }, icon('check'), `Поставить ${memGb(fix)} и запустить`)] });
  });
}
function memGb(mb) { return (mb / 1024).toFixed(1).replace('.0', '') + ' ГБ'; }
// подсказка под ползунком памяти
function memHint(v) {
  const limit = Math.max(1024, S.ram - (S.ram > 8192 ? 3072 : 2048));
  if (v > limit) return ['bad', `Слишком много: Windows останется меньше ${memGb(S.ram - v)}. Лучше не больше ${memGb(limit)}.`];
  if (v < 2048) return ['warn', 'Мало даже для чистой игры — ставьте от 2 ГБ.'];
  return ['', 'Примерно: без модов 2 ГБ, до 50 модов 3 ГБ, до 120 — 4 ГБ, больше — 6–8 ГБ. Много памяти не ускоряет игру.'];
}
