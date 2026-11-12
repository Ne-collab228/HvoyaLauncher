'use strict';
// Код сборки (поделиться с друзьями) и окно «Что нового».

// ================================================================ код сборки
async function openShare(inst) {
  const body = h('div', { class: 'modal-b' }, spinner('Собираю список модов…'));
  const m = modal({ title: `Поделиться «${inst.name}»`, cls: 'mid', body });
  const r = await call('share_code', inst.id).catch(e => { toast(e.message, 'err'); return null; });
  if (!r) { m.close(); return; }
  const ta = h('textarea', { class: 'input share-code', rows: 4, readOnly: true, value: r.code, onclick: e => e.target.select() });
  const copy = async btn => {
    try { await navigator.clipboard.writeText(r.code); } catch (e) { ta.select(); document.execCommand('copy'); }
    btn.lastChild.textContent = 'Скопировано';
    setTimeout(() => { btn.lastChild.textContent = 'Копировать'; }, 1600);
  };
  const parts = [];
  if (r.modpack) parts.push(`модпак «${r.modpack}»`);
  if (r.count) parts.push(`${r.count} ${plural(r.count, 'файл', 'файла', 'файлов')} с Modrinth и CurseForge`);
  body.innerHTML = '';
  body.append(...[
    h('div', { class: 'share-sum' }, h('div', { class: 'share-ico', style: { backgroundImage: `url(${instIconUrl(inst)})` } }),
      h('div', null, h('b', null, inst.name), h('div', { class: 'muted' },
        `${LOADER_NAMES[inst.loader]} ${inst.mc}${parts.length ? ' · ' + parts.join(' + ') : ' · без модов'}`))),
    ta,
    h('div', { class: 'hint', style: { marginTop: '8px' } },
      `${r.code.length} символов. Друг вставляет код в Hvoya: «Импорт → По коду сборки» — лаунчер сам скачает ту же версию, загрузчик и все моды.`),
    r.code.length > 1900 ? h('div', { class: 'opt-note warn' }, icon('alert'), h('div', null, 'Код длиннее одного сообщения Discord — лучше отправить его файлом (кнопка «В файл»).')) : null,
    r.skipped.length ? h('div', { class: 'card' }, h('h4', null, icon('alert'), `Не попадут в код: ${r.skipped.length}`),
      h('div', { class: 'muted', style: { fontSize: '12px', marginBottom: '6px' } }, 'Этих файлов нет ни на Modrinth, ни на CurseForge. Чтобы передать их тоже, используйте «Экспорт → .zip».'),
      h('div', { class: 'share-skip' }, r.skipped.map(s => h('div', null, s)))) : null,
    h('div', { class: 'muted', style: { fontSize: '12px', marginTop: '10px' } }, 'В код не входят миры, настройки и конфиги модов — только сама сборка.')].filter(Boolean));
  m.el.append(h('div', { class: 'modal-f' },
    h('button', { class: 'btn', onclick: () => safe(call('share_save', r.code, inst.name)).then(p => p && toast('Сохранено')) }, icon('download'), 'В файл'),
    h('div', { class: 'spacer' }),
    h('button', { class: 'btn', onclick: () => m.close() }, 'Закрыть'),
    h('button', { class: 'btn primary', onclick: e => copy(e.currentTarget) }, icon('copy'), h('span', null, 'Копировать'))));
  setTimeout(() => ta.select(), 50);
}
function plural(n, one, few, many) {
  const a = n % 10, b = n % 100;
  return a === 1 && b !== 11 ? one : a >= 2 && a <= 4 && (b < 10 || b >= 20) ? few : many;
}

