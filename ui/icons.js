// Иконки интерфейса (SVG) и пиксельные иконки сборок.
const ICONS = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  sliders: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  play: '<path d="M7 5v14l12-7z" fill="currentColor"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="1.5" fill="currentColor"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  box: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9zM12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>',
  terminal: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M13 15h4"/>',
  note: '<path d="M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h5"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14.5-4.5L4 8M4 4v4h4M4 13a8 8 0 0 0 14.5 4.5L20 16M20 20v-4h-4"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>',
  chev: '<path d="M6 9l6 6 6-6"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>',
  upload: '<path d="M12 20V9M7 14l5-5 5 5M5 4h14"/>',
  wrench: '<path d="M14.5 5.5a4 4 0 0 0 4.9 4.9L11 18.8a2.1 2.1 0 0 1-3-3l8.4-8.4"/><path d="M14.5 5.5l2-2 4 4-2 2"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3"/>',
  check: '<path d="M5 12l5 5 9-10"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  layers: '<path d="M12 3l9 5-9 5-9-5zM3 13l9 5 9-5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
  file: '<path d="M6 3h9l4 4v14H6zM14 3v5h5"/>',
  disk: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
  swap: '<path d="M4 8h13l-3-3M20 16H7l3 3"/>',
  archive: '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4"/>',
  dots: '<circle cx="5" cy="12" r="1.3" fill="currentColor"/><circle cx="12" cy="12" r="1.3" fill="currentColor"/><circle cx="19" cy="12" r="1.3" fill="currentColor"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.5"/>',
  zap: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  alert: '<path d="M12 3l10 18H2zM12 10v5M12 18v.5"/>',
  chat: '<path d="M4 5h16v11H9l-5 4z"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
};

function icon(name, cls) {
  const s = document.createElement('i');
  s.className = 'ic' + (cls ? ' ' + cls : '');
  s.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ''}</svg>`;
  return s;
}

// ------------------------------------------------------------ пиксельные иконки 8x8
const PIX = {
  grass: { map: ['GGGGGGGG', 'GgGGgGGG', 'gDgGDgGg', 'DDDgDDgD', 'DdDDDDDD', 'DDDdDDdD', 'DdDDDDDD', 'DDDDdDDD'],
    pal: { G: '#62b03c', g: '#4a8f2c', D: '#8a5a32', d: '#6e4526' } },
  stone: { map: ['SSSsSSSS', 'SsSSSSsS', 'SSSSsSSS', 'sSSSSSSs', 'SSsSSSSS', 'SSSSSsSS', 'SsSSSSSS', 'SSSSsSSs'],
    pal: { S: '#8c8c8c', s: '#6c6c6c' } },
  diamond: { map: ['SSSsSSSS', 'SCcSSSsS', 'SccSsCSS', 'sSSSCcSs', 'SSsSSSSS', 'SCSSSCcS', 'ScCSScSS', 'SSSSsSSs'],
    pal: { S: '#8c8c8c', s: '#6c6c6c', C: '#7ff3e6', c: '#2cc5b5' } },
  gold: { map: ['SSSsSSSS', 'SYySSSsS', 'SyySsYSS', 'sSSSYySs', 'SSsSSSSS', 'SYSSSYyS', 'SyYSSySS', 'SSSSsSSs'],
    pal: { S: '#8c8c8c', s: '#6c6c6c', Y: '#ffe36b', y: '#d6a52b' } },
  pine: { map: ['...GG...', '..GgGG..', '...GG...', '..GGgG..', '.GgGGGG.', 'GGGGGgGG', '...TT...', '...Tt...'],
    pal: { G: '#2f8a4c', g: '#4fb36a', T: '#7a4a24', t: '#5d361a' } },
  cone: { map: ['...gg...', '..BbBb..', '.bBbBbB.', '.BbBbBb.', '.bBbBbB.', '..BbBb..', '..bBbB..', '...bb...'],
    pal: { g: '#4fb36a', B: '#a8703a', b: '#7a4c22' } },
  chest: { map: ['WWWWWWWW', 'WwwwwwwW', 'WwwwwwwW', 'KKKYYKKK', 'WwwYYwwW', 'WwwwwwwW', 'WwwwwwwW', 'WWWWWWWW'],
    pal: { W: '#6b4423', w: '#a0702f', K: '#3b2512', Y: '#d9c24a' } },
  portal: { map: ['OOOOOOOO', 'OpPppPpO', 'OPppPPpO', 'OpPPpPPO', 'OPpPPppO', 'OppPpPPO', 'OPpPPpPO', 'OOOOOOOO'],
    pal: { O: '#1c1427', p: '#7b3fd6', P: '#b06cff' } },
  tnt: { map: ['RRRRRRRR', 'RrRRrRRr', 'WWWWWWWW', 'WKWKWKWW', 'WWWWWWWW', 'RRrRRRrR', 'RrRRrRRR', 'RRRRRRRR'],
    pal: { R: '#d4473c', r: '#a8322a', W: '#e9e4d8', K: '#2a2a2a' } },
  water: { map: ['BBbBBBBb', 'BbBBBbBB', 'BBBBbBBB', 'bBBbBBBb', 'BBBBBBbB', 'BbBBbBBB', 'BBBbBBBb', 'bBBBBbBB'],
    pal: { B: '#3d7fe0', b: '#5a9cf0' } },
};
const DEFAULT_HEAD = { map: ['HHHHHHHH', 'HHHHHHHH', 'HSSSSSSH', 'SSSSSSSS', 'SWESSEWS', 'SSSssSSS', 'SSmmmmSS', 'SSSSSSSS'],
  pal: { H: '#4a3020', S: '#d9a277', s: '#c08a62', W: '#ffffff', E: '#3a5bb8', m: '#8a4d3a' } };

const _pixCache = {};
function pixUrl(def) {
  const key = def.map.join('|');
  if (_pixCache[key]) return _pixCache[key];
  const c = document.createElement('canvas');
  c.width = c.height = 8;
  const g = c.getContext('2d');
  def.map.forEach((row, y) => [...row].forEach((ch, x) => {
    if (def.pal[ch]) { g.fillStyle = def.pal[ch]; g.fillRect(x, y, 1, 1); }
  }));
  return (_pixCache[key] = c.toDataURL());
}
