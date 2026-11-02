// Общее для страницы и редактора NeuroMarkupLab: адреса API, SVG-геометрия фигур LabelMe,
// подписи вариантов разметки, сообщения. Только представление: типы и сохранение решает сервер.
window.NML = window.NML || {};
NML.common = (function () {
  var SVGNS = 'http://www.w3.org/2000/svg';
  var ROOT = '/neuro-markup-lab';
  // Подписи вариантов разметки
  var VARIANT_LABELS = { production: 'Боевая', sidecar: 'Рядом с видео' };
  // Порядок кнопок переключателя вариантов
  var VARIANTS = ['production', 'sidecar'];
  // Сколько показывать сообщение, мс
  var TOAST_MS = 3500;

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function query(params) {
    return Object.keys(params).map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(params[k] == null ? '' : params[k]); }).join('&');
  }
  function frameUrl(video, full) { return ROOT + '/frame?' + query({ video: video, full: full ? 1 : '' }); }
  // GET JSON; ответ {ok:false,error} — reject с текстом ошибки
  function getJson(path, params) {
    return fetch(ROOT + path + '?' + query(params)).then(parseJson);
  }
  function postJson(path, body) {
    return fetch(ROOT + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(parseJson);
  }
  function parseJson(r) {
    return r.json().catch(function () { return { ok: false, error: 'HTTP ' + r.status }; }).then(function (d) {
      if (!r.ok || !d || d.ok === false) throw new Error((d && d.error) || ('HTTP ' + r.status));
      return d;
    });
  }

  // ---- геометрия
  function geomTag(type, n) {
    if (type === 'rectangle' && n >= 2) return 'rect';
    if (type === 'circle' && n >= 2) return 'circle';
    if (n === 1) return 'circle';
    return (type === 'linestrip' || type === 'line') ? 'polyline' : 'polygon';
  }
  function createGeom(type, points, cls) {
    var el = document.createElementNS(SVGNS, geomTag(type, points.length));
    el.setAttribute('class', cls);
    if (points.length === 1) el.setAttribute('r', 6);
    updateGeom(el, type, points);
    return el;
  }
  function updateGeom(el, type, pts) {
    if (type === 'rectangle' && pts.length >= 2) {
      var x1 = pts[0][0], y1 = pts[0][1], x2 = pts[1][0], y2 = pts[1][1];
      el.setAttribute('x', Math.min(x1, x2)); el.setAttribute('y', Math.min(y1, y2));
      el.setAttribute('width', Math.abs(x2 - x1)); el.setAttribute('height', Math.abs(y2 - y1));
    } else if (type === 'circle' && pts.length >= 2) {
      el.setAttribute('cx', pts[0][0]); el.setAttribute('cy', pts[0][1]);
      el.setAttribute('r', Math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]));
    } else if (pts.length === 1) {
      el.setAttribute('cx', pts[0][0]); el.setAttribute('cy', pts[0][1]);
    } else {
      el.setAttribute('points', pts.map(function (p) { return p[0] + ',' + p[1]; }).join(' '));
    }
  }
  // Фигура видна, если в атрибутах нет "show": false
  function isVisible(attributes) { return !attributes || attributes.show !== false; }

  // Наложение разметки на кадр карточки: svg в системе координат кадра
  function buildOverlay(doc) {
    var w = doc.image_width, h = doc.image_height;
    if (!w || !h) return null;
    var svg = document.createElementNS(SVGNS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('class', 'nml-preview-svg');
    (doc.shapes || []).forEach(function (s) {
      if (!isVisible(s.attributes) || !(s.points || []).length) return;
      svg.appendChild(createGeom(s.shape_type, s.points, 'nml-preview-shape'));
    });
    return svg;
  }

  // Переключатель вариантов: кнопки «Боевая | Рядом с видео»; отсутствующий вариант неактивен
  function renderSwitch(host, entry, active, onPick) {
    host.innerHTML = VARIANTS.map(function (v) {
      var loc = entry[v] || {};
      var title = loc.exists ? (loc.path || loc.name) : (loc.reason || 'Файла нет' + (loc.name ? ': ' + loc.name : ''));
      return '<button type="button" data-variant="' + v + '"' + (v === active ? ' class="active"' : '')
        + (loc.exists ? '' : ' disabled') + ' title="' + esc(title) + '">' + esc(VARIANT_LABELS[v]) + '</button>';
    }).join('');
    host.onclick = function (e) {
      var b = e.target.closest && e.target.closest('button[data-variant]');
      if (b && !b.disabled) { e.stopPropagation(); onPick(b.getAttribute('data-variant')); }
    };
  }

  // Открыть JSON разметки видео в программе по умолчанию (на этом компьютере)
  function openFile(video, variant, jsonsDir) {
    postJson('/api/open-file', { video: video, variant: variant, jsons_dir: jsonsDir || '' })
      .then(function (d) { toast('Открываю ' + d.path); })
      .catch(function (err) { toast('Не удалось открыть файл: ' + err.message, true); });
  }

  var toastEl;
  function toast(text, isError) {
    if (!toastEl) { toastEl = document.createElement('div'); toastEl.className = 'nml-msg'; document.body.appendChild(toastEl); }
    toastEl.textContent = text;
    toastEl.classList.toggle('error', !!isError);
    toastEl.classList.add('show');
    clearTimeout(toast._t); toast._t = setTimeout(function () { toastEl.classList.remove('show'); }, TOAST_MS);
  }

  return {
    SVGNS: SVGNS, VARIANT_LABELS: VARIANT_LABELS, esc: esc, frameUrl: frameUrl, getJson: getJson, postJson: postJson,
    createGeom: createGeom, updateGeom: updateGeom, isVisible: isVisible, buildOverlay: buildOverlay,
    renderSwitch: renderSwitch, toast: toast, openFile: openFile,
  };
})();