async function openImportCode(prefill = '') {
  const ta = h('textarea', { class: 'input share-code', rows: 4, placeholder: 'Вставьте код вида HVOYA1:…', spellcheck: false });
  const prev = h('div');
  const name = h('input', { class: 'input' });
  let code = '', ok = false;
  const btn = h('button', { class: 'btn primary', disabled: true }, icon('download'), 'Установить');
  let req = 0;
  const check = debounce(async () => {
    code = ta.value.trim();
    ok = false; btn.disabled = true;
    prev.innerHTML = '';
    if (!code) return;
    const my = ++req;
    prev.append(spinner('Читаю код…'));
    let p;
    try { p = await call('share_preview', code); } catch (e) {
      if (my !== req) return;
      prev.innerHTML = '';
      prev.append(h('div', { class: 'opt-note warn' }, icon('alert'), h('div', null, e.message)));
      return;
    }
    if (my !== req) return;
    prev.innerHTML = '';
    name.value = p.name;
    const counts = Object.entries(p.counts).map(([k, n]) => `${({ mods: 'моды', resourcepacks: 'ресурспаки', shaderpacks: 'шейдеры' })[k]}: ${n}`);
    prev.append(h('div', { class: 'card' },
      h('div', { class: 'share-sum', style: { marginBottom: '12px' } },
        h('div', { class: 'share-ico', style: { backgroundImage: `url(${p.modpack && p.modpack.icon ? p.modpack.icon : pixUrl(PIX[p.icon] || PIX.grass)})` } }),
        h('div', null, h('div', { class: 'chips', style: { justifyContent: 'flex-start' } },
          h('span', { class: 'chip' }, p.mc),
          h('span', { class: 'chip ld-' + p.loader }, `${LOADER_NAMES[p.loader]} ${p.loaderVersion || ''}`.trim()),
          p.modpack ? h('span', { class: 'chip' }, `Модпак: ${p.modpack.title}`) : null),
        h('div', { class: 'muted', style: { marginTop: '4px', fontSize: '12px' } }, counts.length ? counts.join(' · ') : 'без модов'))),
      h('div', { class: 'field', style: { marginBottom: 0 } }, h('label', null, 'Название сборки'), name)));
    ok = true; btn.disabled = false;
  }, 300);
  ta.addEventListener('input', check);
  const m = modal({ title: 'Сборка по коду', cls: 'mid',
    body: h('div', { class: 'modal-b' },
      h('div', { class: 'muted', style: { marginBottom: '8px' } }, 'Друг нажимает «Поделиться» у своей сборки и присылает код. Вставьте его сюда:'),
      ta,
      h('div', { class: 'row', style: { margin: '8px 0 4px' } },
        h('button', { class: 'btn sm', onclick: async () => {
          try { ta.value = await navigator.clipboard.readText(); check(); } catch (e) { toast('Нет доступа к буферу — вставьте Ctrl+V', 'warn'); }
        } }, icon('copy'), 'Вставить из буфера'),
        h('button', { class: 'btn sm', onclick: async () => { const t = await safe(call('share_open_file')); if (t) { ta.value = t.trim(); check(); } } }, icon('file'), 'Открыть файл .hvoya')),
      prev),
    footer: [h('button', { class: 'btn', onclick: () => m.close() }, 'Отмена'), btn] });
  btn.onclick = async () => {
    if (!ok) return;
    const id = await safe(call('share_install', code, name.value.trim()));
    if (id) { m.close(); toast('Установка начата — прогресс внизу'); }
  };
  if (prefill) { ta.value = prefill; check(); } else {
    try { const t = await navigator.clipboard.readText(); if (t && t.includes('HVOYA1:')) { ta.value = t.trim(); check(); } } catch (e) { /* буфер недоступен */ }
  }
  setTimeout(() => ta.focus(), 50);
}

