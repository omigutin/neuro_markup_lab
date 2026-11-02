// Страница NeuroMarkupLab: каталог видео и каталог боевых JSON (помнит браузер), список
// видео с раскрывающейся карточкой: ссылки на JSON (открываются программой по умолчанию), первый
// кадр с разметкой, поверх кадра — переключатель «Боевая | Рядом с видео» и карандаш редактора.
// Только представление: данные — из API страницы.
(function () {
  var C = NML.common, esc = C.esc;
  // Ключи localStorage: каталог видео, «в подкаталогах», каталог JSON
  var KEY_VIDEO_DIR = 'nml_video_dir', KEY_RECURSIVE = 'nml_recursive', KEY_JSONS_DIR = 'nml_jsons_dir';
  var NO_MARKUP_TITLE = 'Нет ни JSON рядом с видео, ни боевого JSON';

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

  // ------------------------------------------------------------------ каталоги
  function saveInputs() {
    store(KEY_VIDEO_DIR, videoInput.value.trim());
    store(KEY_JSONS_DIR, jsonsInput.value.trim());
    store(KEY_RECURSIVE, recursiveCb.checked ? '1' : '0');
  }
  function pickFolder(input) {
    C.toast('Открываю выбор каталога…');
    C.postJson('api/pick', { initial: input.value.trim() }).then(function (d) {
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
        entries = (d.videos || []).map(function (v) { v.cardVariant = v.default_variant; v.cache = {}; v.open = false; return v; });
        renderStatus(d);
        render();
      }).catch(function (err) {
        if (seq !== loadSeq) return;
        entries = [];
        render();
        statusHost.innerHTML = '<span class="nml-error-text">' + esc(err.message) + '</span>';
      });
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
  function camText(v) {
    if (v.factory && v.cam_id) return v.factory + ' · cam ' + v.cam_id;
    return 'камера не определена';
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
  // Путь JSON: есть файл — ссылка (открыть программой по умолчанию), нет — пояснение
  function locationLink(variant, loc) {
    var value = loc.exists
      ? '<a href="#" class="nml-link" data-open-variant="' + variant + '" title="Открыть в программе по умолчанию">' + esc(loc.path) + '</a>'
      : '<span class="muted">' + esc(loc.path ? 'нет файла ' + loc.name : (loc.reason || '—')) + '</span>';
    return '<div><span class="muted">' + esc(C.VARIANT_LABELS[variant]) + ':</span>' + value + '</div>';
  }
  function renderBody(v) {
    var card = cardOf(v);
    if (!card) return;
    var host = card.querySelector('.nml-video-body-host');
    var canEdit = !!v.cardVariant;
    host.innerHTML = '<div class="nml-video-body">'
      + '<div class="nml-links">' + locationLink('sidecar', v.sidecar) + locationLink('production', v.production) + '</div>'
      + '<div class="nml-preview"><img alt="" src="' + esc(C.frameUrl(v.path, false)) + '">'
      + '<div class="nml-variant-switch"></div>'
      + '<button type="button" class="nml-preview-edit" data-edit title="' + (canEdit ? 'Редактировать разметку' : NO_MARKUP_TITLE) + '"'
      + (canEdit ? '' : ' disabled') + '>✎</button></div>'
      + '</div>';
    var img = host.querySelector('img');
    img.onerror = function () { host.querySelector('.nml-preview').innerHTML = '<div class="nml-preview-ph">Кадр не прочитан</div>'; };
    C.renderSwitch(host.querySelector('.nml-variant-switch'), v, v.cardVariant, function (variant) {
      v.cardVariant = variant;
      renderBody(v);
    });
    if (v.cardVariant) drawOverlay(v, host.querySelector('.nml-preview'));
  }
  function drawOverlay(v, box) {
    var variant = v.cardVariant;
    var promise = v.cache[variant] || (v.cache[variant] = C.getJson('api/markup', { video: v.path, variant: variant, jsons: jsonsDir }));
    promise.then(function (doc) {
      if (v.cardVariant !== variant || !box.isConnected) return;
      var old = box.querySelector('.nml-preview-svg');
      if (old) old.parentNode.removeChild(old);
      var svg = C.buildOverlay(doc);
      if (svg) box.insertBefore(svg, box.querySelector('.nml-variant-switch'));
    }).catch(function (err) {
      delete v.cache[variant];
      C.toast('Разметка не открыта: ' + err.message, true);
    });
  }
  function openEditor(v) {
    var variant = v.cardVariant || v.default_variant;
    if (!variant) return;
    NML.editor.open({
      video: v.path, videoName: v.name, jsonsDir: jsonsDir, variant: variant,
      entry: { sidecar: v.sidecar, production: v.production },
      onSaved: function (target, location) {
        v[target] = location;
        v.cache = {};
        v.cardVariant = target;
        if (!v.default_variant) v.default_variant = target;
        if (lastListing) renderStatus(lastListing);
        var card = cardOf(v);
        if (card) {
          var head = card.querySelector('.nml-video-head');
          head.outerHTML = headHtml(v);
          if (v.open) renderBody(v);
        }
      },
    });
  }

  // ------------------------------------------------------------------ события
  listHost.addEventListener('click', function (e) {
    var card = e.target.closest('.nml-video');
    if (!card) return;
    var v = entryByPath(card.getAttribute('data-path'));
    if (!v) return;
    if (e.target.closest('[data-edit]')) { e.stopPropagation(); if (!e.target.closest('[data-edit]').disabled) openEditor(v); return; }
    var link = e.target.closest('[data-open-variant]');
    if (link) { e.preventDefault(); C.openFile(v.path, link.getAttribute('data-open-variant'), jsonsDir); return; }
    if (e.target.closest('[data-toggle]')) {
      v.open = !v.open;
      card.classList.toggle('open', v.open);
      if (v.open) renderBody(v); else card.querySelector('.nml-video-body-host').innerHTML = '';
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
