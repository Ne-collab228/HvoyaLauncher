'use strict';
// Оформление: темы, акцентный цвет, вид списка сборок, фон.

const THEMES = [
  { id: 'hvoya', name: 'Хвоя', accent: '#4caf6a', desc: 'Тёмная, по умолчанию' },
  { id: 'midnight', name: 'Полночь', accent: '#5b8cff', desc: 'Глубокий синий' },
  { id: 'amethyst', name: 'Аметист', accent: '#a77be0', desc: 'Фиолетовая' },
  { id: 'sunset', name: 'Закат', accent: '#ff8a4c', desc: 'Тёплая, оранжевая' },
  { id: 'ocean', name: 'Океан', accent: '#2ec4b6', desc: 'Бирюзовая' },
  { id: 'nether', name: 'Незер', accent: '#e5483b', desc: 'Чёрно-красная' },
  { id: 'end', name: 'Край', accent: '#e8e07a', desc: 'Тёмная с жёлтым' },
  { id: 'graphite', name: 'Графит', accent: '#d9d9d9', desc: 'Строгая серая' },
  { id: 'contrast', name: 'Контраст', accent: '#ffd400', desc: 'Максимальная читаемость' },
  { id: 'light', name: 'Светлая', accent: '#2f9a52', desc: 'Для дня', light: true },
  { id: 'sakura', name: 'Сакура', accent: '#e0457b', desc: 'Светлая розовая', light: true },
  { id: 'desert', name: 'Пустыня', accent: '#c47a2c', desc: 'Светлая песочная', light: true },
  // особые — меняют весь интерфейс
  { id: 'pixel', name: 'Пиксель', accent: '#5fbf4a', special: true, desc: 'Блочные кнопки, слоты, пиксельный шрифт, земля и камень' },
  { id: 'terminal', name: 'Терминал', accent: '#39ff6a', special: true, desc: 'Зелёный текст на чёрном, моноширинный шрифт, развёртка ЭЛТ' },
  { id: 'retro', name: 'Ретро 98', accent: '#000080', special: true, light: true, desc: 'Объёмные серые окна и синие заголовки из 90-х' },
  { id: 'glass', name: 'Стекло', accent: '#7cc6ff', special: true, desc: 'Парящие полупрозрачные панели на ярком фоне', bg: 'aurora' },
  { id: 'neon', name: 'Неон', accent: '#ff2bd6', special: true, desc: 'Светящиеся рамки и кнопки на чёрном' },
  { id: 'paper', name: 'Блокнот', accent: '#2f6fd6', special: true, light: true, desc: 'Тетрадный лист, рукописный шрифт, сборки-стикеры' },
];
const ACCENTS = ['#4caf6a', '#2ec4b6', '#3d9df0', '#5b8cff', '#8f6bff', '#c05cf0', '#e0457b', '#e5483b', '#ff8a4c', '#f0b429', '#a3c43a', '#d9d9d9'];

