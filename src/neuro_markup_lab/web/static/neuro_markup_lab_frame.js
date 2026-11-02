// Кадр видео с разметкой — модуль для любой страницы (своей и чужой): первый кадр, разметка поверх,
// переключатель «Боевая | Рядом с видео», карандаш редактора и, по желанию, панель справа — файлы
// разметки (клик выбирает показываемый вариант; ссылка, копирование пути, выбор боевой вручную), содержимое
// разметки только для чтения (объекты с координатами и атрибутами, поля документа), «Открыть видео» и
// «Открыть редактор разметки».
//
//   var frame = NML.frame.mount(element, {
//     video: 'D:/video/line1_cam5.avi',  // путь к видео на компьютере сервера (обязательно)
//     jsonsDir: 'D:/markup',              // каталог боевых JSON; нет — только «рядом с видео»
//     productionKey: 'line1_cam5',        // боевая, выбранная вручную; нет — подбирается
//     variant: 'sidecar',                 // что показать; нет — «рядом с видео», если есть, иначе боевую
//     entry: { sidecar, production },     // уже известные файлы разметки; нет — запрашиваются
//     details: true,                      // панель справа от кадра
//     editable: true,                     // карандаш редактора
//     onProductionKey: function (key) {}, // боевая выбрана вручную (key) или сброшена (null)
//     onEntry: function (entry) {},       // обновились сведения о файлах разметки
//     onVariant: function (variant) {},   // сменился показываемый вариант
//     onSaved: function (variant, location) {},
//   });
//   frame.setVariant('production'); frame.refresh(); frame.destroy();
//
// Нужны neuro_markup_lab.css, _shapes.js и _editor.js (редактор открывается карандашом).
window.NML = window.NML || {};
NML.frame = (function () {
  var C = NML.common, esc = C.esc;
  // Адреса API по умолчанию (от корня редактора)
  var DEFAULT_URLS = { markup: 'api/markup', frame: 'frame', locations: 'api/locations' };
  var VARIANTS = ['sidecar', 'production'];
  // Ключи фигуры, которые не показываются среди атрибутов (геометрия выводится отдельно)
  var GEOMETRY_KEYS = { points: 1, shape_type: 1 };
  // Знаков после запятой в координатах
  var COORD_DIGITS = 2;
  var COPY_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="5" y="5" width="9" height="9" rx="1.5"/>'
    + '<path d="M11 5V3.5A1.5 1.5 0 0 0 9.5 2h-6A1.5 1.5 0 0 0 2 3.5v6A1.5 1.5 0 0 0 3.5 11H5"/></svg>';

  function defaultVariant(entry) {
    if (entry.sidecar && entry.sidecar.exists) return 'sidecar';
    if (entry.production && entry.production.exists) return 'production';
    return null;
  }
  function plural(n, one, few, many) {
    var m10 = n % 10, m100 = n % 100;
    if (m10 === 1 && m100 !== 11) return one;
    if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
    return many;
  }
  function coord(v) { return typeof v === 'number' ? String(Number(v.toFixed(COORD_DIGITS))) : esc(String(v)); }
  function valueHtml(v) {
    if (v === null || v === undefined) return '<span class="nml-null">null</span>';
    if (typeof v === 'boolean') return '<span class="nml-bool">' + v + '</span>';
    if (typeof v === 'object') return '<code>' + esc(JSON.stringify(v)) + '</code>';
    if (v === '') return '<span class="nml-null">""</span>';
    return esc(String(v));
  }
  // Копирование в буфер: сначала navigator.clipboard (нужен защищённый контекст и разрешение),
  // при отказе — через скрытое поле и execCommand
  function copyByCommand(text) {
    var area = document.createElement('textarea');
    area.value = text; area.setAttribute('readonly', ''); area.style.position = 'fixed'; area.style.opacity = '0';
    document.body.appendChild(area); area.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    area.remove();
    return ok ? Promise.resolve() : Promise.reject(new Error('clipboard is not available'));
  }
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(function () { return copyByCommand(text); });
    }
    return copyByCommand(text);
  }

  function mount(host, options) {
    var o = Object.assign({ details: false, editable: true }, options || {});
    var urls = Object.assign({}, DEFAULT_URLS, o.urls || {});
    var jsonsDir = o.jsonsDir || '';
    var state = { entry: o.entry || null, variant: o.variant || null, key: o.productionKey || null,
                  cache: {}, doc: null, error: '', seq: 0, alive: true };

    host.classList.add('nml-frame');
    host.innerHTML = '<div class="nml-frame-view"><div class="nml-preview">'
      + '<img alt="" src="' + esc(C.frameUrl(o.video, false, urls.frame)) + '">'
      + '<div class="nml-variant-switch"></div>'
      + (o.editable ? '<button type="button" class="nml-preview-edit" title="Редактировать разметку">✎</button>' : '')
      + '</div></div>'
      + (o.details ? '<aside class="nml-frame-info"></aside>' : '');
    var box = host.querySelector('.nml-preview');
    var img = box.querySelector('img');
    var switchHost = box.querySelector('.nml-variant-switch');
    var editBtn = box.querySelector('.nml-preview-edit');
    var info = host.querySelector('.nml-frame-info');
    img.onerror = function () {
      img.remove();
      box.insertAdjacentHTML('afterbegin', '<div class="nml-preview-ph">Кадр не прочитан</div>');
    };

    // ---- данные
    function query(extra) { return Object.assign({ video: o.video, jsons: jsonsDir, key: state.key || '' }, extra || {}); }
    function loadEntry(extra) {
      return C.getJson(urls.locations, query(extra)).then(function (d) {
        state.entry = { sidecar: d.sidecar, production: d.production, factory: d.factory };
        state.cache = {};
        if (!state.variant || !(state.entry[state.variant] || {}).exists) state.variant = defaultVariant(state.entry);
        if (o.onEntry) o.onEntry(state.entry);
      });
    }
    function loadDoc() {
      var variant = state.variant, seq = ++state.seq;
      state.doc = null; state.error = '';
      if (!variant) { render(); return; }
      var promise = state.cache[variant] || (state.cache[variant] = C.getJson(urls.markup, query({ variant: variant })));
      promise.then(function (doc) {
        if (seq !== state.seq || !state.alive) return;
        state.doc = doc;
        render();
      }).catch(function (err) {
        delete state.cache[variant];
        if (seq !== state.seq || !state.alive) return;
        state.error = err.message;
        render();
      });
      render();
    }

    // ---- кадр
    function buildOverlay(doc) {
      var w = doc.image_width, h = doc.image_height;
      if (!w || !h) return null;
      var svg = document.createElementNS(C.SVGNS, 'svg');
      svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
      svg.setAttribute('preserveAspectRatio', 'none');
      svg.setAttribute('class', 'nml-preview-svg');
      (doc.shapes || []).forEach(function (s) {
        if (!(s.points || []).length) return;
        var geom = C.createGeom(s.shape_type, s.points, 'nml-preview-shape' + (C.isVisible(s.attributes) ? '' : ' nml-preview-shape-hidden'));
        geom.setAttribute('data-index', s.index);
        svg.appendChild(geom);
      });
      return svg;
    }
    function render() {
      if (!state.alive || !state.entry) return;
      C.renderSwitch(switchHost, state.entry, state.variant, setVariant);
      if (editBtn) {
        editBtn.disabled = !state.variant;
        editBtn.title = state.variant ? 'Редактировать разметку' : 'Нет ни JSON рядом с видео, ни боевого JSON';
      }
      var old = box.querySelector('.nml-preview-svg');
      if (old) old.remove();
      var svg = state.doc ? buildOverlay(state.doc) : null;
      if (svg) box.insertBefore(svg, switchHost);
      if (info) renderInfo();
    }
    function highlight(index) {
      box.querySelectorAll('.nml-preview-shape.hl').forEach(function (el) { el.classList.remove('hl'); });
      if (index == null) return;
      var el = box.querySelector('.nml-preview-shape[data-index="' + index + '"]');
      if (el) el.classList.add('hl');
    }

    // ---- панель
    // Карточка файла разметки: клик по карточке показывает этот вариант; ссылка открывает файл
    function fileCard(variant) {
      var loc = state.entry[variant] || {};
      var active = variant === state.variant;
      var path = loc.exists
        ? '<button type="button" class="nml-icon-btn" data-copy="' + esc(loc.path) + '" title="Копировать путь">' + COPY_ICON + '</button>'
          + '<a href="#" class="nml-link" data-open-variant="' + variant + '" title="Открыть в программе по умолчанию">' + esc(loc.path) + '</a>'
        : '<span class="muted">' + esc(loc.path ? 'нет файла ' + loc.name : (loc.reason || '—')) + '</span>';
      var actions = '';
      if (variant === 'production' && jsonsDir) {
        actions = '<span class="nml-info-actions">'
          + (loc.manual ? '<button type="button" class="nml-btn nml-btn-small" data-auto-production title="Вернуть подбор по каталогу">Подбирать автоматически</button>' : '')
          + '<button type="button" class="nml-btn nml-btn-small" data-choose-production>Выбрать файл…</button></span>';
      }
      var selectable = loc.exists && !active;
      return '<div class="nml-info-file' + (active ? ' active' : '') + (loc.exists ? '' : ' missing') + (selectable ? ' selectable' : '') + '"'
        + (selectable ? ' data-select-variant="' + variant + '" title="Показать эту разметку"' : '') + '>'
        + '<div class="nml-info-file-head"><b>' + esc(C.VARIANT_LABELS[variant]) + '</b>'
        + (loc.manual ? '<span class="nml-tag">выбрана вручную</span>' : '')
        + (active ? '<span class="nml-tag nml-tag-active">выбрано</span>' : '') + '</div>'
        + '<div class="nml-info-row"><div class="nml-info-path">' + path + '</div>' + actions + '</div></div>';
    }
    function summaryHtml(doc) {
      var shapes = doc.shapes || [];
      var chips = [shapes.length + ' ' + plural(shapes.length, 'объект', 'объекта', 'объектов')];
      if (doc.image_width && doc.image_height) chips.push('кадр ' + doc.image_width + '×' + doc.image_height);
      if (doc.version) chips.push('LabelMe ' + doc.version);
      var report = doc.report || {}, conv = (report.conversions || []).length, probs = (report.problems || []).length;
      var check = !conv && !probs ? '<span class="nml-chip nml-chip-ok">типы полей в порядке</span>'
        : (probs ? '<span class="nml-chip nml-chip-error">' + probs + ' ' + plural(probs, 'значение', 'значения', 'значений') + ' не привести</span>' : '')
          + (conv ? '<span class="nml-chip nml-chip-warn">' + conv + ' ' + plural(conv, 'значение', 'значения', 'значений') + ' будет приведено</span>' : '');
      return '<div class="nml-chips">' + chips.map(function (c) { return '<span class="nml-chip">' + esc(c) + '</span>'; }).join('') + check + '</div>';
    }
    function shapeCard(s, known) {
      var attrs = s.attributes || {};
      var label = attrs.label == null || attrs.label === '' ? '(без метки)' : String(attrs.label);
      var points = s.points || [];
      var names = Object.keys(attrs).filter(function (k) { return k !== 'label' && !GEOMETRY_KEYS[k] && !(known[k] && known[k].hidden); });
      var order = Object.keys(known);
      names.sort(function (a, b) {
        var ia = order.indexOf(a), ib = order.indexOf(b);
        return (ia < 0 ? 1e6 : ia) - (ib < 0 ? 1e6 : ib) || (a < b ? -1 : a > b ? 1 : 0);
      });
      var coords = points.map(function (p, i) {
        return '<span class="nml-pt"><i>P' + (i + 1) + '</i>' + coord(p[0]) + ', ' + coord(p[1]) + '</span>';
      }).join('');
      var rows = names.map(function (k) {
        var title = known[k] && known[k].title ? ' title="' + esc(known[k].title + (known[k].hint ? ' — ' + known[k].hint : '')) + '"' : '';
        return '<div class="nml-attr"><span' + title + '>' + esc(k) + '</span><div>' + valueHtml(attrs[k]) + '</div></div>';
      }).join('');
      var hidden = C.isVisible(attrs) ? '' : '<span class="nml-tag" title="show: false — не рисуется">скрыт</span>';
      return '<div class="nml-obj" data-index="' + s.index + '">'
        + '<div class="nml-obj-head"><span class="nml-obj-n">#' + s.index + '</span><b>' + esc(label) + '</b>'
        + '<span class="muted">' + esc(s.shape_type || '—') + ' · ' + points.length + ' ' + plural(points.length, 'точка', 'точки', 'точек') + '</span>' + hidden + '</div>'
        + '<div class="nml-pts">' + (coords || '<span class="muted">точек нет</span>') + '</div>'
        + (rows ? '<div class="nml-attrs">' + rows + '</div>' : '')
        + '</div>';
    }
    function docFieldsHtml(doc) {
      var fields = (doc.schema && doc.schema.document) || [];
      if (!fields.length) return '<div class="muted">Своих полей нет.</div>';
      return '<div class="nml-attrs">' + fields.map(function (f) {
        return '<div class="nml-attr"><span' + (f.hint ? ' title="' + esc(f.hint) + '"' : '') + '>' + esc(f.name) + '</span>'
          + '<div><code>' + esc(f.type + (f.nullable ? ' | null' : '')) + '</code></div></div>';
      }).join('') + '</div>';
    }
    function contentHtml() {
      if (!state.variant) return '<div class="muted">Разметки нет: ни рядом с видео, ни боевой.</div>';
      if (state.error) return '<div class="nml-error-text">Разметка не открыта: ' + esc(state.error) + '</div>';
      var doc = state.doc;
      if (!doc) return '<div class="muted">Загрузка…</div>';
      var known = {};
      ((doc.schema && doc.schema.known) || []).forEach(function (s) { known[s.name] = s; });
      var shapes = doc.shapes || [];
      return summaryHtml(doc)
        + '<div class="nml-info-h">Объекты</div>'
        + (shapes.length ? '<div class="nml-objs">' + shapes.map(function (s) { return shapeCard(s, known); }).join('') + '</div>'
          : '<div class="muted">Объектов нет.</div>')
        + '<div class="nml-info-h">Поля документа</div>' + docFieldsHtml(doc);
    }
    function renderInfo() {
      info.innerHTML = '<section class="nml-info-sec"><div class="nml-info-h">Файлы разметки</div>'
        + '<div class="nml-info-files">' + VARIANTS.map(fileCard).join('') + '</div></section>'
        + '<section class="nml-info-sec">' + contentHtml() + '</section>'
        + '<div class="nml-info-foot"><button type="button" class="nml-btn" data-open-video title="Открыть видео в программе по умолчанию">Открыть видео</button>'
        + (o.editable ? '<button type="button" class="nml-btn nml-btn-primary" data-open-editor' + (state.variant ? '' : ' disabled') + '>Открыть редактор разметки</button>' : '')
        + '</div>';
    }

    // ---- действия
    function setVariant(variant) {
      if (!state.entry || !(state.entry[variant] || {}).exists || variant === state.variant) return;
      state.variant = variant;
      if (o.onVariant) o.onVariant(variant);
      loadDoc();
    }
    function chooseProduction() {
      C.postJson('api/pick', { kind: 'json', initial: jsonsDir }).then(function (d) {
        if (!d.path) { C.toast('Файл не выбран.'); return null; }
        return loadEntry({ production: d.path, key: '' }).then(function () {
          state.key = state.entry.production.key || null;
          state.variant = 'production';
          if (o.onProductionKey) o.onProductionKey(state.key);
          if (o.onVariant) o.onVariant(state.variant);
          loadDoc();
        });
      }).catch(function (err) { C.toast(err.message, true); });
    }
    function autoProduction() {
      state.key = null;
      loadEntry().then(function () {
        if (o.onProductionKey) o.onProductionKey(null);
        if (o.onVariant) o.onVariant(state.variant);
        loadDoc();
      }).catch(function (err) { C.toast(err.message, true); });
    }
    function openEditor() {
      if (!state.variant) return;
      NML.editor.open({
        video: o.video, jsonsDir: jsonsDir, productionKey: state.key, variant: state.variant, entry: state.entry,
        urls: o.editorUrls,
        onSaved: function (target, location) {
          state.entry[target] = location;
          state.cache = {};
          state.variant = target;
          if (o.onEntry) o.onEntry(state.entry);
          if (o.onVariant) o.onVariant(target);
          if (o.onSaved) o.onSaved(target, location);
          loadDoc();
        },
      });
    }
    function onClick(e) {
      var t = e.target;
      if (editBtn && t.closest('.nml-preview-edit')) { e.stopPropagation(); if (!editBtn.disabled) openEditor(); return; }
      var copy = t.closest('[data-copy]');
      if (copy) {
        e.stopPropagation();
        copyText(copy.getAttribute('data-copy')).then(function () { C.toast('Путь скопирован.'); })
          .catch(function () { C.toast('Не удалось скопировать путь.', true); });
        return;
      }
      var link = t.closest('[data-open-variant]');
      if (link) { e.preventDefault(); e.stopPropagation(); C.openFile(o.video, link.getAttribute('data-open-variant'), jsonsDir, state.key); return; }
      if (t.closest('[data-choose-production]')) { e.stopPropagation(); chooseProduction(); return; }
      if (t.closest('[data-auto-production]')) { e.stopPropagation(); autoProduction(); return; }
      if (t.closest('[data-open-editor]')) { e.stopPropagation(); openEditor(); return; }
      if (t.closest('[data-open-video]')) {
        e.stopPropagation();
        C.postJson('api/open-video', { video: o.video }).then(function (d) { C.toast('Открываю ' + d.path); })
          .catch(function (err) { C.toast('Не удалось открыть видео: ' + err.message, true); });
        return;
      }
      var card = t.closest('[data-select-variant]');
      if (card) { e.stopPropagation(); setVariant(card.getAttribute('data-select-variant')); }
    }
    function onOver(e) {
      var obj = e.target.closest && e.target.closest('.nml-obj');
      highlight(obj ? obj.getAttribute('data-index') : null);
    }
    host.addEventListener('click', onClick);
    if (info) { info.addEventListener('mouseover', onOver); info.addEventListener('mouseleave', function () { highlight(null); }); }

    function refresh() {
      return loadEntry().then(loadDoc).catch(function (err) {
        state.entry = state.entry || { sidecar: {}, production: {} };
        state.error = err.message;
        render();
      });
    }
    if (state.entry) {
      if (!state.variant) state.variant = defaultVariant(state.entry);
      loadDoc();
    } else {
      refresh();
    }

    return {
      refresh: refresh,
      setVariant: setVariant,
      destroy: function () { state.alive = false; host.removeEventListener('click', onClick); host.innerHTML = ''; host.classList.remove('nml-frame'); },
      get variant() { return state.variant; },
      get entry() { return state.entry; },
      get productionKey() { return state.key; },
    };
  }

  return { mount: mount, copyText: copyText };
})();
