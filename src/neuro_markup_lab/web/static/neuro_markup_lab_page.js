// Страница NeuroMarkupLab: каталог видео и каталог боевых JSON (помнит браузер), список видео
// с раскрывающейся карточкой. Тело карточки — модуль кадра NML.frame: кадр с разметкой, переключатель
// «Боевая | Рядом с видео», карандаш редактора, справа — файлы разметки, выбор боевой вручную, сведения.
// Боевая, выбранная вручную, запоминается браузером для пары «каталог JSON + видео».
// Только представление: данные — из API страницы.
(function () {
  var C = NML.common, esc = C.esc;
  // Ключи localStorage: каталог видео, «в подкаталогах», каталог JSON
  var KEY_VIDEO_DIR = 'nml_video_dir', KEY_RECURSIVE = 'nml_recursive', KEY_JSONS_DIR = 'nml_jsons_dir';
  // Ключ localStorage: боевая разметка, выбранная вручную: «каталог JSON\nвидео» → ключ файла
  var KEY_MANUAL = 'nml_production_keys';

  var videoInput = document.getElementById('nml-video-dir');
  var jsonsInput = document.getElementById('nml-jsons-dir');
  var recursiveCb = document.getElementById('nml-recursive');
  var filterInput = document.getElementById('nml-filter');
  var listHost = document.getElementById('nml-list');
  var statusHost = document.getElementById('nml-status');

  var entries = [];        // видео текущего каталога (ответ API + состояние карточки)
  var jsonsDir = '';       // каталог JSON, с которым получен список
  var lastListing = null;  // последний ответ списка (для строки статуса)
  var loadSeq = 0;

  function store(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* хранилище недоступно */ } }
  function restore(key) { try { return localStorage.getItem(key) || ''; } catch (e) { return ''; } }
  function manualKeys() { try { return JSON.parse(restore(KEY_MANUAL) || '{}') || {}; } catch (e) { return {}; } }
  function manualKey(v) { return manualKeys()[jsonsDir + '\n' + v.path] || null; }
  function setManualKey(v, key) {
    var all = manualKeys(), id = jsonsDir + '\n' + v.path;
    if (key) all[id] = key; else delete all[id];
    store(KEY_MANUAL, JSON.stringify(all));
  }

  // ------------------------------------------------------------------ каталоги
  function saveInputs() {
    store(KEY_VIDEO_DIR, videoInput.value.trim());
    store(KEY_JSONS_DIR, jsonsInput.value.trim());
    store(KEY_RECURSIVE, recursiveCb.checked ? '1' : '0');
  }
  function pickFolder(input) {
    C.toast('Открываю выбор каталога…');
    C.postJson('api/pick', { kind: 'dir', initial: input.value.trim() }).then(function (d) {
      if (d.path) { input.value = d.path; saveInputs(); load(); } else C.toast('Каталог не выбран.');
    }).catch(function (err) { C.toast('Выбор каталога недоступен: ' + err.message, true); });
  }

  // ------------------------------------------------------------------ список
  function load() {
    var path = videoInput.value.trim();
    if (!path) { entries = []; render(); statusHost.textContent = 'Укажите каталог видео.'; return; }
    var seq = ++loadSeq;
    statusHost.textContent = 'Загрузка…';
    C.getJson('api/videos', { path: path, recursive: recursiveCb.checked ? 1 : '', jsons: jsonsInput.value.trim() })
      .then(function (d) {
        if (seq !== loadSeq) return;
        jsonsDir = d.jsons_dir || '';
        lastListing = d;
        entries = (d.videos || []).map(function (v) { v.cardVariant = v.default_variant; v.open = false; return v; });
        renderStatus(d);
        render();
        applyManualKeys(seq);
      }).catch(function (err) {
        if (seq !== loadSeq) return;
        entries = [];
        render();
        statusHost.innerHTML = '<span class="nml-error-text">' + esc(err.message) + '</span>';
      });
  }
  // Боевая, выбранная вручную, — уточнить у сервера (файл мог исчезнуть) и обновить шапки
  function applyManualKeys(seq) {
    entries.forEach(function (v) {
      var key = manualKey(v);
      if (!key) return;
      C.getJson('api/locations', { video: v.path, jsons: jsonsDir, key: key }).then(function (d) {
        if (seq !== loadSeq) return;
        updateEntry(v, d);
      }).catch(function (err) { C.toast(v.name + ': ' + err.message, true); });
    });
  }
  function updateEntry(v, entry) {
    v.sidecar = entry.sidecar; v.production = entry.production;
    if (!v.cardVariant || !(v[v.cardVariant] || {}).exists) v.cardVariant = v.sidecar.exists ? 'sidecar' : (v.production.exists ? 'production' : null);
    if (lastListing) renderStatus(lastListing);
    var card = cardOf(v);
    if (card) card.querySelector('.nml-video-head').outerHTML = headHtml(v);
  }
  function renderStatus(d) {
    var parts = ['Видео: ' + entries.length];
    var withSidecar = entries.filter(function (v) { return v.sidecar.exists; }).length;
    var withProduction = entries.filter(function (v) { return v.production.exists; }).length;
    parts.push('рядом с видео: ' + withSidecar, 'боевых: ' + withProduction);
    var html = esc(parts.join(' · '));
    if (d.jsons_error) html += ' · <span class="nml-error-text">' + esc(d.jsons_error) + '</span>';
    else if (!d.jsons_dir) html += ' · <span class="nml-warn-text">каталог JSON не задан — боевая разметка недоступна</span>';
    if ((d.warnings || []).length) html += ' · <span class="nml-warn-text" title="' + esc(d.warnings.join('\n')) + '">⚠ предупреждений: ' + d.warnings.length + '</span>';
    statusHost.innerHTML = html;
  }
  function matchesFilter(v) {
    var f = filterInput.value.trim().toLowerCase();
    return !f || (v.relative_dir + '/' + v.name).toLowerCase().indexOf(f) >= 0;
  }
  function render() {
    var visible = entries.filter(matchesFilter);
    if (!visible.length) { listHost.innerHTML = entries.length ? '<div class="muted">Ничего не найдено.</div>' : ''; return; }
    var grouped = visible.some(function (v) { return v.relative_dir; }), lastDir = null, html = '';
    visible.forEach(function (v) {
      if (grouped && v.relative_dir !== lastDir) {
        lastDir = v.relative_dir;
        html += '<div class="nml-group-h">' + esc(v.relative_dir || '(корень каталога)') + '</div>';
      }
      html += '<div class="nml-video' + (v.open ? ' open' : '') + '" data-path="' + esc(v.path) + '">' + headHtml(v) + '<div class="nml-video-body-host"></div></div>';
    });
    listHost.innerHTML = html;
    visible.forEach(function (v) { if (v.open) renderBody(v); });
  }
  // Подпись видео: производство (если известно) и ключ боевой разметки
  function camText(v) {
    var parts = [];
    if (v.factory) parts.push(v.factory);
    parts.push(v.production.key || 'боевая не подобрана');
    return parts.join(' · ');
  }
  function badge(loc, text) {
    return '<span class="nml-badge' + (loc.exists ? ' on' : '') + '" title="' + esc(loc.exists ? loc.path : (loc.reason || 'Файла нет')) + '">'
      + (loc.exists ? '✓ ' : '— ') + esc(text) + '</span>';
  }
  function headHtml(v) {
    return '<div class="nml-video-head" data-toggle>'
      + '<span class="nml-caret">▸</span>'
      + '<span class="nml-video-name" title="' + esc(v.path) + '">' + esc(v.name) + '</span>'
      + '<span class="nml-video-cam">' + esc(camText(v)) + '</span>'
      + badge(v.sidecar, 'рядом с видео') + badge(v.production, 'боевой')
      + '</div>';
  }
  function entryByPath(path) {
    for (var i = 0; i < entries.length; i++) if (entries[i].path === path) return entries[i];
    return null;
  }
  function cardOf(v) { return listHost.querySelector('.nml-video[data-path="' + CSS.escape(v.path) + '"]'); }
  function renderBody(v) {
    var card = cardOf(v);
    if (!card) return;
    var host = card.querySelector('.nml-video-body-host');
    if (v.frame) v.frame.destroy();
    host.innerHTML = '<div class="nml-video-body"></div>';
    v.frame = NML.frame.mount(host.firstChild, {
      video: v.path, jsonsDir: jsonsDir, productionKey: manualKey(v), variant: v.cardVariant,
      entry: { sidecar: v.sidecar, production: v.production, factory: v.factory }, details: true,
      onEntry: function (entry) { updateEntry(v, entry); },
      onVariant: function (variant) { v.cardVariant = variant; },
      onProductionKey: function (key) { setManualKey(v, key); },
    });
  }
  function closeBody(v) {
    if (v.frame) { v.frame.destroy(); v.frame = null; }
    var card = cardOf(v);
    if (card) card.querySelector('.nml-video-body-host').innerHTML = '';
  }

  // ------------------------------------------------------------------ события
  listHost.addEventListener('click', function (e) {
    var card = e.target.closest('.nml-video');
    if (!card) return;
    var v = entryByPath(card.getAttribute('data-path'));
    if (!v) return;
    if (e.target.closest('[data-toggle]')) {
      v.open = !v.open;
      card.classList.toggle('open', v.open);
      if (v.open) renderBody(v); else closeBody(v);
    }
  });
  document.querySelectorAll('[data-pick]').forEach(function (b) {
    b.addEventListener('click', function () { pickFolder(document.getElementById(b.getAttribute('data-pick'))); });
  });
  [videoInput, jsonsInput].forEach(function (input) {
    input.addEventListener('change', function () { saveInputs(); load(); });
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); input.blur(); } });
  });
  recursiveCb.addEventListener('change', function () { saveInputs(); load(); });
  filterInput.addEventListener('input', render);

  videoInput.value = restore(KEY_VIDEO_DIR);
  jsonsInput.value = restore(KEY_JSONS_DIR);
  recursiveCb.checked = restore(KEY_RECURSIVE) === '1';
  load();
})();