// ---------------------------------------------------------------- цвет
function hexRgb(hex) {
  let h = hex.replace('#', '');
  if (h.length === 3) h = [...h].map(c => c + c).join('');
  const n = parseInt(h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
const rgbHex = c => '#' + c.map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('');
const mix = (a, b, t) => a.map((v, i) => v + (b[i] - v) * t);
function accentVars(hex) {
  const c = hexRgb(hex);
  const lum = (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255;
  return {
    '--accent': hex, '--accent-h': rgbHex(mix(c, [255, 255, 255], 0.16)), '--accent-d': rgbHex(mix(c, [0, 0, 0], 0.38)),
    '--accent-rgb': c.join(','), '--on-accent': lum > 0.5 ? '#111' : '#fff',
  };
}

// ---------------------------------------------------------------- генераторы картинок
function rng(seed) {
  let s = seed >>> 0;
  return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
}
function noiseTex(base, spread, seed, extra) {
  const c = document.createElement('canvas');
  c.width = c.height = 16;
  const g = c.getContext('2d');
  const r = rng(seed);
  const b = hexRgb(base);
  for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
    const k = (r() - 0.5) * spread;
    g.fillStyle = rgbHex(b.map(v => v + k));
    g.fillRect(x, y, 1, 1);
  }
  if (extra) extra(g, r);
  return c.toDataURL();
}
let _tex = null;
function textures() {
  if (_tex) return _tex;
  _tex = {
    dirt: noiseTex('#79553a', 46, 7, (g, r) => { for (let i = 0; i < 10; i++) { g.fillStyle = r() > 0.5 ? '#5c3f2a' : '#9b7350'; g.fillRect(r() * 16 | 0, r() * 16 | 0, 1, 1); } }),
    stone: noiseTex('#7d7d7d', 36, 11, (g, r) => { for (let i = 0; i < 7; i++) { g.fillStyle = '#5f5f5f'; g.fillRect(r() * 15 | 0, r() * 16 | 0, 2, 1); } }),
  };
  return _tex;
}

/** Процедурный пиксельный пейзаж (своё, не из игры). */
function pixelScene(o) {
  const W = 320, H = 180, c = document.createElement('canvas');
  c.width = W; c.height = H;
  const g = c.getContext('2d');
  const r = rng(o.seed || 1);
  const top = hexRgb(o.sky[0]), bot = hexRgb(o.sky[1]);
  for (let y = 0; y < H; y += 6) { g.fillStyle = rgbHex(mix(top, bot, y / H)); g.fillRect(0, y, W, 6); }
  if (o.stars) for (let i = 0; i < 90; i++) { g.fillStyle = r() > 0.8 ? '#fff' : '#9fb0d8'; g.fillRect(r() * W | 0, r() * H * 0.6 | 0, 1, 1); }
  if (o.sun) {
    const [sx, sy, sr, col] = o.sun;
    g.fillStyle = col;
    for (let y = -sr; y <= sr; y += 2) for (let x = -sr; x <= sr; x += 2) if (x * x + y * y <= sr * sr) g.fillRect(sx + x, sy + y, 2, 2);
    if (o.moon) { g.fillStyle = o.sky[0]; for (let y = -sr; y <= sr; y += 2) for (let x = -sr; x <= sr; x += 2) if ((x - 5) ** 2 + (y + 2) ** 2 <= sr * sr * 0.8) g.fillRect(sx + x, sy + y, 2, 2); }
  }
  if (o.clouds) for (let i = 0; i < 6; i++) {
    const cx = r() * W | 0, cy = 12 + r() * 50 | 0, w = 18 + r() * 30 | 0;
    g.fillStyle = o.clouds;
    g.fillRect(cx, cy, w, 6); g.fillRect(cx + 6, cy - 4, w - 12, 4);
  }
  o.hills.forEach((hl, li) => {
    const rr = rng((o.seed || 1) * 31 + li);
    const ph = rr() * 10, ph2 = rr() * 10;
    const tops = [];
    for (let x = 0; x < W; x += 4) {
      const y = Math.round((hl.base + Math.sin(x / hl.f + ph) * hl.amp + Math.sin(x / (hl.f * 0.43) + ph2) * hl.amp * 0.35) / 4) * 4;
      tops.push(y);
      g.fillStyle = hl.fill; g.fillRect(x, y, 4, H - y);
      if (hl.dots) for (let yy = y + 8; yy < H; yy += 4) if (rr() < 0.12) { g.fillStyle = hl.dots; g.fillRect(x + (rr() * 3 | 0), yy, 1, 1); }
      g.fillStyle = hl.top; g.fillRect(x, y, 4, hl.topH || 4);
    }
    if (hl.trees) for (let i = 0; i < hl.trees; i++) {
      const xi = rr() * tops.length | 0, x = xi * 4, y = tops[xi];
      const hgt = 14 + (rr() * 10 | 0);
      g.fillStyle = hl.trunk || '#5d3a1e'; g.fillRect(x + 1, y - 6, 2, 6);
      g.fillStyle = hl.leaf;
      for (let k = 0; k < hgt; k += 2) { const w = Math.max(2, Math.round((k / hgt) * 10)); g.fillRect(x + 2 - w / 2, y - 6 - hgt + k, w, 2); }
      if (hl.snowCap) { g.fillStyle = '#f4f8fb'; g.fillRect(x + 1, y - 6 - hgt, 2, 2); g.fillRect(x - 1, y - 6 - hgt + 6, 6, 1); }
    }
  });
  return c.toDataURL();
}

const BG_PRESETS = [
  { id: 'hills', name: 'Холмы', pix: true, gen: () => pixelScene({ seed: 3, sky: ['#7ec3ff', '#d6f0ff'], sun: [250, 34, 12, '#fff6b0'], clouds: '#ffffff',
    hills: [{ base: 96, amp: 14, f: 34, fill: '#7fa8c9', top: '#94bcd9' },
      { base: 118, amp: 12, f: 26, fill: '#5d8a3a', top: '#6fae45', trees: 7, leaf: '#3c7a2e' },
      { base: 142, amp: 8, f: 20, fill: '#8a5a32', top: '#62b03c', topH: 6, dots: '#6e4526', trees: 4, leaf: '#2f8a4c' }] }) },
  { id: 'night', name: 'Ночь', pix: true, gen: () => pixelScene({ seed: 5, sky: ['#0b1030', '#2a2f6a'], stars: true, sun: [70, 36, 12, '#f2f0d8'], moon: true,
    hills: [{ base: 100, amp: 14, f: 30, fill: '#1c2448', top: '#253060' },
      { base: 124, amp: 10, f: 24, fill: '#142034', top: '#1d3a2c', trees: 8, leaf: '#12301f' },
      { base: 146, amp: 7, f: 18, fill: '#2a1c14', top: '#21452a', topH: 6, trees: 3, leaf: '#163a24' }] }) },
  { id: 'winter', name: 'Зима', pix: true, gen: () => pixelScene({ seed: 9, sky: ['#9fc4e8', '#eef6ff'], clouds: '#ffffff',
    hills: [{ base: 92, amp: 16, f: 28, fill: '#c9d9ea', top: '#e9f1fa' },
      { base: 120, amp: 10, f: 22, fill: '#d7e4f0', top: '#ffffff', trees: 9, leaf: '#2e5d45', snowCap: true },
      { base: 146, amp: 6, f: 16, fill: '#e5eef7', top: '#ffffff', topH: 6, trees: 4, leaf: '#244e3a', snowCap: true }] }) },
  { id: 'sunsetpx', name: 'Закат', pix: true, gen: () => pixelScene({ seed: 4, sky: ['#3b1b5a', '#ff9a5a'], sun: [160, 108, 22, '#ffd27a'],
    hills: [{ base: 104, amp: 12, f: 30, fill: '#6a2f5c', top: '#7d3a6a' },
      { base: 128, amp: 9, f: 22, fill: '#3e1d3c', top: '#4e2547', trees: 6, leaf: '#2a1228' },
      { base: 150, amp: 6, f: 16, fill: '#221022', top: '#2e1630', topH: 6, trees: 3, leaf: '#1a0b1a' }] }) },
  { id: 'aurora', name: 'Сияние', css: 'radial-gradient(at 18% 22%, #1f8a62 0, transparent 48%), radial-gradient(at 82% 12%, #6a35b8 0, transparent 50%), radial-gradient(at 62% 86%, #1c4fa8 0, transparent 55%), radial-gradient(at 8% 92%, #b8326a 0, transparent 40%), #0b1020' },
  { id: 'dusk', name: 'Сумерки', css: 'linear-gradient(160deg, #2b1055 0%, #7b2f6b 42%, #ff7a59 78%, #ffc371 100%)' },
  { id: 'deep', name: 'Глубина', css: 'linear-gradient(180deg, #06223f 0%, #0b4f6c 55%, #1f9e95 100%)' },
  { id: 'forest', name: 'Лес', css: 'radial-gradient(ellipse at 50% 120%, #2f7a45 0%, #13341f 45%, #08140c 80%)' },
  { id: 'candy', name: 'Карамель', css: 'linear-gradient(135deg, #ff9a9e 0%, #fad0c4 40%, #a1c4fd 100%)' },
  { id: 'mono', name: 'Графит', css: 'radial-gradient(circle at 30% 20%, #3a3f45 0, #15181b 70%)' },
];
const _bgCache = {};
function presetValue(id) {
  const p = BG_PRESETS.find(b => b.id === id);
  if (!p) return null;
  if (p.css) return { css: p.css };
  if (!_bgCache[id]) _bgCache[id] = p.gen();
  return { css: `url(${_bgCache[id]})`, pix: true };
}

// ---------------------------------------------------------------- применение
const LOOK_KEYS = ['theme', 'accent', 'layout', 'bg', 'sidePos', 'compactToolbar'];
function lookOf(s) {
  return {
    theme: s.theme || 'hvoya', accent: s.accent || '', layout: s.layout || 'tiles', sidePos: s.sidePos || 'right',
    compactToolbar: !!s.compactToolbar, bg: Object.assign({ kind: 'none', value: '', blur: 0, dim: 35 }, s.bg || {}),
  };
}
let _bgReq = 0;
async function applyLook(st) {
  const L = lookOf(st);
  const root = document.documentElement;
  const th = THEMES.find(t => t.id === L.theme) || THEMES[0];
  root.dataset.theme = th.id;
  root.dataset.layout = L.layout;
  root.dataset.side = L.sidePos;
  root.classList.toggle('compact-tb', L.compactToolbar);
  for (const [k, v] of Object.entries(accentVars(L.accent || th.accent))) root.style.setProperty(k, v);
  const tx = textures();
  root.style.setProperty('--tex-dirt', `url(${tx.dirt})`);
  root.style.setProperty('--tex-stone', `url(${tx.stone})`);
  try { localStorage.setItem('hv-look', JSON.stringify(L)); } catch (e) { /* нет хранилища — не страшно */ }

  let bg = document.getElementById('bg');
  if (!bg) { bg = h('div', { id: 'bg' }); document.body.prepend(bg); }
  let kind = L.bg.kind, value = L.bg.value;
  if (kind === 'none' && th.bg) { kind = 'preset'; value = th.bg; }
  const my = ++_bgReq;
  let css = null, pix = false;
  if (kind === 'preset') { const p = presetValue(value); if (p) { css = p.css; pix = !!p.pix; } }
  else if (kind === 'image' && value) {
    const url = window.pywebview && window.pywebview.api ? await call('bg_url', value).catch(() => null) : null;
    if (my !== _bgReq) return;
    if (url) css = `url("${url}")`;
  }
  bg.style.background = css ? `${css} center / cover no-repeat` : '';
  bg.classList.toggle('pix', pix);
  bg.style.filter = L.bg.blur ? `blur(${L.bg.blur}px)` : '';
  bg.style.setProperty('--bg-dim', (L.bg.dim ?? 35) / 100);
  root.classList.toggle('has-bg', !!css);
}
// сразу при загрузке — из кэша, чтобы не мигала тема по умолчанию
try { const c = JSON.parse(localStorage.getItem('hv-look') || 'null'); if (c) { c.bg = { ...c.bg, kind: c.bg && c.bg.kind === 'image' ? 'none' : (c.bg || {}).kind }; applyLook(c); } } catch (e) { /* пусто */ }

let _saveLookT;
function saveLook(patch) {
  Object.assign(S.settings, patch);
  applyLook(S.settings);
  renderInstances();
  clearTimeout(_saveLookT);
  _saveLookT = setTimeout(async () => {
    const vals = {};
    LOOK_KEYS.forEach(k => { vals[k] = S.settings[k]; });
    const r = await call('save_settings', vals).catch(e => { toast(e.message, 'err'); return null; });
    if (r) Object.assign(S.settings, r);
  }, 350);
}

// ---------------------------------------------------------------- окно «Оформление»
function themePreview(th, cur, onpick) {
  const icons = ['grass', 'diamond', 'pine', 'chest', 'portal', 'tnt'];
  const el = h('button', { class: 'th-card' + (cur === th.id ? ' on' : ''), onclick: () => onpick(th.id), title: th.desc },
    h('div', { class: 'th-prev', 'data-theme': th.id },
      h('div', { class: 'tp-bar' }, h('i'), h('b'), h('b'), h('b')),
      h('div', { class: 'tp-body' },
        h('div', { class: 'tp-main' }, icons.map(k => h('div', { class: 'tp-tile' }, h('span', { style: { backgroundImage: `url(${pixUrl(PIX[k])})` } })))),
        h('div', { class: 'tp-side' }, h('div', { class: 'tp-play' }), h('div', { class: 'tp-line' }), h('div', { class: 'tp-line' }), h('div', { class: 'tp-line s' })))),
    h('div', { class: 'th-name' }, th.name, cur === th.id ? icon('check', 'sm') : null),
    h('div', { class: 'th-desc' }, th.desc));
  const pv = el.querySelector('.th-prev');
  for (const [k, v] of Object.entries(accentVars(th.accent))) pv.style.setProperty(k, v);
  if (th.bg) pv.style.background = presetValue(th.bg).css;  // «Стекло» — на своём фоне
  return el;
}

function openAppearance(tab = 'themes') {
  const cur = () => lookOf(S.settings);
  const panes = {};
  const navBtns = {};
  const holder = h('div', { class: 'pane' });
  const show = t => {
    Object.entries(navBtns).forEach(([k, b]) => b.classList.toggle('on', k === t));
    holder.innerHTML = '';
    holder.append(panes[t]());
  };

  panes.themes = () => {
    const L = cur();
    const wrap = h('div', { class: 'pane-scroll' });
    const draw = () => {
      const L2 = cur();
      wrap.innerHTML = '';
      const pick = id => { saveLook({ theme: id }); draw(); };
      wrap.append(
        h('div', { class: 'lk-h' }, 'Цветовые темы'),
        h('div', { class: 'th-grid' }, THEMES.filter(t => !t.special).map(t => themePreview(t, L2.theme, pick))),
        h('div', { class: 'lk-h' }, 'Особые темы', h('span', { class: 'muted' }, ' — полностью меняют вид лаунчера')),
        h('div', { class: 'th-grid' }, THEMES.filter(t => t.special).map(t => themePreview(t, L2.theme, pick))),
        h('div', { class: 'lk-h' }, 'Акцентный цвет'),
        h('div', { class: 'acc-row' },
          h('button', { class: 'acc-auto' + (!L2.accent ? ' on' : ''), onclick: () => { saveLook({ accent: '' }); draw(); } }, 'Как в теме'),
          ACCENTS.map(c => h('button', { class: 'acc-sw' + (L2.accent === c ? ' on' : ''), style: { background: c }, title: c,
            onclick: () => { saveLook({ accent: c }); draw(); } })),
          h('label', { class: 'acc-sw custom' + (L2.accent && !ACCENTS.includes(L2.accent) ? ' on' : ''), title: 'Свой цвет',
            style: L2.accent && !ACCENTS.includes(L2.accent) ? { background: L2.accent } : null },
          icon('plus', 'sm'), h('input', { type: 'color', value: L2.accent || '#4caf6a', onchange: e => { saveLook({ accent: e.target.value }); draw(); } }))));
    };
    draw();
    void L;
    return wrap;
  };

  panes.bg = () => {
    const wrap = h('div', { class: 'pane-scroll' });
    let images = [];
    const draw = () => {
      const L = cur();
      const th = THEMES.find(t => t.id === L.theme) || THEMES[0];
      const setBg = patch => { saveLook({ bg: { ...cur().bg, ...patch } }); draw(); };
      const isOn = (k, v) => L.bg.kind === k && (k === 'none' || L.bg.value === v);
      wrap.innerHTML = '';
      wrap.append(
        h('div', { class: 'bg-grid' },
          h('button', { class: 'bg-it none' + (isOn('none') ? ' on' : ''), onclick: () => setBg({ kind: 'none', value: '' }) },
            h('div', { class: 'bg-th' }, icon('x', 'lg')), h('span', null, th.bg ? 'Как в теме' : 'Без фона')),
          BG_PRESETS.map(p => h('button', { class: 'bg-it' + (isOn('preset', p.id) ? ' on' : ''), onclick: () => setBg({ kind: 'preset', value: p.id }) },
            h('div', { class: 'bg-th' + (p.pix ? ' pix' : ''), style: { background: `${presetValue(p.id).css} center / cover` } }), h('span', null, p.name)))),
        h('div', { class: 'lk-h' }, 'Свои картинки'),
        h('div', { class: 'bg-grid' },
          images.map(im => h('div', { class: 'bg-it' + (isOn('image', im.name) ? ' on' : ''), onclick: () => setBg({ kind: 'image', value: im.name }) },
            h('div', { class: 'bg-th', style: { backgroundImage: `url("${im.url}")` } }),
            h('span', null, im.name),
            h('button', { class: 'bg-del', title: 'Удалить', onclick: async e => {
              e.stopPropagation();
              const r = await safe(call('bg_remove', im.name));
              if (r) { images = r; if (isOn('image', im.name)) setBg({ kind: 'none', value: '' }); else draw(); }
            } }, icon('x', 'sm')))),
          h('button', { class: 'bg-it add', onclick: async () => {
            const r = await safe(call('bg_add'));
            if (r && r.length) { images = await call('bg_list'); setBg({ kind: 'image', value: r[0].name }); }
          } }, h('div', { class: 'bg-th' }, icon('plus', 'lg')), h('span', null, 'Картинка с компьютера')),
          h('button', { class: 'bg-it add', onclick: () => pickShotBg(async it => { images = await call('bg_list'); setBg({ kind: 'image', value: it.name }); }) },
            h('div', { class: 'bg-th' }, icon('camera', 'lg')), h('span', null, 'Из скриншотов игры'))),
        h('div', { class: 'lk-h' }, 'Настройка'),
        h('div', { class: 'row lk-sl' },
          h('div', { class: 'field' }, h('label', null, 'Размытие'), h('input', { type: 'range', min: 0, max: 30, value: L.bg.blur,
            oninput: e => { S.settings.bg = { ...cur().bg, blur: +e.target.value }; applyLook(S.settings); }, onchange: e => setBg({ blur: +e.target.value }) })),
          h('div', { class: 'field' }, h('label', null, 'Затемнение'), h('input', { type: 'range', min: 0, max: 90, value: L.bg.dim,
            oninput: e => { S.settings.bg = { ...cur().bg, dim: +e.target.value }; applyLook(S.settings); }, onchange: e => setBg({ dim: +e.target.value }) }))),
        h('div', { class: 'hint', style: { marginTop: '4px' } }, 'Фон виден за списком сборок, панели становятся полупрозрачными.'));
    };
    draw();
    call('bg_list').then(r => { images = r || []; draw(); }).catch(() => {});
    return wrap;
  };

  panes.view = () => {
    const L = cur();
    const mini = kind => h('div', { class: 'lay-prev ' + kind }, [0, 1, 2, 3].map(() => h('div', null, h('i'), h('b'))));
    const opt = (key, val, label, prev) => h('button', { class: 'lay' + (L[key] === val ? ' on' : ''), onclick: () => { saveLook({ [key]: val }); show('view'); } }, prev, h('span', null, label));
    return h('div', { class: 'pane-scroll' },
      h('div', { class: 'lk-h' }, 'Список сборок'),
      h('div', { class: 'lay-row' }, opt('layout', 'tiles', 'Плитки', mini('tiles')), opt('layout', 'list', 'Список', mini('list')), opt('layout', 'cards', 'Карточки', mini('cards'))),
      h('div', { class: 'lk-h' }, 'Панель сборки'),
      seg([['right', 'Справа'], ['left', 'Слева']], L.sidePos, v => saveLook({ sidePos: v })),
      h('div', { class: 'lk-h' }, 'Верхняя панель'),
      seg([['full', 'Кнопки с подписями'], ['compact', 'Только значки']], L.compactToolbar ? 'compact' : 'full', v => saveLook({ compactToolbar: v === 'compact' })));
  };

  const nav = h('div', { class: 'nav' },
    [['themes', 'palette', 'Темы'], ['bg', 'image', 'Фон'], ['view', 'layers', 'Вид']].map(([k, ic, t]) => (navBtns[k] = h('button', { onclick: () => show(k) }, icon(ic), t))),
    h('div', { class: 'spacer' }),
    h('button', { onclick: async () => {
      if (!await confirmBox('Сбросить оформление?', 'Тема, цвет, фон и вид списка вернутся к стандартным.', 'Сбросить', false)) return;
      saveLook({ theme: 'hvoya', accent: '', layout: 'tiles', sidePos: 'right', compactToolbar: false, bg: { kind: 'none', value: '', blur: 0, dim: 35 } });
      show('themes');
    } }, icon('refresh'), 'Сбросить'));
  modal({ title: 'Оформление', cls: 'wide look', body: h('div', { class: 'split' }, nav, holder) });
  show(tab);
}

async function pickShotBg(done) {
  const list = await safe(call('bg_recent_shots'));
  if (!list) return;
  if (!list.length) { toast('Скриншотов пока нет — в игре они делаются клавишей F2', 'warn'); return; }
  const m = modal({ title: 'Скриншот для фона', cls: 'wide',
    body: h('div', { class: 'modal-b' }, h('div', { class: 'shots' }, list.map(s => h('div', { class: 'shot', style: { cursor: 'pointer' }, onclick: async () => {
      const r = await safe(call('bg_from_shot', s.inst, s.name));
      if (r) { m.close(); done(r); toast('Фон установлен'); }
    } }, h('img', { src: s.url, loading: 'lazy' }), h('span', { style: { opacity: 1 } }, s.instName))))) });
}