// ================================================================ «Что нового»
const CHANGELOG = [
  { v: '2.1.0', date: '2026-11-12', items: [
    '**Зеркала загрузок** — Mojang, библиотеки, Forge/NeoForge, Fabric/Quilt, Modrinth и CurseForge берутся с зеркал, если основные серверы недоступны без VPN. Режим — в настройках.',
    '**Серверы** — вкладка в сборке: список из игры (servers.dat), онлайн, пинг, MOTD, добавление и правка, кнопка «Играть» сразу заходит на сервер.',
    '**Проверка модов** — битые файлы, моды не под тот загрузчик или версию игры, дубликаты, недостающие зависимости (можно поставить в один клик), конфликты.',
    '**Ярлык на рабочий стол** — запуск сборки в один клик (меню «Ещё…» в панели сборки).',
    '**Компактная боковая панель** — все кнопки помещаются без прокрутки, редкие действия в меню «Ещё…».',
  ] },
  { v: '2.0.2', date: '2026-11-12', items: [
    '**NeoForge без VPN** — если maven.neoforged.net недоступен, список версий и установщик берутся с зеркала; последний список запоминается.',
  ] },
  { v: '2.0.1', date: '2026-11-11', items: [
    '**NeoForge для Minecraft 26.x** — список версий загрузчика больше не пустой для 26.1, 26.1.1, 26.2 и новее.',
  ] },
  { v: '2.0', date: '2026-11-10', items: [
    '**Оформление** — 18 тем: 12 цветовых и 6 особых, которые полностью меняют интерфейс: Пиксель, Терминал, Ретро 98, Стекло, Неон, Блокнот. Свой акцентный цвет.',
    '**Фон** — пиксельные пейзажи, градиенты, своя картинка или скриншот из игры; размытие и затемнение.',
    '**Вид списка сборок** — плитки, список или большие карточки; панель сборки слева или справа; верхняя панель только значками.',
    '**Поделиться сборкой** — короткий код: друг вставляет его через «Импорт → По коду сборки», и лаунчер ставит ту же версию, загрузчик и моды.',
    '**Время в игре** — живой счётчик во время игры, статистика по дням и по сборкам (клик по «Всего в игре» внизу).',
    '**Обновления** модов, ресурспаков и шейдеров — с Modrinth и CurseForge, счётчик прямо в панели сборки, обновление одного мода или всех сразу.',
    '**Сортировка сборок**: по названию, недавние, по времени в игре, новые.',
    '**39 новых иконок** для сборок.',
    'Окно «Что нового» после обновления.', 'Сохранение времени в игре раз в минуту — не теряется при закрытии лаунчера.'] },
  { v: '1.5', date: '2026-11-10', items: [
    '**Ускорить игру** — Sodium, Iris, ModernFix и другие моды оптимизации одной кнопкой (на Forge — Embeddium, Oculus).',
    '**Обновление модпаков** с Modrinth и CurseForge с бэкапом миров; настройки и свои моды сохраняются.',
    '**Скины в 3D** и свой скин для офлайн-аккаунта (через CustomSkinLoader).',
    '**Предупреждения о памяти** перед запуском.'] },
  { v: '1.4', date: '2026-11-09', items: [
    '**Миры**: бэкапы, восстановление, импорт, копирование в другую сборку.',
    '**Анализ вылетов** — причина по-русски и что делать.',
    '**Экспорт** в .mrpack и .zip, **галерея скриншотов**, **статус в Discord**.'] },
  { v: '1.3.2', date: '2026-11-09', items: ['Скины Ely.by грузятся даже на нестабильном интернете (через лаунчер, с повторами и кэшем).'] },
  { v: '1.3.1', date: '2026-11-09', items: ['Загрузка не зависает и не начинается заново: каждый файл повторяется до 10 раз.', 'Лицензия MIT.'] },
  { v: '1.3', date: '2026-11-09', items: ['**Автообновление** лаунчера в один клик.', 'Исправлена прокрутка в окне создания сборки.'] },
  { v: '1.2', date: '2026-11-09', items: ['**Установщик** с ярлыками и удалением через «Параметры».'] },
  { v: '1.1', date: '2026-11-09', items: ['**Хранилище** — сколько места занимает каждая сборка, очистка.', '**Импорт** из Prism, MultiMC, CurseForge, Modrinth App, ATLauncher, TLauncher.'] },
  { v: '1.0', date: '2026-11-09', items: ['Первый релиз: офлайн и Ely.by, все загрузчики, моды и модпаки с Modrinth и CurseForge.'] },
];
function cmpVer(a, b) {
  const pa = String(a).split('.').map(Number), pb = String(b).split('.').map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] || 0) - (pb[i] || 0);
    if (d) return d;
  }
  return 0;
}
function mdLine(t) {
  const el = h('li');
  t.split(/(\*\*[^*]+\*\*)/).forEach(p => el.append(p.startsWith('**') ? h('b', null, p.slice(2, -2)) : p));
  return el;
}
function openNews(since) {
  const fresh = since ? CHANGELOG.filter(c => cmpVer(c.v, since) > 0) : [];
  const list = fresh.length ? fresh : CHANGELOG.slice(0, 1);
  const older = CHANGELOG.filter(c => !list.includes(c));
  const ver = c => h('div', { class: 'news-v' }, h('div', { class: 'news-h' }, h('b', null, `Версия ${c.v}`), h('span', { class: 'muted' }, new Date(c.date + 'T12:00').toLocaleDateString('ru', { day: 'numeric', month: 'long', year: 'numeric' }))),
    h('ul', null, c.items.map(mdLine)));
  const olderBox = h('div', { class: 'hidden' }, older.map(ver));
  const more = older.length ? h('button', { class: 'btn sm', onclick: e => { olderBox.classList.remove('hidden'); e.currentTarget.remove(); } }, icon('chev'), 'Прошлые версии') : null;
  const m = modal({ title: since && fresh.length ? `Hvoya обновился до ${S.version}` : 'Что нового', cls: 'mid news',
    body: h('div', { class: 'modal-b' },
      h('div', { class: 'news-top' }, h('div', { class: 'news-logo', style: { backgroundImage: `url(${pixUrl(PIX.cone)})` } }),
        h('div', null, h('div', { class: 'news-title' }, `Hvoya Launcher ${S.version}`), h('div', { class: 'muted' }, 'Вот что изменилось'))),
      list.map(ver), more, olderBox),
    footer: [
      list[0] && list[0].v === '2.0' ? h('button', { class: 'btn', onclick: () => { m.close(); openAppearance(); } }, icon('palette'), 'Выбрать тему') : null,
      h('div', { class: 'spacer' }),
      h('button', { class: 'btn primary', onclick: () => m.close() }, 'Отлично')] });
}
function checkNews() {
  const last = S.settings.lastSeenVersion || '';
  if (last === S.version) return;
  // первый запуск лаунчера вообще — без окна; обновление со старой версии (до 1.6 поля не было) — показываем
  const show = last ? cmpVer(S.version, last) > 0 : S.instances.length > 0;
  call('save_settings', { lastSeenVersion: S.version }).then(r => { if (r) S.settings = r; }).catch(() => {});
  if (show) setTimeout(() => openNews(last || '1.5'), 700);
}
