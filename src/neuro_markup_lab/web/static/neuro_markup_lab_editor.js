// Редактор разметки NeuroMarkupLab.
//  * Кадр и фигуры LabelMe лежат в ОДНОМ <svg viewBox="0 0 W H"> (W,H — система координат JSON);
//    мышь переводится в координаты кадра через getScreenCTM, правка точна при любом масштабе.
//  * Геометрия: перемещение фигуры (мышь, стрелки, Shift — 10 px), точки и стороны; двойной клик
//    по стороне — новая точка (прямоугольник станет полигоном), по точке или Delete — удалить.
//  * Атрибуты выбранной фигуры: все поля, кроме points и shape_type, — правка по типу поля,
//    добавление и удаление полей. Тип поля один на все фигуры документа; приведение типов и
//    запись выполняет сервер (сначала проверка dry_run, затем запись с подтверждением).
//  * Переключатель «Боевая | Рядом с видео» поверх кадра открывает другой вариант разметки.
//
// Открытие из любой страницы (подключены neuro_markup_lab.css, _shapes.js и _editor.js):
//   NML.editor.open({
//     video: 'D:/video/line1_cam5.avi',  // путь к видео на компьютере сервера (обязательно)
//     jsonsDir: 'D:/markup',              // каталог боевых JSON; нет — только «рядом с видео»
//     variant: 'sidecar',                 // 'sidecar' | 'production'; нет — «рядом с видео», если есть
//     productionKey: 'line1_cam5',        // боевая разметка, выбранная вручную; нет — подбирается
//     version: 3,                         // версия разметки рядом с видео; нет — файл рядом с видео
//     urls: { markup, save, frame, locations },  // свои адреса загрузки и сохранения; нет — адреса редактора
//     onSaved: function (variant, location) {},
//   });
// Окно редактора вставляется в страницу при первом открытии. После сохранения на document
// приходит событие 'nml:saved' с detail = {video, variant, location}.
window.NML = window.NML || {};
NML.editor = (function () {
  var C = NML.common, SVGNS = C.SVGNS, esc = C.esc;
  // Размер ручки точки и ширина полосы захвата стороны на экране, px
  var HANDLE_SCREEN_PX = 10, EDGE_SCREEN_PX = 10;
  // Курсоры углов прямоугольника (по часовой от левого верхнего) и его сторон (верх, право, низ, лево)
  var RECT_CORNER_CURSORS = ['nwse-resize', 'nesw-resize', 'nwse-resize', 'nesw-resize'];
  var RECT_EDGE_CURSORS = ['ns-resize', 'ew-resize', 'ns-resize', 'ew-resize'];
  var VERTEX_CURSOR = 'grab', VERTEX_DRAG_CURSOR = 'grabbing', EDGE_CURSOR = 'crosshair';
  // Шаг сдвига стрелками, px кадра: обычный и с Shift
  var ARROW_STEP = 1, ARROW_STEP_FAST = 10;
  // Минимум точек у полигона и типы, у которых можно добавлять и удалять точки
  var POLYGON_MIN_POINTS = 3;
  var EDITABLE_POINTS_TYPES = { polygon: true, linestrip: true };
  // Точность сравнения координат
  var EPS = 1e-6;
  // Имя атрибута: латиница в нижнем регистре, цифры, «_», не с цифры (как на сервере)
  var ATTRIBUTE_NAME_RE = /^[a-z_][a-z0-9_]*$/;
  // Ключи геометрии — не атрибуты
  var RESERVED = { points: true, shape_type: true };
  // Типы, которые можно задать полю документа
  var FIELD_TYPES = ['int', 'float', 'str', 'bool', 'dict'];
  // Пустые значения по типу (при добавлении поля, не допускающего null)
  var DEFAULTS = { int: 0, float: 0, str: '', bool: false, dict: {} };
  // Размер кадра, если его нет ни в JSON, ни в кадре
  var FALLBACK_W = 1920, FALLBACK_H = 1080;
  // Длина значения в списках и подсказках, символов
  var SHORT_VALUE_LEN = 40;
  // Подсказка для нового своего поля (у полей из схемы подсказку даёт сервер)
  var DOCUMENT_FIELD_HINT = 'Своё поле документа: в модели фигуры его нет, читается по имени.';

  // Адреса API по умолчанию (от корня редактора); ctx.urls их заменяет
  var DEFAULT_URLS = { markup: 'api/markup', save: 'api/save', frame: 'frame', locations: 'api/locations',
                       versions: 'api/versions', versionCurrent: 'api/versions/current', versionUpdate: 'api/versions/update' };
  // Как версия появилась (подписи в списке версий)
  var ORIGIN_LABELS = { initial: 'исходная', external: 'изменена вне редактора', sync: 'синхронизация', editor: '' };
  // Разметка окна редактора: вставляется в страницу при первом открытии
  var EDITOR_HTML = 'static/neuro_markup_lab_editor.html';

  var ctx = null;            // {video, videoName, jsonsDir, productionKey, version, entry, variant, urls, onSaved}
  var versions = null;       // список версий разметки рядом с видео (ответ /api/versions)
  var compare = null;        // сравниваемая версия: {number, doc}
  var domReady = null;       // загрузка окна редактора (Promise)
  var doc = null;            // ответ /api/markup
  var known = {};            // известные поля модели фигуры: имя → spec
  var docFields = {};        // поля документа: имя → {type, nullable} (рабочие)
  var originalDocFields = {};
  var docHints = {};         // подсказки полей документа с сервера: имя → текст
  var shapes = [];
  var selectedIndex = -1, activeVertex = -1;
  var W = 0, H = 0;
  var svg = null, handlesLayer = null, drag = null;
  var modal = null, overlay = null, dialogOk = null, dialogValidate = null, loadSeq = 0;

  function el(id) { return document.getElementById(id); }
  function clonePoints(pts) { return pts.map(function (p) { return [p[0], p[1]]; }); }
  function cloneJson(v) { return v === undefined ? undefined : JSON.parse(JSON.stringify(v)); }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function fmt(n) { return (Math.round(n * 100) / 100).toFixed(2); }
  function isOpen() { return !!modal && !modal.classList.contains('hidden'); }
  function hasOwn(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  function shortValue(v) {
    var s = JSON.stringify(v);
    if (s === undefined) s = String(v);
    return s.length > SHORT_VALUE_LEN ? s.slice(0, SHORT_VALUE_LEN - 1) + '…' : s;
  }

  // ------------------------------------------------------------------ открыть / закрыть
  function open(context) {
    ensureDom().then(function () {
      ctx = Object.assign({}, context);
      versions = null; compare = null;
      ctx.urls = Object.assign({}, DEFAULT_URLS, context.urls || {});
      ctx.jsonsDir = ctx.jsonsDir || '';
      ctx.videoName = ctx.videoName || String(ctx.video || '').split(/[\\/]/).pop();
      el('nml-editor-title').textContent = ctx.videoName;
      el('nml-editor-title').title = ctx.video || '';
      show();
      if (ctx.entry) { start(); return; }
      el('nml-editor-canvas').innerHTML = '<div>Загрузка…</div>';
      C.getJson(ctx.urls.locations, { video: ctx.video, jsons: ctx.jsonsDir, key: ctx.productionKey || '' }).then(function (d) {
        ctx.entry = { sidecar: d.sidecar, production: d.production };
        start();
      }).catch(function (err) {
        el('nml-editor-canvas').innerHTML = '<div>Не удалось найти разметку: ' + esc(err.message) + '</div>';
      });
    }).catch(function (err) { C.toast('Редактор не загрузился: ' + err.message, true); });
  }
  // Открыть вариант из ctx или вариант по умолчанию: «рядом с видео», если есть, иначе боевую
  function start() {
    var entry = ctx.entry;
    var variant = ctx.variant
      || (entry.sidecar && entry.sidecar.exists ? 'sidecar' : (entry.production && entry.production.exists ? 'production' : ''));
    if (variant) { load(variant, variant === 'sidecar' ? ctx.version : null); return; }
    el('nml-editor-canvas').innerHTML = '<div>Разметки нет: ни рядом с видео, ни боевой.</div>';
    C.renderSwitch(el('nml-editor-switch'), entry, '', switchVariant);
  }
  // Окно редактора: уже в странице или загружается из статики редактора
  function ensureDom() {
    if (el('nml-editor')) { init(); return Promise.resolve(); }
    if (!domReady) {
      domReady = fetch(C.url(EDITOR_HTML)).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.text();
      }).then(function (html) {
        var host = document.createElement('div');
        host.innerHTML = html;
        while (host.firstChild) document.body.appendChild(host.firstChild);
        init();
      }).catch(function (err) { domReady = null; throw err; });
    }
    return domReady;
  }
  // Открыть разметку: вариант и, для «рядом с видео», версию (null — файл рядом с видео)
  function load(variant, version) {
    var seq = ++loadSeq;
    ctx.variant = variant;
    ctx.version = variant === 'sidecar' && version != null ? version : null;
    // Прежний кадр остаётся на месте до загрузки новой разметки: вёрстка не прыгает
    var canvas = el('nml-editor-canvas');
    if (svg) canvas.classList.add('nml-loading'); else canvas.innerHTML = '<div>Загрузка…</div>';
    svg = null; handlesLayer = null; shapes = []; selectedIndex = -1; compare = null;
    C.getJson(ctx.urls.markup, { video: ctx.video, variant: variant, jsons: ctx.jsonsDir, key: ctx.productionKey || '',
                                 version: ctx.version == null ? '' : ctx.version }).then(function (d) {
      if (seq !== loadSeq) return;
      doc = d;
      if (doc.location) ctx.entry[variant] = doc.location;
      buildModel();
      renderHeader();
      renderSaveButtons();
      W = doc.image_width || 0; H = doc.image_height || 0;
      if (W && H) { startScene(); return; }
      var probe = new Image();
      probe.onload = function () { if (seq !== loadSeq) return; W = probe.naturalWidth || FALLBACK_W; H = probe.naturalHeight || FALLBACK_H; startScene(); };
      probe.onerror = function () { if (seq !== loadSeq) return; W = FALLBACK_W; H = FALLBACK_H; startScene(); };
      probe.src = C.frameUrl(ctx.video, true, ctx.urls.frame);
    }).catch(function (err) {
      if (seq !== loadSeq) return;
      doc = null;
      el('nml-editor-canvas').classList.remove('nml-loading');
      el('nml-editor-canvas').innerHTML = '<div>Не удалось открыть разметку: ' + esc(err.message) + '</div>';
      C.renderSwitch(el('nml-editor-switch'), ctx.entry, ctx.variant, switchVariant);
    });
  }
  function startScene() {
    selectedIndex = shapes.length ? shapes[0].index : -1;
    activeVertex = -1;
    buildScene();
    drawCompare();
    renderAll();
  }
  function show() {
    overlay.classList.remove('hidden'); modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
    document.addEventListener('keydown', onKey);
    window.addEventListener('resize', renderHandles);
  }
  function close() {
    overlay.classList.add('hidden'); modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    document.removeEventListener('keydown', onKey);
    window.removeEventListener('resize', renderHandles);
    endDrag();
    hideDialog();
    el('nml-versions').classList.add('hidden');
    loadSeq++;
  }
  function requestClose() {
    if (!isDirty()) { close(); return; }
    confirmDialog('Закрыть без сохранения?', 'Несохранённые изменения будут потеряны.', 'Закрыть', close);
  }

  // ------------------------------------------------------------------ модель
  function buildModel() {
    known = {};
    ((doc.schema && doc.schema.known) || []).forEach(function (s) { known[s.name] = s; });
    docFields = {};
    ((doc.schema && doc.schema.document) || []).forEach(function (s) { docFields[s.name] = { type: s.type, nullable: s.nullable }; });
    originalDocFields = cloneJson(docFields);
    docHints = {};
    ((doc.schema && doc.schema.document) || []).forEach(function (s) { if (s.hint) docHints[s.name] = s.hint; });
    shapes = (doc.shapes || []).map(function (s) {
      var pts = clonePoints(s.points || []);
      return {
        index: s.index, originalType: s.shape_type || '', shape_type: s.shape_type || '',
        original: clonePoints(pts), current: clonePoints(pts),
        originalAttrs: cloneJson(s.attributes || {}), attrs: cloneJson(s.attributes || {}),
        elGroup: null, elGeom: null,
      };
    });
  }
  function specFor(name) {
    if (known[name]) return known[name];
    var f = docFields[name] || { type: 'any', nullable: true };
    return { name: name, type: f.type, nullable: f.nullable, known: false, choices: [], deprecated: [],
             strict: false, hidden: false, hint: docHints[name] || DOCUMENT_FIELD_HINT };
  }
  function typeText(spec) {
    if (spec.strict) return 'список';
    return spec.type + (spec.nullable ? ' | null' : '');
  }
  function pointsChanged(sh) {
    if (sh.shape_type !== sh.originalType || sh.current.length !== sh.original.length) return true;
    for (var i = 0; i < sh.current.length; i++) {
      if (Math.abs(sh.current[i][0] - sh.original[i][0]) > EPS || Math.abs(sh.current[i][1] - sh.original[i][1]) > EPS) return true;
    }
    return false;
  }
  function attrsChanged(sh) { return JSON.stringify(sh.attrs) !== JSON.stringify(sh.originalAttrs); }
  function shapeDirty(sh) { return pointsChanged(sh) || attrsChanged(sh); }
  function fieldsDirty() { return JSON.stringify(docFields) !== JSON.stringify(originalDocFields); }
  function isDirty() { return shapes.some(shapeDirty) || fieldsDirty(); }
  function label(sh) { return (sh.attrs && typeof sh.attrs.label === 'string' && sh.attrs.label) || '(без метки)'; }

  // Значение соответствует типу поля (для подсветки; приводит типы сервер)
  function matchesType(spec, v) {
    if (spec.type === 'any') return true;
    if (spec.strict) return (spec.choices || []).indexOf(v) >= 0;
    if (v === null) return !!spec.nullable;
    switch (spec.type) {
      case 'int': return typeof v === 'number' && Number.isInteger(v);
      case 'float': return typeof v === 'number' && isFinite(v);
      case 'str': return typeof v === 'string';
      case 'bool': return typeof v === 'boolean';
      case 'dict': return typeof v === 'object' && !Array.isArray(v);
    }
    return true;
  }
  function mismatches() {
    var list = [];
    shapes.forEach(function (sh) {
      Object.keys(sh.attrs).forEach(function (k) {
        var spec = specFor(k);
        if (!spec.hidden && !matchesType(spec, sh.attrs[k])) list.push({ sh: sh, field: k, value: sh.attrs[k], spec: spec });
      });
    });
    return list;
  }

  // ------------------------------------------------------------------ сцена
  function buildScene() {
    var canvas = el('nml-editor-canvas');
    canvas.innerHTML = '';
    canvas.classList.remove('nml-loading');
    svg = document.createElementNS(SVGNS, 'svg');
    svg.setAttribute('class', 'nml-svg');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    var image = document.createElementNS(SVGNS, 'image');
    image.setAttribute('x', 0); image.setAttribute('y', 0);
    image.setAttribute('width', W); image.setAttribute('height', H);
    image.setAttribute('preserveAspectRatio', 'none');
    image.setAttribute('href', C.frameUrl(ctx.video, true, ctx.urls.frame));
    svg.appendChild(image);
    shapes.forEach(function (sh) {
      var g = document.createElementNS(SVGNS, 'g');
      g.setAttribute('class', 'nml-shape');
      g.setAttribute('data-index', sh.index);
      sh.elGroup = g;
      sh.elGeom = C.createGeom(sh.shape_type, sh.current, 'nml-geom');
      g.appendChild(sh.elGeom);
      g.addEventListener('pointerdown', onShapePointerDown);
      g.addEventListener('dblclick', onShapeDblClick);
      svg.appendChild(g);
      applyVisibility(sh);
    });
    handlesLayer = document.createElementNS(SVGNS, 'g');
    svg.appendChild(handlesLayer);
    canvas.appendChild(svg);
  }
  function rebuildGeom(sh) {
    var fresh = C.createGeom(sh.shape_type, sh.current, 'nml-geom');
    if (sh.elGeom && sh.elGeom.parentNode) sh.elGeom.parentNode.replaceChild(fresh, sh.elGeom);
    sh.elGeom = fresh;
  }
  function applyVisibility(sh) {
    if (sh.elGroup) sh.elGroup.classList.toggle('hidden-shape', !C.isVisible(sh.attrs));
  }
  function byIndex(idx) {
    for (var i = 0; i < shapes.length; i++) if (shapes[i].index === idx) return shapes[i];
    return null;
  }
  function selected() { return byIndex(selectedIndex); }

  // ------------------------------------------------------------------ ручки
  function rectBounds(pts) {
    return { x1: Math.min(pts[0][0], pts[1][0]), x2: Math.max(pts[0][0], pts[1][0]),
             y1: Math.min(pts[0][1], pts[1][1]), y2: Math.max(pts[0][1], pts[1][1]) };
  }
  function handlePoints(sh) {
    if (sh.shape_type === 'rectangle' && sh.current.length >= 2) {
      var r = rectBounds(sh.current);
      return [[r.x1, r.y1], [r.x2, r.y1], [r.x2, r.y2], [r.x1, r.y2]];
    }
    if (sh.shape_type === 'circle') return [];
    return sh.current;
  }
  function edgeList(sh) {
    var n = handlePoints(sh).length, closed = sh.shape_type === 'rectangle' || sh.shape_type === 'polygon';
    if (n < 2) return [];
    var count = closed ? n : n - 1, edges = [];
    for (var i = 0; i < count; i++) edges.push([i, (i + 1) % n]);
    return edges;
  }
  function isRect(sh) { return sh.shape_type === 'rectangle'; }
  function vertexCursor(sh, i) { return isRect(sh) ? RECT_CORNER_CURSORS[i % 4] : VERTEX_CURSOR; }
  function edgeCursor(sh, i) { return isRect(sh) ? RECT_EDGE_CURSORS[i % 4] : EDGE_CURSOR; }
  function screenToUser(px) {
    var ctm = svg && svg.getScreenCTM();
    var scale = ctm ? Math.abs(ctm.a) : 1;
    return px / (scale || 1);
  }
  // Ручки пересоздаются только при смене фигуры/типа/числа точек — иначе обрывается захват мыши
  function renderHandles() {
    if (!handlesLayer) return;
    var sh = selected();
    if (!sh || !C.isVisible(sh.attrs)) { handlesLayer.innerHTML = ''; handlesLayer.removeAttribute('data-sig'); return; }
    var pts = handlePoints(sh), edges = edgeList(sh);
    var sig = sh.index + ':' + sh.shape_type + ':' + pts.length;
    if (handlesLayer.getAttribute('data-sig') !== sig) buildHandles(sh, pts, edges, sig);
    var size = screenToUser(HANDLE_SCREEN_PX), width = screenToUser(EDGE_SCREEN_PX);
    var edgeEls = handlesLayer.querySelectorAll('.nml-edge');
    edges.forEach(function (e, i) {
      var line = edgeEls[i], p = pts[e[0]], q = pts[e[1]];
      line.setAttribute('x1', p[0]); line.setAttribute('y1', p[1]);
      line.setAttribute('x2', q[0]); line.setAttribute('y2', q[1]);
      line.setAttribute('stroke-width', width);
    });
    var vertexEls = handlesLayer.querySelectorAll('.nml-handle');
    pts.forEach(function (p, i) {
      var h = vertexEls[i];
      h.setAttribute('x', p[0] - size / 2); h.setAttribute('y', p[1] - size / 2);
      h.setAttribute('width', size); h.setAttribute('height', size);
      h.classList.toggle('active', i === activeVertex);
    });
  }
  function buildHandles(sh, pts, edges, sig) {
    handlesLayer.innerHTML = '';
    handlesLayer.setAttribute('data-sig', sig);
    // Сначала стороны, поверх — точки: у маленькой фигуры угол важнее стороны
    edges.forEach(function (e, i) {
      var line = document.createElementNS(SVGNS, 'line');
      line.setAttribute('class', 'nml-edge');
      line.setAttribute('data-edge', i);
      line.style.cursor = edgeCursor(sh, i);
      line.addEventListener('pointerdown', onEdgePointerDown);
      line.addEventListener('dblclick', onEdgeDblClick);
      handlesLayer.appendChild(line);
    });
    pts.forEach(function (p, i) {
      var h = document.createElementNS(SVGNS, 'rect');
      h.setAttribute('class', 'nml-handle');
      h.setAttribute('data-vertex', i);
      h.style.cursor = vertexCursor(sh, i);
      h.addEventListener('pointerdown', onHandlePointerDown);
      h.addEventListener('dblclick', onHandleDblClick);
      handlesLayer.appendChild(h);
    });
  }

  // ------------------------------------------------------------------ мышь
  function clientToUser(cx, cy) {
    var pt = svg.createSVGPoint(); pt.x = cx; pt.y = cy;
    var u = pt.matrixTransform(svg.getScreenCTM().inverse());
    return { x: u.x, y: u.y };
  }
  // Перетаскивание отслеживается на окне: ручки под мышью пересоздаются, мышь уходит за кадр
  function startDrag(e, state, cursor) {
    e.preventDefault(); e.stopPropagation();
    endDrag();
    drag = state;
    drag.start = clientToUser(e.clientX, e.clientY);
    drag.startPoints = clonePoints(byIndex(state.idx).current);
    svg.classList.add('dragging');
    svg.style.cursor = cursor;
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', endDrag);
    window.addEventListener('pointercancel', endDrag);
  }
  function endDrag() {
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', endDrag);
    window.removeEventListener('pointercancel', endDrag);
    if (svg) { svg.classList.remove('dragging'); svg.style.cursor = ''; }
    drag = null;
  }
  function onShapePointerDown(e) {
    if (e.button !== 0 || e.detail > 1) return;   // второй клик двойного клика обрабатывает dblclick
    var idx = parseInt(e.currentTarget.getAttribute('data-index'), 10);
    if (idx !== selectedIndex) select(idx);
    startDrag(e, { mode: 'move', idx: idx }, 'move');
  }
  function onHandlePointerDown(e) {
    if (e.button !== 0 || e.detail > 1) return;
    var vertex = parseInt(e.currentTarget.getAttribute('data-vertex'), 10);
    var sh = selected();
    activeVertex = vertex;
    var state = { mode: 'vertex', idx: selectedIndex, vertex: vertex };
    // Противоположный угол прямоугольника стоит на месте
    if (isRect(sh)) state.fixed = handlePoints(sh)[(vertex + 2) % 4].slice();
    startDrag(e, state, isRect(sh) ? vertexCursor(sh, vertex) : VERTEX_DRAG_CURSOR);
    renderHandles();
  }
  function onEdgePointerDown(e) {
    if (e.button !== 0 || e.detail > 1) return;
    var edge = parseInt(e.currentTarget.getAttribute('data-edge'), 10);
    var sh = selected();
    activeVertex = -1;
    startDrag(e, { mode: 'edge', idx: selectedIndex, edge: edge, pair: edgeList(sh)[edge] }, edgeCursor(sh, edge));
    renderHandles();
  }
  function onPointerMove(e) {
    if (!drag) return;
    var u = clientToUser(e.clientX, e.clientY), sh = byIndex(drag.idx);
    var dx = u.x - drag.start.x, dy = u.y - drag.start.y;
    if (drag.mode === 'move') {
      sh.current = drag.startPoints.map(function (p) { return [p[0] + dx, p[1] + dy]; });
    } else if (drag.mode === 'vertex') {
      var x = clamp(u.x, 0, W), y = clamp(u.y, 0, H);
      if (isRect(sh)) {
        sh.current = [[Math.min(drag.fixed[0], x), Math.min(drag.fixed[1], y)], [Math.max(drag.fixed[0], x), Math.max(drag.fixed[1], y)]];
      } else {
        sh.current[drag.vertex] = [x, y];
      }
    } else if (isRect(sh)) {
      sh.current = moveRectEdge(rectBounds(drag.startPoints), drag.edge, u);
    } else {
      sh.current = clonePoints(drag.startPoints);
      drag.pair.forEach(function (i) { sh.current[i] = [drag.startPoints[i][0] + dx, drag.startPoints[i][1] + dy]; });
    }
    geometryChanged(sh);
  }
  // Сторона прямоугольника (0 — верх, 1 — право, 2 — низ, 3 — лево) идёт за мышью
  function moveRectEdge(r, edge, u) {
    var x = clamp(u.x, 0, W), y = clamp(u.y, 0, H);
    if (edge === 0) r.y1 = y; else if (edge === 1) r.x2 = x; else if (edge === 2) r.y2 = y; else r.x1 = x;
    return [[Math.min(r.x1, r.x2), Math.min(r.y1, r.y2)], [Math.max(r.x1, r.x2), Math.max(r.y1, r.y2)]];
  }
  function onShapeDblClick(e) {
    var idx = parseInt(e.currentTarget.getAttribute('data-index'), 10), sh = byIndex(idx);
    if (!sh || !EDITABLE_POINTS_TYPES[sh.shape_type]) return;
    e.preventDefault(); endDrag();
    var u = clientToUser(e.clientX, e.clientY), best = nearestSegment(sh, u.x, u.y);
    if (!best) return;
    if (idx !== selectedIndex) select(idx);
    insertVertex(sh, best.insertAt, best.x, best.y);
  }
  function onEdgeDblClick(e) {
    e.preventDefault(); e.stopPropagation(); endDrag();
    var sh = selected();
    if (!sh) return;
    var edge = parseInt(e.currentTarget.getAttribute('data-edge'), 10);
    if (isRect(sh)) toPolygon();
    if (!EDITABLE_POINTS_TYPES[sh.shape_type]) return;
    var pair = edgeList(sh)[edge];
    var p = projectOnSegment(sh.current[pair[0]], sh.current[pair[1]], clientToUser(e.clientX, e.clientY));
    insertVertex(sh, pair[0] + 1, p.x, p.y);
  }
  function onHandleDblClick(e) {
    e.preventDefault(); e.stopPropagation(); endDrag();
    removeVertex(parseInt(e.currentTarget.getAttribute('data-vertex'), 10));
  }
  function insertVertex(sh, at, x, y) { sh.current.splice(at, 0, [x, y]); activeVertex = at; geometryChanged(sh); }
  function projectOnSegment(a, b, u) {
    var vx = b[0] - a[0], vy = b[1] - a[1], len2 = vx * vx + vy * vy;
    var t = len2 ? clamp(((u.x - a[0]) * vx + (u.y - a[1]) * vy) / len2, 0, 1) : 0;
    return { x: a[0] + t * vx, y: a[1] + t * vy };
  }
  function nearestSegment(sh, x, y) {
    var pts = sh.current, n = pts.length, best = null;
    var segments = sh.shape_type === 'polygon' ? n : n - 1;
    for (var i = 0; i < segments; i++) {
      var p = projectOnSegment(pts[i], pts[(i + 1) % n], { x: x, y: y }), d = Math.hypot(x - p.x, y - p.y);
      if (!best || d < best.d) best = { d: d, x: p.x, y: p.y, insertAt: i + 1 };
    }
    return best;
  }
  function minPoints(sh) { return sh.shape_type === 'polygon' ? POLYGON_MIN_POINTS : 2; }
  function removeVertex(vertex) {
    var sh = selected();
    if (!sh || !EDITABLE_POINTS_TYPES[sh.shape_type] || vertex < 0) return;
    if (sh.current.length <= minPoints(sh)) { C.toast('Меньше ' + minPoints(sh) + ' точек оставить нельзя.'); return; }
    sh.current.splice(vertex, 1);
    activeVertex = -1;
    geometryChanged(sh);
  }

  // ------------------------------------------------------------------ правка геометрии
  // Во время перетаскивания панель целиком не перерисовывается — только координаты и маркер
  function geometryChanged(sh) {
    C.updateGeom(sh.elGeom, sh.shape_type, sh.current);
    renderHandles();
    renderCoords();
    updateListItem(sh);
    updateGeometryActions(sh);
  }
  function moveShape(dx, dy) {
    var sh = selected();
    sh.current = sh.current.map(function (p) { return [p[0] + dx, p[1] + dy]; });
    geometryChanged(sh);
  }
  function toPolygon() {
    var sh = selected();
    if (!sh || sh.shape_type !== 'rectangle') return;
    sh.current = handlePoints(sh).map(function (p) { return p.slice(); });
    sh.shape_type = 'polygon';
    activeVertex = -1;
    rebuildGeom(sh);
    renderAll();
  }
  function resetGeometry() {
    var sh = selected();
    if (!sh) return;
    sh.current = clonePoints(sh.original);
    sh.shape_type = sh.originalType;
    activeVertex = -1;
    rebuildGeom(sh);
    renderAll();
  }

  // ------------------------------------------------------------------ правка атрибутов
  function attributesChanged(sh) {
    applyVisibility(sh);
    renderAll();
  }
  function setAttr(sh, name, value) { sh.attrs[name] = value; attributesChanged(sh); }
  function removeAttr(sh, name) {
    if (specFor(name).required) { C.toast('Поле ' + name + ' удалить нельзя.'); return; }
    delete sh.attrs[name];
    attributesChanged(sh);
  }
  function resetAttrs() {
    var sh = selected();
    if (!sh) return;
    sh.attrs = cloneJson(sh.originalAttrs);
    attributesChanged(sh);
  }
  // Галочка «показывать»: show=false; обратно — как было в исходном JSON (поля могло не быть)
  function setVisible(sh, visible) {
    if (visible && !hasOwn(sh.originalAttrs, 'show')) delete sh.attrs.show;
    else sh.attrs.show = visible;
    attributesChanged(sh);
  }
  function defaultValue(spec) { return spec.nullable ? null : cloneJson(DEFAULTS[spec.type]); }
  // Разбор введённого значения по типу поля: {ok, value}
  function parseInput(spec, raw) {
    if (spec.type === 'bool') return { ok: true, value: !!raw };
    if (spec.type === 'str') return { ok: true, value: String(raw) };
    var t = String(raw).trim();
    if (t === '') return spec.nullable ? { ok: true, value: null } : { ok: false };
    if (spec.type === 'dict') {
      var obj;
      try { obj = JSON.parse(t); } catch (err) { return { ok: false }; }
      return (obj && typeof obj === 'object' && !Array.isArray(obj)) ? { ok: true, value: obj } : { ok: false };
    }
    if (spec.type === 'int') return /^-?\d+$/.test(t) ? { ok: true, value: parseInt(t, 10) } : { ok: false };
    if (spec.type === 'float') {
      var n = Number(t.replace(',', '.'));
      return isFinite(n) ? { ok: true, value: n } : { ok: false };
    }
    return { ok: false };
  }
  // Поля, которые можно добавить фигуре: известные и поля документа, которых у неё нет
  function addableFields(sh) {
    var names = [];
    Object.keys(known).forEach(function (k) { if (!hasOwn(sh.attrs, k) && known[k].type !== 'any' && !known[k].hidden) names.push(k); });
    Object.keys(docFields).forEach(function (k) { if (!hasOwn(sh.attrs, k) && docFields[k].type !== 'any') names.push(k); });
    return names;
  }
  function addExistingField(sh, name) {
    var spec = specFor(name);
    sh.attrs[name] = spec.strict ? (spec.choices[0] || '') : defaultValue(spec);
    attributesChanged(sh);
  }
  function validateNewName(name) {
    if (!name) return 'Введите имя поля.';
    if (!ATTRIBUTE_NAME_RE.test(name)) return 'Только латиница в нижнем регистре, цифры и «_», не с цифры.';
    if (RESERVED[name]) return 'Имя занято геометрией фигуры.';
    if (known[name] || docFields[name]) return 'Такое поле уже есть — выберите его в списке «Добавить поле».';
    return '';
  }
  // Новое поле — в диалоге поверх редактора, панель при этом не съезжает
  function openNewFieldDialog(sh) {
    var body = '<div class="nml-form">'
      + '<label class="nml-form-row"><span>Имя</span><input type="text" class="nml-input" id="nml-new-name" placeholder="имя_поля" autocomplete="off" spellcheck="false"></label>'
      + '<label class="nml-form-row"><span>Тип</span><select class="nml-input" id="nml-new-type">'
      + FIELD_TYPES.map(function (t) { return '<option value="' + t + '">' + t + '</option>'; }).join('') + '</select></label>'
      + '<label class="nml-check"><input type="checkbox" id="nml-new-nullable" checked> может быть null</label>'
      + '<label class="nml-check"><input type="checkbox" id="nml-new-all"> добавить всем фигурам документа</label>'
      + '<div class="muted">Имя — латиница в нижнем регистре, цифры и «_», не с цифры. Поле появится у других фигур в списке «Добавить поле».</div>'
      + '</div>';
    formDialog('Новое поле фигуры #' + sh.index, body, 'Добавить', function () {
      return validateNewName(el('nml-new-name').value.trim());
    }, function () {
      addNewField(sh, el('nml-new-name').value.trim(), el('nml-new-type').value, el('nml-new-nullable').checked, el('nml-new-all').checked);
    });
    var input = el('nml-new-name');
    input.addEventListener('input', function () {
      var error = input.value ? validateNewName(input.value.trim()) : '';
      input.classList.toggle('invalid', !!error);
      el('nml-dialog-error').textContent = error;
    });
    input.focus();
  }
  function addNewField(sh, name, type, nullable, toAll) {
    docFields[name] = { type: type, nullable: nullable };
    var value = defaultValue(specFor(name));
    (toAll ? shapes : [sh]).forEach(function (s) { if (!hasOwn(s.attrs, name)) s.attrs[name] = cloneJson(value); });
    renderAll();
  }
  function setFieldType(name, type, nullable) {
    docFields[name] = { type: type, nullable: nullable };
    renderAll();
  }
  function removeFieldEverywhere(name) {
    confirmDialog('Удалить поле у всех фигур?', 'Поле <code>' + esc(name) + '</code> будет удалено у всех фигур документа.', 'Удалить', function () {
      shapes.forEach(function (s) { delete s.attrs[name]; });
      delete docFields[name];
      renderAll();
    });
  }

  // ------------------------------------------------------------------ клавиши
  function onKey(e) {
    if (!isOpen()) return;
    if (!el('nml-dialog').classList.contains('hidden')) {
      if (e.key === 'Escape') { e.preventDefault(); hideDialog(); }
      return;
    }
    var tag = (e.target && e.target.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (e.key === 'Escape') { requestClose(); return; }
    if (!selected()) return;
    if ((e.key === 'Delete' || e.key === 'Backspace') && activeVertex >= 0) { e.preventDefault(); removeVertex(activeVertex); return; }
    var d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
    if (!d) return;
    e.preventDefault();
    var step = e.shiftKey ? ARROW_STEP_FAST : ARROW_STEP;
    moveShape(d[0] * step, d[1] * step);
  }

  // ------------------------------------------------------------------ выбор
  function select(idx) {
    if (idx !== selectedIndex) activeVertex = -1;
    selectedIndex = idx;
    renderAll();
  }
  function applySelection() {
    shapes.forEach(function (sh) { if (sh.elGroup) sh.elGroup.classList.toggle('selected', sh.index === selectedIndex); });
    var sh = selected();
    // выбранная фигура — поверх остальных, ручки — поверх всего
    if (sh && sh.elGroup && svg) svg.insertBefore(sh.elGroup, handlesLayer);
    renderHandles();
  }

  // ------------------------------------------------------------------ отрисовка панели
  function renderAll() {
    renderDocInfo();
    renderTypes();
    renderList();
    renderSelected();
    renderDocFields();
    applySelection();
  }
  // Шапка: открытая разметка (цвет варианта, версия) и полный путь к её JSON ссылкой
  function renderHeader() {
    var loc = doc.location || {};
    var version = '';
    if (ctx.variant === 'sidecar') {
      if (doc.markup_version != null) version = ' · v' + doc.markup_version;
      else if (doc.versions_count) version = ' · <span class="nml-warn-text">изменён вне версий — сохранится новой версией</span>';
    }
    el('nml-editor-source').innerHTML = '<b class="nml-v-' + esc(ctx.variant) + '">' + esc(C.VARIANT_LABELS[ctx.variant]) + version + '</b> '
      + '<a href="#" class="nml-link" data-open-variant="' + esc(ctx.variant) + '" title="Открыть в программе по умолчанию">'
      + esc(loc.path || loc.name || '') + '</a>';
    renderSwitch();
    if (ctx.variant === 'sidecar' && doc.versions_count) refreshVersions();
    else { versions = null; el('nml-versions').classList.add('hidden'); }
  }
  // Переключатель вариантов и, для разметки рядом с видео с версиями, кнопка версии «vN ▾»
  function renderSwitch() {
    var host = el('nml-editor-switch');
    C.renderSwitch(host, ctx.entry, ctx.variant, switchVariant);
    if (!doc || ctx.variant !== 'sidecar' || !doc.versions_count) return;
    var n = doc.markup_version;
    var v = n != null ? versionByNumber(n) : null;
    var title = n == null ? 'Файл изменён вне версий' : 'v' + n + (v && v.comment ? ' — ' + v.comment : '') + '. Выбрать версию';
    host.insertAdjacentHTML('beforeend', '<button type="button" class="nml-ver-seg" data-ver-toggle title="' + esc(title) + '">'
      + (n != null ? 'v' + n : 'вне версий') + ' ▾</button>');
    host.querySelector('[data-ver-toggle]').addEventListener('click', function (e) { e.stopPropagation(); toggleVersions(); });
  }
  // Кнопка «в боевой JSON» неактивна, если путь боевого JSON не определён; «в версию» — только для открытой версии
  function renderSaveButtons() {
    var prod = el('nml-save-production'), loc = ctx.entry.production || {};
    prod.disabled = !loc.path;
    prod.title = loc.path ? loc.path : (loc.reason || '');
    el('nml-save-sidecar').disabled = !(ctx.entry.sidecar || {}).path;
    var save = el('nml-save-current'), target = currentTarget();
    save.disabled = !doc || !target;
    save.title = !target ? '' : target.variant === 'production' ? 'Перезаписать боевой JSON'
      : target.mode === 'overwrite' ? 'Перезаписать версию v' + openVersion() + ' разметки рядом с видео'
        : 'Сохранить новой версией разметки рядом с видео';
  }
  // Куда сохраняет «Сохранить»: в открытую версию, в боевой JSON или — файл вне версий — новой версией
  function currentTarget() {
    if (!doc || !ctx.variant) return null;
    if (ctx.variant === 'production') return (ctx.entry.production || {}).path ? { variant: 'production' } : null;
    return { variant: 'sidecar', mode: openVersion() != null ? 'overwrite' : 'new' };
  }
  function saveCurrent() {
    var target = currentTarget();
    if (target) doSave(target.variant, target.mode);
  }
  // Открытая версия разметки рядом с видео (null — открыта боевая или файл вне истории версий)
  function openVersion() { return doc && ctx.variant === 'sidecar' && doc.markup_version != null ? doc.markup_version : null; }
  function renderDocInfo() {
    var parts = [];
    if (W && H) parts.push(W + '×' + H);
    if (doc.version) parts.push('LabelMe ' + doc.version);
    parts.push('фигур: ' + shapes.length);
    el('nml-editor-docinfo').textContent = parts.join(' · ');
  }
  function renderTypes() {
    var host = el('nml-editor-types'), list = mismatches();
    if (!list.length) { host.innerHTML = ''; return; }
    host.innerHTML = '<div class="nml-types"><div><b>Значения не по типу поля: ' + list.length + '</b> — при сохранении '
      + 'приводятся к типу; то, что не приводится или не из списка, нужно исправить.</div>'
      + list.map(function (m) {
        return '<div class="nml-types-row" data-index="' + m.sh.index + '">#' + m.sh.index + ' ' + esc(label(m.sh)) + ' · <code>'
          + esc(m.field) + '</code>: ' + esc(shortValue(m.value)) + ' → ' + esc(m.spec.strict ? 'значение из списка' : typeText(m.spec)) + '</div>';
      }).join('') + '</div>';
  }
  function renderList() {
    var host = el('nml-editor-shapes');
    if (!shapes.length) { host.innerHTML = '<div class="muted">В разметке нет фигур.</div>'; return; }
    host.innerHTML = shapes.map(function (sh) {
      var a = sh.attrs, meta = ['#' + sh.index, sh.shape_type || '—'];
      if (hasOwn(a, 'group_id')) meta.push('group ' + (a.group_id === null ? '—' : a.group_id));
      if (hasOwn(a, 'wz')) meta.push('wz ' + (a.wz === null ? '—' : a.wz));
      if (a.position) meta.push(String(a.position));
      var visible = C.isVisible(a);
      return '<div class="nml-item' + (sh.index === selectedIndex ? ' active' : '') + (visible ? '' : ' is-hidden') + '" data-index="' + sh.index + '">'
        + '<input type="checkbox" class="nml-show-cb" data-index="' + sh.index + '" title="Показывать фигуру"' + (visible ? ' checked' : '') + '>'
        + '<span class="nml-item-main"><span class="nml-item-label">' + esc(label(sh))
        + '<span class="nml-changed" title="изменена">' + (shapeDirty(sh) ? ' •' : '') + '</span></span>'
        + '<span class="nml-item-meta">' + esc(meta.join(' · ')) + '</span></span></div>';
    }).join('');
  }
  function updateListItem(sh) {
    var mark = el('nml-editor-shapes').querySelector('.nml-item[data-index="' + sh.index + '"] .nml-changed');
    if (mark) mark.textContent = shapeDirty(sh) ? ' •' : '';
  }

  // Выбранная фигура: заголовок с постоянными кнопками, координаты, атрибуты
  function renderSelected() {
    var host = el('nml-editor-selected'), sh = selected();
    if (!sh) { host.innerHTML = '<div class="muted">Выберите объект.</div>'; return; }
    host.innerHTML = '<div class="nml-sel-head"><div class="nml-sel-title">#' + sh.index + ' ' + esc(label(sh))
      + ' <span class="muted nml-sel-type" id="nml-editor-geomtype"></span></div>'
      + '<div class="nml-sel-actions">'
      + '<button type="button" class="nml-btn nml-btn-sm" data-action="to-polygon" title="Прямоугольник станет полигоном из 4 точек">В полигон</button>'
      + '<button type="button" class="nml-btn nml-btn-sm" data-action="reset-geometry" title="Вернуть исходные точки и тип фигуры">Вернуть форму</button>'
      + '<button type="button" class="nml-btn nml-btn-sm" data-action="reset-attrs" title="Вернуть исходные атрибуты фигуры">Вернуть атрибуты</button>'
      + '</div></div>'
      + '<div class="nml-sub">Координаты</div><div class="nml-coords" id="nml-editor-coords"></div>'
      + '<div class="nml-sub">Атрибуты</div>'
      + '<div class="nml-attrs"><div class="nml-attr nml-attr-head"><span>Поле</span><span>Тип</span><span>Значение</span><span></span><span></span></div>'
      + attrRows(sh) + '</div>'
      + '<select class="nml-input nml-input-sm nml-add-select" data-add-select>' + addOptions(sh) + '</select>';
    renderCoords();
    updateGeometryActions(sh);
  }
  // Кнопки не исчезают — неприменимые неактивны, вёрстка не съезжает
  function updateGeometryActions(sh) {
    var host = el('nml-editor-selected');
    if (!host || !sh) return;
    var state = { 'to-polygon': sh.shape_type === 'rectangle', 'reset-geometry': pointsChanged(sh), 'reset-attrs': attrsChanged(sh) };
    Object.keys(state).forEach(function (a) {
      var btn = host.querySelector('[data-action="' + a + '"]');
      if (btn) btn.disabled = !state[a];
    });
    var t = el('nml-editor-geomtype');
    if (t) t.textContent = (sh.shape_type === sh.originalType ? sh.shape_type : sh.originalType + ' → ' + sh.shape_type) + ' · точек: ' + sh.current.length;
  }
  // Координаты редактируются числами; при перетаскивании обновляются значения, поле в фокусе не трогаем
  function renderCoords() {
    var host = el('nml-editor-coords'), sh = selected();
    if (!host || !sh) return;
    var inputs = host.querySelectorAll('input[data-coord]');
    if (inputs.length !== sh.current.length * 2) {
      host.innerHTML = sh.current.map(function (p, i) {
        return '<span class="muted">P' + (i + 1) + '</span>'
          + '<label>X <input type="text" class="nml-input nml-input-sm" inputmode="decimal" data-coord="' + i + '" data-axis="0"></label>'
          + '<label>Y <input type="text" class="nml-input nml-input-sm" inputmode="decimal" data-coord="' + i + '" data-axis="1"></label>';
      }).join('');
      inputs = host.querySelectorAll('input[data-coord]');
    }
    Array.prototype.forEach.call(inputs, function (input) {
      if (input === document.activeElement) return;
      var p = sh.current[parseInt(input.getAttribute('data-coord'), 10)];
      input.value = fmt(p[parseInt(input.getAttribute('data-axis'), 10)]);
      input.classList.remove('invalid');
    });
  }
  function setCoord(input) {
    var sh = selected(), n = Number(String(input.value).trim().replace(',', '.'));
    if (!sh || String(input.value).trim() === '' || !isFinite(n)) { input.classList.add('invalid'); C.toast('Координата — число.', true); return; }
    var i = parseInt(input.getAttribute('data-coord'), 10), axis = parseInt(input.getAttribute('data-axis'), 10);
    sh.current[i][axis] = n;
    input.blur();
    geometryChanged(sh);
  }
  function attrRows(sh) {
    var names = Object.keys(sh.attrs).filter(function (n) { return !specFor(n).hidden; });
    if (!names.length) return '<div class="muted">Атрибутов нет.</div>';
    return names.map(function (name) {
      var spec = specFor(name), v = sh.attrs[name], ok = matchesType(spec, v);
      var hint = (spec.title ? spec.title + '. ' : '') + (spec.hint || '');
      return '<div class="nml-attr' + (ok ? '' : ' mismatch') + '">'
        + '<span class="nml-attr-name' + (spec.known ? ' known' : '') + '" title="' + esc(hint) + '">' + esc(name) + '</span>'
        + '<span class="nml-attr-type" title="' + esc(ok ? 'Тип поля' : 'Значение не подходит к полю') + '">' + esc(typeText(spec)) + '</span>'
        + '<span class="nml-attr-value">' + valueEditor(spec, name, v) + '</span>'
        + '<span>' + nullButton(spec, name, v) + '</span>'
        + '<span>' + (spec.required ? '' : '<button type="button" class="nml-attr-del" data-del="' + esc(name) + '" title="Удалить поле у фигуры">×</button>') + '</span>'
        + '</div>';
    }).join('');
  }
  function valueEditor(spec, name, v) {
    var attr = ' data-attr="' + esc(name) + '"';
    if (spec.type === 'any') return '<span class="nml-attr-ro" title="' + esc(JSON.stringify(v)) + '">' + esc(shortValue(v)) + '</span>';
    if (spec.strict) {
      var choices = spec.choices || [], deprecated = spec.deprecated || [];
      var options = choices.map(function (c) {
        return '<option value="' + esc(c) + '"' + (c === v ? ' selected' : '') + '>' + esc(c === '' ? '(пусто)' : c)
          + (deprecated.indexOf(c) >= 0 ? ' (устаревшая)' : '') + '</option>';
      });
      if (choices.indexOf(v) < 0) options.unshift('<option value="" selected disabled>' + esc(shortValue(v)) + ' — нет в списке</option>');
      return '<select class="nml-input nml-input-sm"' + attr + '>' + options.join('') + '</select>';
    }
    if (spec.type === 'bool' && (v === null || typeof v === 'boolean')) {
      return '<input type="checkbox"' + attr + (v === true ? ' checked' : '') + '>';
    }
    if (spec.type === 'dict') {
      var dictText = v === null ? '' : (typeof v === 'string' ? v : JSON.stringify(v));
      return '<input type="text" class="nml-input nml-input-sm nml-mono" spellcheck="false"' + attr + (v === null ? ' placeholder="null"' : '') + ' value="' + esc(dictText) + '">';
    }
    var text = v === null || v === undefined ? '' : (typeof v === 'string' ? v : JSON.stringify(v));
    var mode = spec.type === 'int' ? ' inputmode="numeric"' : (spec.type === 'float' ? ' inputmode="decimal"' : '');
    var ph = v === null ? ' placeholder="null"' : '';
    return '<input type="text" class="nml-input nml-input-sm" spellcheck="false"' + attr + mode + ph + ' value="' + esc(text) + '">';
  }
  function nullButton(spec, name, v) {
    if (!spec.nullable || spec.type === 'any') return '';
    return '<button type="button" class="nml-btn nml-attr-null' + (v === null ? ' on' : '') + '" data-null="' + esc(name) + '" title="'
      + (v === null ? 'Сейчас null — нажмите, чтобы задать значение' : 'Сделать null') + '">null</button>';
  }
  function addOptions(sh) {
    return '<option value="">+ Добавить поле…</option>' + addableFields(sh).map(function (n) {
      return '<option value="' + esc(n) + '">' + esc(n) + ' (' + esc(typeText(specFor(n))) + ')</option>';
    }).join('') + '<option value="__new__">Новое поле…</option>';
  }
  function renderDocFields() {
    var host = el('nml-editor-docfields'), names = Object.keys(docFields);
    if (!names.length) {
      host.innerHTML = '<div class="muted">Своих полей нет. Новое поле — в списке «Добавить поле» у фигуры.</div>';
      return;
    }
    host.innerHTML = '<div class="muted">Тип поля один на все фигуры документа; при сохранении значения приводятся к нему.</div>'
      + names.map(function (name) {
        var f = docFields[name], count = shapes.filter(function (s) { return hasOwn(s.attrs, name); }).length;
        var typeSelect = f.type === 'any'
          ? '<span class="nml-attr-type" title="Значения разных видов — поле только для просмотра">any</span>'
          : '<select class="nml-input nml-input-sm" data-field-type="' + esc(name) + '">' + FIELD_TYPES.map(function (t) {
            return '<option value="' + t + '"' + (t === f.type ? ' selected' : '') + '>' + t + '</option>'; }).join('') + '</select>';
        return '<div class="nml-docfield"><span class="nml-attr-name" title="' + esc(specFor(name).hint) + '">' + esc(name)
          + ' <span class="muted">· фигур: ' + count + '</span></span>'
          + typeSelect
          + '<label class="nml-check" title="Можно хранить null"><input type="checkbox" data-field-nullable="' + esc(name) + '"'
          + (f.nullable ? ' checked' : '') + (f.type === 'any' ? ' disabled' : '') + '> null</label>'
          + '<button type="button" class="nml-btn nml-btn-sm nml-btn-danger" data-field-del="' + esc(name) + '">Удалить у всех</button></div>';
      }).join('');
  }

  // ------------------------------------------------------------------ события панели
  function onSideClick(e) {
    var t = e.target;
    if (!t.closest) return;
    var row = t.closest('.nml-types-row');
    if (row) { select(parseInt(row.getAttribute('data-index'), 10)); return; }
    var item = t.closest('.nml-item');
    if (item) { if (!t.classList.contains('nml-show-cb')) select(parseInt(item.getAttribute('data-index'), 10)); return; }
    var sh = selected();
    var action = t.closest('[data-action]');
    if (action) {
      var a = action.getAttribute('data-action');
      if (a === 'to-polygon') toPolygon();
      else if (a === 'reset-geometry') resetGeometry();
      else if (a === 'reset-attrs') resetAttrs();
      return;
    }
    var del = t.closest('[data-del]');
    if (del && sh) { removeAttr(sh, del.getAttribute('data-del')); return; }
    var nul = t.closest('[data-null]');
    if (nul && sh) {
      var name = nul.getAttribute('data-null'), spec = specFor(name);
      setAttr(sh, name, sh.attrs[name] === null ? cloneJson(DEFAULTS[spec.type]) : null);
      return;
    }
    var fdel = t.closest('[data-field-del]');
    if (fdel) removeFieldEverywhere(fdel.getAttribute('data-field-del'));
  }
  function onSideChange(e) {
    var t = e.target, sh = selected();
    if (t.classList.contains('nml-show-cb')) { setVisible(byIndex(parseInt(t.getAttribute('data-index'), 10)), t.checked); return; }
    if (t.hasAttribute('data-coord')) { setCoord(t); return; }
    if (t.hasAttribute('data-add-select')) {
      var v = t.value;
      t.value = '';
      if (v === '__new__' && sh) openNewFieldDialog(sh);
      else if (v && sh) addExistingField(sh, v);
      return;
    }
    if (t.hasAttribute('data-field-type') || t.hasAttribute('data-field-nullable')) {
      var box = t.closest('.nml-docfield');
      var name = t.getAttribute('data-field-type') || t.getAttribute('data-field-nullable');
      var typeSel = box.querySelector('[data-field-type]'), nullCb = box.querySelector('[data-field-nullable]');
      setFieldType(name, typeSel ? typeSel.value : docFields[name].type, !!(nullCb && nullCb.checked));
      return;
    }
    if (t.hasAttribute('data-attr') && sh) {
      var attr = t.getAttribute('data-attr'), spec = specFor(attr);
      var parsed = spec.strict ? { ok: true, value: t.value } : parseInput(spec, t.type === 'checkbox' ? t.checked : t.value);
      if (!parsed.ok) {
        t.classList.add('invalid');
        C.toast('Значение не подходит к типу ' + typeText(spec) + '.', true);
        return;
      }
      setAttr(sh, attr, parsed.value);
    }
  }
  function onSideKey(e) {
    var t = e.target;
    if (e.key === 'Enter' && t.hasAttribute && (t.hasAttribute('data-coord') || t.hasAttribute('data-attr'))) { e.preventDefault(); t.blur(); }
  }
  function onSourceClick(e) {
    var link = e.target.closest && e.target.closest('[data-open-variant]');
    if (!link) return;
    e.preventDefault();
    C.openFile(ctx.video, link.getAttribute('data-open-variant'), ctx.jsonsDir, ctx.productionKey);
  }

  // ------------------------------------------------------------------ вариант
  function switchVariant(variant) {
    if (variant === ctx.variant) return;
    if (!isDirty()) { load(variant); return; }
    confirmDialog('Открыть другую разметку?', 'Несохранённые изменения будут потеряны.', 'Открыть', function () { load(variant); });
  }

  // ------------------------------------------------------------------ сохранение
  function payload(target, dryRun, confirmProduction, opts) {
    opts = opts || {};
    var changes = {};
    shapes.forEach(function (sh) {
      var change = {};
      if (pointsChanged(sh)) { change.points = clonePoints(sh.current); change.shape_type = sh.shape_type; }
      if (attrsChanged(sh)) change.attributes = cloneJson(sh.attrs);
      if (Object.keys(change).length) changes[sh.index] = change;
    });
    // Передаём только заданные или изменённые в редакторе типы полей документа
    var fields = {};
    Object.keys(docFields).forEach(function (name) {
      var f = docFields[name];
      if (f.type !== 'any' && ATTRIBUTE_NAME_RE.test(name) && JSON.stringify(f) !== JSON.stringify(originalDocFields[name])) fields[name] = f;
    });
    return { video: ctx.video, jsons_dir: ctx.jsonsDir, production_key: ctx.productionKey || null,
      base_variant: ctx.variant, target_variant: target, base_version: openVersion(),
      mode: opts.mode || 'new', comment: opts.comment || '', force: !!opts.force,
      // Защита от чужих правок: файл назначения должен быть таким, каким его открыли
      expected_hash: target === ctx.variant ? (doc.file_hash || null) : null,
      changes: changes, fields: fields, dry_run: dryRun, confirm_production: !!confirmProduction };
  }
  function setSaving(busy) {
    if (busy) { ['nml-save-sidecar', 'nml-save-production', 'nml-save-current'].forEach(function (id) { el(id).disabled = true; }); }
    else renderSaveButtons();
  }
  // target: 'sidecar' | 'production'; mode для «рядом с видео»: 'new' — новая версия, 'overwrite' — в открытую версию
  function doSave(target, mode) {
    if (!doc) return;
    mode = mode || 'new';
    var unchanged = !isDirty() && !mismatches().length;
    if (unchanged && target === ctx.variant && (target === 'production' || mode === 'overwrite')) { C.toast('Нет изменений для сохранения.'); return; }
    setSaving(true);
    C.postJson(ctx.urls.save, payload(target, true)).then(function (check) {
      setSaving(false);
      var report = check.report || {}, problems = report.problems || [], conversions = report.conversions || [];
      if (problems.length) {
        infoDialog('Сохранить нельзя', '<div>Эти значения не приводятся к типу поля — исправьте их:</div><ul>'
          + problems.map(function (p) {
            return '<li>#' + p.shape_index + ' ' + esc(p.label) + ' · <code>' + esc(p.field) + '</code> = '
              + esc(shortValue(p.value)) + ', нужно: ' + esc(p.expected) + '</li>';
          }).join('') + '</ul>');
        return;
      }
      var production = target === 'production';
      var body = '';
      if (!production) {
        var what = mode === 'overwrite' ? 'Будет перезаписана версия <b>v' + openVersion() + '</b>; она станет текущей.'
          : 'Будет создана новая версия разметки рядом с видео; она станет текущей.';
        body += '<div>' + what + '</div><label class="nml-dialog-label">Комментарий к версии (необязательно)'
          + '<input type="text" class="nml-input" id="nml-save-comment" maxlength="300" autocomplete="off"></label>';
      }
      if (production) {
        body += '<div>' + (check.target.exists ? 'Будет перезаписан боевой JSON:' : 'Будет создан боевой JSON:')
          + '<br><code>' + esc(check.target.path) + '</code></div>';
      }
      if (conversions.length) {
        body += '<div style="margin-top:8px">Типы будут приведены (' + conversions.length + '):</div><ul>'
          + conversions.map(function (c) {
            return '<li>#' + c.shape_index + ' ' + esc(c.label) + ' · <code>' + esc(c.field) + '</code>: '
              + esc(shortValue(c.before)) + ' → ' + esc(shortValue(c.after)) + '</li>';
          }).join('') + '</ul>';
      }
      var title = production ? 'Записать боевой JSON?' : (mode === 'overwrite' ? 'Сохранить в v' + openVersion() + '?' : 'Сохранить новую версию?');
      confirmDialog(title, body, production ? 'Записать' : 'Сохранить', function () {
        var comment = el('nml-save-comment') ? el('nml-save-comment').value.trim() : '';
        commit(target, production, { mode: mode, comment: comment });
      });
      if (el('nml-save-comment')) el('nml-save-comment').focus();
    }).catch(function (err) { setSaving(false); C.toast(err.message, true); });
  }
  function commit(target, confirmProduction, opts) {
    opts = opts || {};
    setSaving(true);
    C.postJson(ctx.urls.save, payload(target, false, confirmProduction, opts)).then(function (res) {
      setSaving(false);
      if (!res.saved) { C.toast('Разметка не сохранена.', true); return; }
      C.toast('Сохранено: ' + res.target.name + (res.version ? ' · v' + res.version.number : ''));
      ctx.entry[target] = res.target;
      notifySaved(target, res.target);
      load(target, res.version ? res.version.number : null);
    }).catch(function (err) {
      setSaving(false);
      if (err.status !== 409) { C.toast(err.message, true); return; }
      confirmDialog('Файл изменён после открытия',
        '<div>Файл разметки изменили после того, как он открыт в редакторе (другой программой или в другом окне).</div>'
        + '<div style="margin-top:8px"><button type="button" class="nml-btn nml-btn-small" data-reload-file>Перечитать файл</button>'
        + ' <span class="muted">— правки в редакторе будут потеряны</span></div>'
        + '<div style="margin-top:8px" class="muted">«Всё равно записать» заменит изменения в файле'
        + (target === 'sidecar' ? ' (для разметки рядом с видео они сохранятся отдельной версией)' : '') + '.</div>',
        'Всё равно записать', function () { commit(target, confirmProduction, Object.assign({}, opts, { force: true })); });
    });
  }
  function notifySaved(target, location) {
    if (ctx.onSaved) ctx.onSaved(target, location);
    document.dispatchEvent(new CustomEvent('nml:saved', { detail: { video: ctx.video, variant: target, location: location } }));
  }

  // ------------------------------------------------------------------ версии
  function toggleVersions() {
    var panel = el('nml-versions');
    if (!panel.classList.contains('hidden')) { panel.classList.add('hidden'); return; }
    panel.classList.remove('hidden');
    refreshVersions();
  }
  function refreshVersions() {
    var panel = el('nml-versions');
    if (!versions) panel.innerHTML = '<div class="muted nml-versions-empty">Загрузка…</div>';
    C.getJson(ctx.urls.versions, { video: ctx.video }).then(function (d) {
      versions = d;
      renderSwitch();
      renderVersions();
    }).catch(function (err) { panel.innerHTML = '<div class="nml-error-text nml-versions-empty">' + esc(err.message) + '</div>'; });
  }
  function fmtTime(iso) {
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso || '';
    function two(n) { return (n < 10 ? '0' : '') + n; }
    return two(d.getDate()) + '.' + two(d.getMonth() + 1) + '.' + d.getFullYear() + ' ' + two(d.getHours()) + ':' + two(d.getMinutes());
  }
  // Список версий рядом с видео: звёздочка, номер, комментарий, время, «текущая» отдельным столбцом, «Сравнить».
  // Щелчок по строке делает версию текущей и открывает её.
  function renderVersions() {
    var panel = el('nml-versions');
    var list = ((versions && versions.versions) || []).slice().reverse();
    var current = versions ? versions.current : null;
    var cmp = compare ? '<div class="nml-versions-compare">' + compareSummary()
      + ' <button type="button" class="nml-btn nml-btn-small" data-compare-off>Убрать сравнение</button></div>' : '';
    if (!list.length) { panel.innerHTML = '<div class="muted nml-versions-empty">Версий пока нет: они появятся при сохранении рядом с видео.</div>'; return; }
    panel.innerHTML = cmp + '<div class="nml-versions-list">' + list.map(function (v) {
      var isCurrent = v.number === current;
      var meta = [fmtTime(v.updated !== v.created ? v.updated : v.created)];
      if (ORIGIN_LABELS[v.origin]) meta.push(ORIGIN_LABELS[v.origin]);
      return '<div class="nml-ver' + (isCurrent ? ' current' : '') + '" data-ver="' + v.number + '"'
        + ' title="' + (isCurrent ? 'Текущая версия' : 'Сделать текущей и открыть') + '">'
        + '<button type="button" class="nml-ver-pin' + (v.pinned ? ' on' : '') + '" data-pin="' + v.number + '" title="' + (v.pinned ? 'Убрать из избранного' : 'В избранное') + '">★</button>'
        + '<b class="nml-ver-n">v' + v.number + '</b>'
        + '<span class="nml-ver-comment">' + esc(v.comment || '') + '</span>'
        + '<span class="muted nml-ver-meta">' + esc(meta.join(' · ')) + '</span>'
        + '<span class="nml-ver-cur">' + (isCurrent ? 'текущая' : '') + '</span>'
        + (v.number === openVersion() ? '<span></span>'
          : '<button type="button" class="nml-btn nml-btn-small" data-compare="' + v.number + '" title="Показать контуры этой версии поверх открытой">Сравнить</button>')
        + '</div>';
    }).join('') + '</div>';
  }
  function onVersionsClick(e) {
    var t = e.target;
    if (t.closest('[data-compare-off]')) { setCompare(null); return; }
    var pin = t.closest('[data-pin]');
    if (pin) {
      var n = +pin.getAttribute('data-pin'), v = versionByNumber(n);
      C.postJson(ctx.urls.versionUpdate, { video: ctx.video, number: n, pinned: !(v && v.pinned) }).then(refreshVersions)
        .catch(function (err) { C.toast(err.message, true); });
      return;
    }
    var cmp = t.closest('[data-compare]');
    if (cmp) {
      var number = +cmp.getAttribute('data-compare');
      C.getJson(ctx.urls.markup, { video: ctx.video, variant: 'sidecar', jsons: ctx.jsonsDir, version: number }).then(function (d) {
        setCompare({ number: number, doc: d });
      }).catch(function (err) { C.toast(err.message, true); });
      return;
    }
    var row = t.closest('[data-ver]');
    if (row) { el('nml-versions').classList.add('hidden'); makeCurrent(+row.getAttribute('data-ver')); }
  }
  function versionByNumber(n) {
    return ((versions && versions.versions) || []).filter(function (v) { return v.number === n; })[0] || null;
  }
  // Версия становится текущей (файл рядом с видео — равен ей; изменённый вне версий файл сначала
  // сохраняется отдельной версией) и открывается в редакторе
  function makeCurrent(n) {
    if (n === openVersion() && n === (versions && versions.current)) return;
    function run() {
      C.postJson(ctx.urls.versionCurrent, { video: ctx.video, number: n }).then(function () {
        C.toast('Текущая версия — v' + n);
        notifySaved('sidecar', ctx.entry.sidecar);
        load('sidecar', null);
      }).catch(function (err) { C.toast(err.message, true); });
    }
    if (!isDirty()) { run(); return; }
    confirmDialog('Сделать v' + n + ' текущей?', 'Несохранённые изменения в редакторе будут потеряны.', 'Сделать текущей', run);
  }
  // Сравнение: контуры другой версии пунктиром поверх кадра и сводка отличий
  function setCompare(value) {
    compare = value;
    drawCompare();
    renderVersions();
  }
  function drawCompare() {
    if (!svg) return;
    var old = svg.querySelector('.nml-ghost');
    if (old) old.remove();
    if (!compare) return;
    var g = document.createElementNS(SVGNS, 'g');
    g.setAttribute('class', 'nml-ghost');
    (compare.doc.shapes || []).forEach(function (s) {
      if ((s.points || []).length) g.appendChild(C.createGeom(s.shape_type, s.points, 'nml-ghost-geom'));
    });
    svg.insertBefore(g, handlesLayer);
  }
  function compareSummary() {
    var other = compare.doc.shapes || [], mine = shapes, byIndex = {};
    other.forEach(function (s) { byIndex[s.index] = s; });
    var changed = [];
    mine.forEach(function (a) {
      var b = byIndex[a.index], what = [];
      if (!b) return;
      if (JSON.stringify(a.current) !== JSON.stringify(b.points) || a.shape_type !== b.shape_type) what.push('форма');
      if (JSON.stringify(a.attrs) !== JSON.stringify(b.attributes || {})) what.push('атрибуты');
      if (what.length) changed.push('#' + a.index + ' ' + what.join(', '));
    });
    var parts = ['Сравнение с v' + compare.number + ' (пунктир)'];
    if (other.length !== mine.length) parts.push('объектов там ' + other.length + ', здесь ' + mine.length);
    parts.push(changed.length ? 'отличаются: ' + changed.join('; ') : (other.length === mine.length ? 'объекты совпадают' : ''));
    return esc(parts.filter(Boolean).join(' · '));
  }

  // ------------------------------------------------------------------ диалог
  function confirmDialog(title, bodyHtml, okText, onOk) {
    el('nml-dialog-title').textContent = title;
    el('nml-dialog-body').innerHTML = bodyHtml;
    el('nml-dialog-error').textContent = '';
    el('nml-dialog-ok').textContent = okText || 'OK';
    el('nml-dialog-cancel').classList.remove('hidden');
    dialogOk = onOk;
    dialogValidate = null;
    el('nml-dialog').classList.remove('hidden');
    el('nml-dialog-ok').focus();
  }
  // Диалог с формой: validate возвращает текст ошибки (диалог остаётся открытым) или ''
  function formDialog(title, bodyHtml, okText, validate, onOk) {
    confirmDialog(title, bodyHtml, okText, onOk);
    dialogValidate = validate;
  }
  function submitDialog() {
    if (dialogValidate) {
      var error = dialogValidate();
      if (error) { el('nml-dialog-error').textContent = error; return; }
    }
    var fn = dialogOk;
    hideDialog();
    if (fn) fn();
  }
  function infoDialog(title, bodyHtml) {
    confirmDialog(title, bodyHtml, 'Понятно', null);
    el('nml-dialog-cancel').classList.add('hidden');
  }
  function hideDialog() { el('nml-dialog').classList.add('hidden'); dialogOk = null; dialogValidate = null; }

  // ------------------------------------------------------------------ init
  function init() {
    if (modal) return;
    modal = el('nml-editor'); overlay = el('nml-editor-overlay');
    if (!modal) return;
    el('nml-editor-x').addEventListener('click', requestClose);
    el('nml-editor-cancel').addEventListener('click', requestClose);
    overlay.addEventListener('click', requestClose);
    el('nml-save-sidecar').addEventListener('click', function () { doSave('sidecar', 'new'); });
    el('nml-save-current').addEventListener('click', saveCurrent);
    el('nml-save-production').addEventListener('click', function () { doSave('production'); });
    el('nml-versions').addEventListener('click', function (e) { e.stopPropagation(); onVersionsClick(e); });
    modal.addEventListener('click', function () { el('nml-versions').classList.add('hidden'); });
    el('nml-dialog-body').addEventListener('click', function (e) {
      if (!e.target.closest('[data-reload-file]')) return;
      hideDialog();
      load(ctx.variant, ctx.version);
    });
    el('nml-dialog-cancel').addEventListener('click', hideDialog);
    el('nml-dialog-ok').addEventListener('click', submitDialog);
    el('nml-dialog').addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && e.target.tagName === 'INPUT') { e.preventDefault(); submitDialog(); }
    });
    el('nml-editor-source').addEventListener('click', onSourceClick);
    var side = el('nml-editor-side');
    side.addEventListener('click', onSideClick);
    side.addEventListener('change', onSideChange);
    side.addEventListener('keydown', onSideKey);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();

  return { open: open, close: close, isOpen: isOpen };
})();
