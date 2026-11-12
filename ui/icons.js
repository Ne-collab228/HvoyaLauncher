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
  palette: '<path d="M12 3a9 9 0 1 0 0 18c1.1 0 2-.9 2-2 0-.5-.2-1-.5-1.3-.3-.4-.5-.8-.5-1.3 0-1.1.9-2 2-2h2.4A4.6 4.6 0 0 0 21 9.8C21 6 17 3 12 3z"/><circle cx="7.5" cy="11" r="1" fill="currentColor"/><circle cx="10" cy="7" r="1" fill="currentColor"/><circle cx="15" cy="7" r="1" fill="currentColor"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/>',
  sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 15l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>',
  server: '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/>',
  shield: '<path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
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
  iron: { map: ["SsSSSSSS", "SSSCcSsS", "SsScCSSS", "SSSSSSSs", "sCcSSsSS", "SccSSCcS", "SSSSScCS", "SSsSSSSs"], pal: {"S": "#8c8c8c", "s": "#6c6c6c", "C": "#e3c0a3", "c": "#b48a6b"} },
  emerald: { map: ["SSSsSSSS", "SCcSSSsS", "SccSsCSS", "sSSSCcSs", "SSsSSSSS", "SCSSSCcS", "ScCSScSS", "SSSSsSSs"], pal: {"S": "#8c8c8c", "s": "#6c6c6c", "C": "#5ff59a", "c": "#1a9c4c"} },
  redstone: { map: ["SsSSSSSS", "SSSCcSsS", "SsScCSSS", "SSSSSSSs", "sCcSSsSS", "SccSSCcS", "SSSSScCS", "SSsSSSSs"], pal: {"S": "#8c8c8c", "s": "#6c6c6c", "C": "#ff4a4a", "c": "#a81414"} },
  lapis: { map: ["SSSsSSSS", "SCcSSSsS", "SccSsCSS", "sSSSCcSs", "SSsSSSSS", "SCSSSCcS", "ScCSScSS", "SSSSsSSs"], pal: {"S": "#8c8c8c", "s": "#6c6c6c", "C": "#5b7fe8", "c": "#1f3c9a"} },
  coal: { map: ["SsSSSSSS", "SSSCcSsS", "SsScCSSS", "SSSSSSSs", "sCcSSsSS", "SccSSCcS", "SSSSScCS", "SSsSSSSs"], pal: {"S": "#8c8c8c", "s": "#6c6c6c", "C": "#3b3b3b", "c": "#1d1d1d"} },
  copper: { map: ["SSSsSSSS", "SCcSSSsS", "SccSsCSS", "sSSSCcSs", "SSsSSSSS", "SCSSSCcS", "ScCSScSS", "SSSSsSSs"], pal: {"S": "#8c8c8c", "s": "#6c6c6c", "C": "#f08f5c", "c": "#a3542f"} },
  sand: { map: ["YYYyYYYY", "YyYYYYyY", "YYYYyYYY", "yYYYYYYy", "YYyYYYYY", "YYYYYyYY", "YyYYYYYy", "YYYYyYYY"], pal: {"Y": "#dbd3a0", "y": "#c4b97f"} },
  snow: { map: ["WWWWWWWW", "WwWWwWWW", "wDwWDwWw", "DDDwDDwD", "DdDDDDDD", "DDDdDDdD", "DdDDDDDD", "DDDDdDDD"], pal: {"W": "#f4f8fb", "w": "#cfdbe6", "D": "#8a5a32", "d": "#6e4526"} },
  netherrack: { map: ["NnNNmNNn", "NNmNNnNN", "nNNNNNmN", "NmNnNNNN", "NNNNmNnN", "mNnNNNNN", "NNNmNNnN", "NnNNNmNN"], pal: {"N": "#8a2f2f", "n": "#5e1b1b", "m": "#a8443d"} },
  obsidian: { map: ["OOoOOOpO", "OpOOoOOO", "OOOOOoOO", "oOOpOOOo", "OOOOOOpO", "OoOOoOOO", "OOpOOOOo", "oOOOOpOO"], pal: {"O": "#15101f", "o": "#2b1f40", "p": "#4a3470"} },
  glowstone: { map: ["yYwYyYYy", "YYYyYwYY", "wYyYYYyY", "YyYYwYYY", "YYYyYYyw", "yYwYYyYY", "YYYYwYyY", "YyYyYYYw"], pal: {"Y": "#f8d26b", "y": "#c79a3e", "w": "#fff3b8"} },
  lava: { map: ["LLlLLyLL", "LyLLlLLl", "lLLyLLLL", "LLlLLLyL", "LyLLlLLL", "LLLLLyLl", "lLyLLLLL", "LLLlLyLL"], pal: {"L": "#ff7a1a", "l": "#d44a0a", "y": "#ffc23d"} },
  ice: { map: ["IIIwIIII", "IwIIIIiI", "IIiIIwII", "IIIIiIII", "iIwIIIIw", "IIIIIiII", "IwIIwIII", "IIiIIIIi"], pal: {"I": "#9ec3f5", "i": "#7aa6e8", "w": "#d6e8ff"} },
  planks: { map: ["PPPPpPPP", "PpPPPPPP", "KKKKKKKK", "PPPpPPPP", "PPPPPPpP", "KKKKKKKK", "PPpPPPPP", "PPPPPPPp"], pal: {"P": "#b88a4e", "p": "#9a6f38", "K": "#6e4b22"} },
  bricks: { map: ["RRRMRRRM", "rRRMRrRM", "MMMMMMMM", "RMRRRMRR", "RMrRRMRr", "MMMMMMMM", "RRRMRRRM", "RrRMRRrM"], pal: {"R": "#a5533f", "r": "#8a3f2e", "M": "#c9b9a8"} },
  log: { map: ["BBBBBBBB", "BWWWWWWB", "BWwwwwWB", "BWwWWwWB", "BWwWWwWB", "BWwwwwWB", "BWWWWWWB", "BBBBBBBB"], pal: {"B": "#5e4426", "W": "#c19a5b", "w": "#a07c43"} },
  leaves: { map: ["LlLdLLlL", "dLLlLdLL", "LLdLLLLd", "lLLLdLlL", "LdLlLLLL", "LLLLdLlL", "LlLdLLLd", "dLLLlLLL"], pal: {"L": "#3f8f2f", "l": "#2c6b20", "d": "#58b043"} },
  bookshelf: { map: ["PPPPPPPP", "KrgKbyrK", "KrgKbyrK", "PPPPPPPP", "PPPPPPPP", "KbyrKgbK", "KbyrKgbK", "PPPPPPPP"], pal: {"P": "#b88a4e", "K": "#3b2512", "r": "#b33a3a", "g": "#3f8a3f", "b": "#3a5bb3", "y": "#c9a93a"} },
  pumpkin: { map: ["OoOOOOoO", "OoOOOOoO", "OKYOOKYO", "OoOOOOoO", "OKYYYYKO", "OoKYYKoO", "OoOOOOoO", "OoOOOOoO"], pal: {"O": "#e38a1e", "o": "#c06d10", "K": "#3a2108", "Y": "#ffd25a"} },
  melon: { map: ["MmMMmMMm", "MmMMmMMm", "MmMmmMMm", "MmMMmMmm", "MmMMmMMm", "mmMMmMMm", "MmMMmmMm", "MmMMmMMm"], pal: {"M": "#6ab03a", "m": "#3e7a1f"} },
  cactus: { map: [".cCCCCc.", ".cCyCCc.", ".cCCCyc.", ".cyCCCc.", ".cCCCCc.", ".cCCyCc.", ".cyCCCc.", ".cCCCCc."], pal: {"C": "#3f8f3a", "c": "#2b6b28", "y": "#d9e08a"} },
  amethyst: { map: ["...P....", "..PpP..p", "..PpP.pP", ".PPpPPpP", ".PpPPPpP", "PPpPpPPP", "PpPPPpPp", "PPPPPPPP"], pal: {"P": "#a77be0", "p": "#7c4fc4"} },
  sword: { map: ["...WW...", "...Ww...", "...Ww...", "...Ww...", "...Ww...", ".GGGGGG.", "...BB...", "...BB..."], pal: {"W": "#e4ecf0", "w": "#aab6bd", "G": "#d9a521", "B": "#6b4423"} },
  pickaxe: { map: ["..CCCC..", ".CCccCC.", "CC.BB.CC", "C..BB..C", "...BB...", "...BB...", "...BB...", "...BB..."], pal: {"C": "#b8c4cc", "c": "#7d8a92", "B": "#8a5a32"} },
  apple: { map: ["....B...", "...BL...", ".RRRRRR.", "RwRRRRRr", "RwRRRRRr", "RRRRRRRr", ".RRRRrr.", "..RR.r.."], pal: {"R": "#d93a3a", "r": "#a62525", "w": "#ff8a8a", "L": "#4fb36a", "B": "#6b4423"} },
  heart: { map: ["........", ".RR..RR.", "RwRRRRRR", "RwRRRRRR", "RRRRRRRR", ".RRRRRR.", "..RRRR..", "...RR..."], pal: {"R": "#e23b4b", "w": "#ff9aa5"} },
  star: { map: ["...YY...", "...YY...", "YYYYYYYY", ".YYYYYY.", "..YYYY..", ".YYyyYY.", ".YY..YY.", "Y......Y"], pal: {"Y": "#ffd84a", "y": "#d9a521"} },
  potion: { map: ["...BB...", "...GG...", "...GG...", "..GPPG..", ".GPPpPG.", ".GPpPPG.", ".GPPPPG.", "..GGGG.."], pal: {"B": "#8a5a32", "G": "#cfe3f0", "P": "#d14fd1", "p": "#9c2f9c"} },
  orb: { map: ["..TTTT..", ".TtTTTT.", "TtWTTTTT", "TTTTKTTT", "TTTKKTTT", "TTTTTTTt", ".TTTTtT.", "..TTTT.."], pal: {"T": "#2c9c8a", "t": "#5fd6c2", "W": "#c9fff4", "K": "#145c52"} },
  gem: { map: ["........", "..CCCC..", ".CWcCcC.", "CCCCCCCC", ".CcCCcC.", "..CccC..", "...CC...", "........"], pal: {"C": "#ff4f8a", "c": "#c22a63", "W": "#ffd0e0"} },
  fish: { map: ["........", "..BB....", ".BBBB..B", "BWKBBBBB", "BBBBBBBB", ".BbbB..B", "..BB....", "........"], pal: {"B": "#5d8fd6", "b": "#3f6db0", "W": "#ffffff", "K": "#1a1a1a"} },
  cake: { map: ["........", ".WWWWWW.", "WWrWWrWW", "WWWWWWWW", "BBBBBBBB", "bbbbbbbb", "BBBBBBBB", ".bbbbbb."], pal: {"W": "#f4f1ea", "r": "#d93a3a", "B": "#b07a45", "b": "#8a5a2f"} },
  flower: { map: ["...RR...", "..RRRR..", ".RRYYRR.", "..RRRR..", "...LR...", ".LLL....", "...L.LL.", "...LL..."], pal: {"R": "#e0457b", "Y": "#ffd84a", "L": "#4fb36a"} },
  mushroom: { map: ["..RRRR..", ".RWRRWR.", "RRRRRRRR", "RWRRRRWR", "...SS...", "...SS...", "..SSSS..", "........"], pal: {"R": "#d43b3b", "W": "#ffffff", "S": "#e6dccb"} },
  book: { map: [".KKKKKK.", "KRRRRRRK", "KRYRRRRK", "KRRRRRRK", "KRRRRRRK", "KRRRRRRK", "KWWWWWWK", ".KKKKKK."], pal: {"K": "#3b2512", "R": "#8a3a2a", "Y": "#d9c24a", "W": "#efe6d6"} },
  moon: { map: ["..WWW...", ".WWw....", "WWw.....", "WWw.....", "WWw.....", "WWWw....", ".WWWWw..", "..WWW..."], pal: {"W": "#e9edf5", "w": "#b9c2d3"} },
  fire: { map: ["...R....", "..RR..R.", "..RYR.R.", ".RYYRRR.", ".RYYYRR.", "RYYWYYR.", "RYWWWYRR", ".RYYYYR."], pal: {"R": "#e64a19", "Y": "#ffb020", "W": "#fff2a8"} },
  slime: { map: ["GGGGGGGG", "GggggggG", "GgKgKggG", "GggggggG", "GgggKggG", "GggggggG", "GggggggG", "GGGGGGGG"], pal: {"G": "#5fbf4a", "g": "#86d96f", "K": "#2d5e23"} },
  rocket: { map: ["...WW...", "..WRRW..", "..WWWW..", "..WBBW..", "..WWWW..", ".RWWWWR.", ".R.YY.R.", "...YY..."], pal: {"W": "#e9edf5", "R": "#d43b3b", "B": "#3d7fe0", "Y": "#ffb020"} },
};
const PIX_NAMES = {"grass": "Трава", "stone": "Камень", "diamond": "Алмаз", "gold": "Золото", "pine": "Ель", "cone": "Шишка", "chest": "Сундук", "portal": "Портал", "tnt": "Динамит", "water": "Вода", "iron": "Железо", "emerald": "Изумруд", "redstone": "Редстоун", "lapis": "Лазурит", "coal": "Уголь", "copper": "Медь", "sand": "Песок", "snow": "Снег", "netherrack": "Незерак", "obsidian": "Обсидиан", "glowstone": "Светокамень", "lava": "Лава", "ice": "Лёд", "planks": "Доски", "bricks": "Кирпичи", "log": "Бревно", "leaves": "Листва", "bookshelf": "Книжная полка", "pumpkin": "Тыква", "melon": "Арбуз", "cactus": "Кактус", "amethyst": "Аметист", "sword": "Меч", "pickaxe": "Кирка", "apple": "Яблоко", "heart": "Сердце", "star": "Звезда", "potion": "Зелье", "orb": "Сфера", "gem": "Кристалл", "fish": "Рыба", "cake": "Торт", "flower": "Цветок", "mushroom": "Гриб", "book": "Книга", "moon": "Луна", "fire": "Огонь", "slime": "Слизь", "rocket": "Ракета"};
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
