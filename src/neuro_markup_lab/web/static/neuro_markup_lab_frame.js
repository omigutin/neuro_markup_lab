// Кадр видео с разметкой — модуль для любой страницы (своей и чужой): первый кадр, разметка поверх,
// переключатель «Боевая | Рядом с видео», карандаш редактора и, по желанию, панель справа — файлы
// разметки (клик выбирает показываемый вариант; ссылка, копирование пути, выбор боевой вручную), содержимое
// разметки только для чтения (объекты с координатами и атрибутами, поля документа), «Открыть видео» и
// «Открыть редактор».
//
//   var frame = NML.frame.mount(element, {
//     video: 'D:/video/line1_cam5.avi',  // путь к видео на компьютере сервера (обязательно)
//     jsonsDir: 'D:/markup',              // каталог боевых JSON; нет — только «рядом с видео»
//     productionKey: 'line1_cam5',        // боевая, выбранная вручную; нет — подбирается
//     variant: 'sidecar',                 // что показать; нет — «рядом с видео», если есть, иначе боевую
//     version: 3,                         // версия разметки рядом с видео для показа; нет — текущая
//     locked: true,                       // только этот вариант (и версия): переключатель, выбор версии
//                                         // и выбор боевой отключены — например, для уже сделанного прогона
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
  var DEFAULT_URLS = { markup: 'api/markup', frame: 'frame', locations: 'api/locations', versions: 'api/versions',
                       versionCurrent: 'api/versions/current' };
  var VARIANTS = ['sidecar', 'production'];
  // Ключи фигуры, которые не показываются среди атрибутов (геометрия выводится отдельно)
  var GEOMETRY_KEYS = { points: 1, shape_type: 1 };
  // Знаков после запятой в координатах
  var COORD_DIGITS = 2;
  var VERSIONS_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8l8-4 8 4-8 4z"/><path d="M4 12l8 4 8-4"/><path d="M4 16l8 4 8-4"/></svg>';
  var FOLDER_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true">'
    + '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>';
  // Значение show, когда в фигуре его нет: фигура видна
  var SHOW_DEFAULT_HINT = 'не задано в файле — по умолчанию видна';

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
                  version: o.version != null ? o.version : null, versions: null, cache: {}, doc: null, error: '', seq: 0, alive: true };

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
        // Заданный вариант при locked не подменяется: показывается то, что передали, или ошибка
        if (!state.variant || (!o.locked && !(state.entry[state.variant] || {}).exists)) state.variant = defaultVariant(state.entry);
        if (o.onEntry) o.onEntry(state.entry);
      });
    }
    // Версии разметки рядом с видео — для выбора в панели
    function loadVersions() {
      if (!state.entry || !(state.entry.sidecar || {}).exists) { state.versions = null; return Promise.resolve(); }
      return C.getJson(urls.versions, { video: o.video }).then(function (d) { state.versions = d; render(); })
        .catch(function () { state.versions = null; });
    }
    function loadDoc() {
      var variant = state.variant, seq = ++state.seq;
      var version = variant === 'sidecar' ? state.version : null;
      var cacheKey = variant + (version != null ? ':v' + version : '');
      state.doc = null; state.error = '';
      if (!variant) { render(); return; }
      var promise = state.cache[cacheKey] || (state.cache[cacheKey] = C.getJson(urls.markup,
        query({ variant: variant, version: version == null ? '' : version })));
      promise.then(function (doc) {
        if (seq !== state.seq || !state.alive) return;
        state.doc = doc;
        render();
      }).catch(function (err) {
        delete state.cache[cacheKey];
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
      if (o.locked) renderLockedSwitch();
      else { C.renderSwitch(switchHost, state.entry, state.variant, setVariant); renderVersionSwitch(); }
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
    // Карточка файла разметки (цвет варианта): клик по карточке показывает этот вариант; ссылка открывает файл;
    // у боевой справа — выбор другого файла
    function fileCard(variant) {
      var loc = state.entry[variant] || {};
      var active = variant === state.variant;
      // У разметки рядом с видео — путь к файлу текущей версии
      var shown = variant === 'sidecar' && loc.exists ? sidecarPath() : { path: loc.path, version: null };
      var path = loc.exists
        ? '<a href="#" class="nml-link" data-open-variant="' + variant + '"' + (shown.version != null ? ' data-open-version="' + shown.version + '"' : '')
          + ' title="Открыть в программе по умолчанию">' + esc(shown.path) + '</a>'
        : '<span class="muted">' + esc(loc.path ? 'нет файла ' + loc.name : (loc.reason || '—')) + '</span>';
      var choose = '';
      if (o.locked) {
        choose = '';
      } else if (variant === 'production' && jsonsDir) {
        choose = '<button type="button" class="nml-info-open" data-choose-production title="Открыть другой файл боевой разметки для этого видео…">' + FOLDER_ICON + '</button>';
      } else if (variant === 'sidecar' && loc.exists) {
        choose = '<button type="button" class="nml-info-open" data-vsel data-vsel-toggle="card" title="' + esc(versionTitle()) + '">'
          + '<span class="nml-info-open-ver">' + versionLabel() + '</span>' + VERSIONS_ICON + '</button>'
          + (state.versionsOpen === 'card' ? versionsListHtml('card') : '');
      }
      var auto = variant === 'production' && jsonsDir && loc.manual && !o.locked
        ? '<button type="button" class="nml-btn nml-btn-small" data-auto-production title="Вернуть подбор по каталогу">Подбирать автоматически</button>' : '';
      var selectable = loc.exists && !active && !o.locked;
      return '<div class="nml-info-file nml-v-' + variant + (active ? ' active' : '') + (loc.exists ? '' : ' missing') + (selectable ? ' selectable' : '') + '"'
        + (selectable ? ' data-select-variant="' + variant + '" title="Показать эту разметку"' : '') + '>'
        + '<div class="nml-info-file-body">'
        + '<div class="nml-info-file-head"><b>' + esc(C.VARIANT_LABELS[variant]) + '</b>'
        + (loc.manual ? '<span class="nml-tag">выбрана вручную</span>' : '') + auto
        + '</div>'
        + '<div class="nml-info-path">' + path + '</div></div>' + choose + '</div>';
    }
    function fmtTime(iso) {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return iso || '';
      function two(n) { return (n < 10 ? '0' : '') + n; }
      return two(d.getDate()) + '.' + two(d.getMonth() + 1) + '.' + d.getFullYear() + ' ' + two(d.getHours()) + ':' + two(d.getMinutes());
    }
    // Версии разметки рядом с видео: на кадре — в переключателе «Боевая | Рядом с видео | vN ▾», в панели —
    // кнопка справа в карточке «Рядом с видео». Список: ★ (избранное), номер, время, комментарий; выбранная
    // версия сразу становится текущей — файл рядом с видео становится равен ей. Файл без истории версий — v1.
    function versionsList() {
      var h = state.versions;
      return h && (h.versions || []).length ? h.versions.slice().reverse() : [];
    }
    // Файл рядом с видео изменён вне версий: текущей версии ему нет
    function outsideVersions() { return !!(state.versions && versionsList().length && !state.versions.working_matches); }
    // Текущая версия рядом с видео: {number, version|null}; null — изменён вне версий
    function currentVersion() {
      var list = versionsList();
      if (!list.length) return { number: 1, version: null };
      if (outsideVersions()) return null;
      var n = state.versions.current;
      return { number: n, version: list.filter(function (v) { return v.number === n; })[0] || null };
    }
    // Путь к файлу текущей версии (в папке версий); нет истории или изменён вне версий — файл рядом с видео
    function sidecarPath() {
      var loc = state.entry.sidecar || {}, cur = currentVersion();
      if (!cur || !cur.version || !state.versions.directory) return { path: loc.path, version: null };
      var sep = String(loc.path || state.versions.directory).indexOf('\\') >= 0 ? '\\' : '/';
      return { path: state.versions.directory + sep + cur.version.file, version: cur.number };
    }
    function versionLabel() {
      var cur = currentVersion();
      return cur ? 'v' + cur.number : 'вне версий';
    }
    function versionTitle() {
      var cur = currentVersion();
      if (!cur) return 'Файл изменён вне версий. Выбрать версию';
      if (!cur.version) return 'v1 — единственная версия';
      return 'v' + cur.number + (cur.version.comment ? ' — ' + cur.version.comment : '') + '. Выбрать версию';
    }
    function versionsListHtml(where) {
      var list = versionsList();
      var rows = list.length ? list.map(function (v) {
        return '<div class="nml-vsel-row" data-version-pick="' + v.number + '" title="Сделать текущей">'
          + '<span class="nml-vsel-star' + (v.pinned ? ' on' : '') + '" title="' + (v.pinned ? 'В избранном' : '') + '">★</span>'
          + '<span class="nml-vsel-n">v' + v.number + '</span>'
          + '<span class="nml-vsel-d">' + esc(fmtTime(v.updated)) + '</span>'
          + '<span class="nml-vsel-c" title="' + esc(v.comment || '') + '">' + esc(v.comment || '') + '</span></div>';
      }).join('') : '<div class="nml-vsel-row nml-vsel-single"><span class="nml-vsel-star">★</span><span class="nml-vsel-n">v1</span>'
        + '<span class="nml-vsel-d"></span><span class="nml-vsel-c muted">единственная версия</span></div>';
      return '<div class="nml-vsel-list nml-vsel-' + where + '" data-vsel>' + rows + '</div>';
    }
    function sidecarShown() { return state.variant === 'sidecar' && (state.entry.sidecar || {}).exists; }
    // locked: на кадре только показываемый вариант (и версия) — без переключения
    function renderLockedSwitch() {
      var v = state.variant;
      if (!v) { switchHost.innerHTML = ''; return; }
      var loc = state.entry[v] || {};
      var ver = v === 'sidecar' ? (state.version != null ? 'v' + state.version : versionLabel()) : '';
      switchHost.innerHTML = '<span class="nml-locked nml-v-' + v + '" title="' + esc(loc.path || loc.name || loc.reason || '') + '">'
        + esc(C.VARIANT_LABELS[v]) + (ver ? ' · ' + esc(ver) : '') + '</span>';
    }
    function renderVersionSwitch() {
      var old = box.querySelector('.nml-vsel-list');
      if (old) old.remove();
      if (!sidecarShown()) return;
      switchHost.insertAdjacentHTML('beforeend', '<button type="button" class="nml-ver-seg" data-vsel data-vsel-toggle="frame" title="'
        + esc(versionTitle()) + '">' + versionLabel() + ' ▾</button>');
      var seg = switchHost.querySelector('[data-vsel-toggle]');
      var prod = switchHost.querySelector('[data-variant="production"]');
      if (prod && prod.offsetWidth) seg.style.minWidth = prod.offsetWidth + 'px';
      if (state.versionsOpen === 'frame') box.insertAdjacentHTML('beforeend', versionsListHtml('frame'));
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
      // show выводится всегда: без него в файле фигура видна
      var showMissing = !('show' in attrs) && !(known.show && known.show.hidden);
      if (showMissing) names.push('show');
      var order = Object.keys(known);
      names.sort(function (a, b) {
        var ia = order.indexOf(a), ib = order.indexOf(b);
        return (ia < 0 ? 1e6 : ia) - (ib < 0 ? 1e6 : ib) || (a < b ? -1 : a > b ? 1 : 0);
      });
      var coords = points.map(function (p, i) {
        return '<div class="nml-info-attr nml-info-pt"><span>P' + (i + 1) + '</span><div>' + coord(p[0]) + ', ' + coord(p[1]) + '</div></div>';
      }).join('');
      var rows = names.map(function (k) {
        var title = known[k] && known[k].title ? ' title="' + esc(known[k].title + (known[k].hint ? ' — ' + known[k].hint : '')) + '"' : '';
        var value = k === 'show' && showMissing
          ? '<span class="nml-default" title="' + SHOW_DEFAULT_HINT + '">true</span>' : valueHtml(attrs[k]);
        return '<div class="nml-info-attr"><span' + title + '>' + esc(k) + '</span><div>' + value + '</div></div>';
      }).join('');
      var hidden = !C.isVisible(attrs);
      return '<div class="nml-obj' + (hidden ? ' nml-obj-hidden' : '') + '" data-index="' + s.index + '"'
        + (hidden ? ' title="show: false — фигура не рисуется"' : '') + '>'
        + '<div class="nml-obj-head"><span class="nml-obj-n">#' + s.index + '</span><b>' + esc(label) + '</b>'
        + '<span class="muted">' + esc(s.shape_type || '—') + '</span></div>'
        + '<div class="nml-info-attrs">' + (coords || '<div class="nml-info-attr"><span>точки</span><div class="muted">нет</div></div>')
        + (rows ? '<div class="nml-info-sep"></div>' + rows : '') + '</div>'
        + '</div>';
    }
    function docFieldsHtml(doc) {
      var fields = (doc.schema && doc.schema.document) || [];
      if (!fields.length) return '<div class="muted">Своих полей нет.</div>';
      return '<div class="nml-info-attrs">' + fields.map(function (f) {
        return '<div class="nml-info-attr"><span' + (f.hint ? ' title="' + esc(f.hint) + '"' : '') + '>' + esc(f.name) + '</span>'
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
        + '<section class="nml-info-sec nml-info-content">' + contentHtml() + '</section>'
        + '<div class="nml-info-foot"><button type="button" class="nml-btn" data-open-video title="Открыть видео в программе по умолчанию">Открыть видео</button>'
        + (o.editable ? '<button type="button" class="nml-btn nml-btn-dark" data-open-editor' + (state.variant ? '' : ' disabled') + ' title="Открыть редактор разметки">Открыть редактор</button>' : '')
        + '</div>';
    }

    // ---- действия
    function setVariant(variant) {
      if (o.locked) return;
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
        version: state.variant === 'sidecar' ? state.version : null, urls: o.editorUrls,
        onSaved: function (target, location) {
          state.entry[target] = location;
          state.cache = {};
          state.version = null;
          state.variant = target;
          loadVersions();
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
      var link = t.closest('[data-open-variant]');
      if (link) {
        e.preventDefault(); e.stopPropagation();
        var openVer = link.getAttribute('data-open-version');
        C.openFile(o.video, link.getAttribute('data-open-variant'), jsonsDir, state.key, openVer ? +openVer : null);
        return;
      }
      // locked: варианты, версии и боевая не меняются — остаются только ссылки и «Открыть видео»
      if (o.locked && t.closest('[data-choose-production], [data-auto-production], [data-vsel-toggle], [data-version-pick], [data-select-variant]')) {
        e.stopPropagation(); return;
      }
      if (t.closest('[data-choose-production]')) { e.stopPropagation(); chooseProduction(); return; }
      if (t.closest('[data-auto-production]')) { e.stopPropagation(); autoProduction(); return; }
      if (t.closest('[data-open-editor]')) { e.stopPropagation(); openEditor(); return; }
      var toggle = t.closest('[data-vsel-toggle]');
      if (toggle) {
        e.stopPropagation();
        var where = toggle.getAttribute('data-vsel-toggle');
        state.versionsOpen = state.versionsOpen === where ? false : where;
        render();
        return;
      }
      var pick = t.closest('[data-version-pick]');
      if (pick) {
        e.stopPropagation();
        var n = +pick.getAttribute('data-version-pick');
        state.versionsOpen = false;
        if (state.versions && n === state.versions.current && !outsideVersions()) {
          if (state.variant !== 'sidecar') setVariant('sidecar'); else render();
          return;
        }
        makeCurrent(n);
        return;
      }
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
    function makeCurrent(n) {
      C.postJson(urls.versionCurrent, { video: o.video, number: n }).then(function () {
        C.toast('Текущая версия — v' + n);
        state.version = null; state.cache = {};
        if (state.variant !== 'sidecar') { state.variant = 'sidecar'; if (o.onVariant) o.onVariant('sidecar'); }
        if (o.onSaved) o.onSaved('sidecar', state.entry.sidecar);
        loadVersions();
        loadDoc();
      }).catch(function (err) { C.toast(err.message, true); });
    }
    host.addEventListener('click', onClick);
    // Щелчок вне списка версий закрывает его
    function onOutside(e) {
      if (state.versionsOpen && !(e.target.closest && e.target.closest('[data-vsel]'))) { state.versionsOpen = false; render(); }
    }
    document.addEventListener('click', onOutside);
    if (info) { info.addEventListener('mouseover', onOver); info.addEventListener('mouseleave', function () { highlight(null); }); }

    // Панель не выше кадра: объекты прокручиваются внутри, кнопки внизу всегда видны.
    // Кадр и панель друг под другом (узкий экран) — высота панели не ограничивается.
    var view = host.querySelector('.nml-frame-view');
    function fitInfo() {
      if (!info) return;
      var column = getComputedStyle(host).flexDirection === 'column';
      info.style.height = column || !view.offsetHeight ? '' : view.offsetHeight + 'px';
    }
    var resizeObserver = info && window.ResizeObserver ? new ResizeObserver(fitInfo) : null;
    if (resizeObserver) resizeObserver.observe(view);

    function refresh() {
      return loadEntry().then(function () { loadVersions(); loadDoc(); }).catch(function (err) {
        state.entry = state.entry || { sidecar: {}, production: {} };
        state.error = err.message;
        render();
      });
    }
    if (state.entry) {
      if (!state.variant) state.variant = defaultVariant(state.entry);
      loadVersions();
      loadDoc();
    } else {
      refresh();
    }

    return {
      refresh: refresh,
      setVariant: setVariant,
      destroy: function () {
        state.alive = false;
        if (resizeObserver) resizeObserver.disconnect();
        document.removeEventListener('click', onOutside);
        host.removeEventListener('click', onClick); host.innerHTML = ''; host.classList.remove('nml-frame');
      },
      get variant() { return state.variant; },
      get entry() { return state.entry; },
      get productionKey() { return state.key; },
    };
  }

  return { mount: mount, copyText: copyText };
})();
