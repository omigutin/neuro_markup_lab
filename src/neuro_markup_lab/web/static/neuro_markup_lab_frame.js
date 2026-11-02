// Кадр видео с разметкой — модуль для любой страницы (своей и чужой, например сборщика датасета):
// первый кадр, разметка поверх, переключатель «Боевая | Рядом с видео», карандаш редактора и,
// по желанию, панель справа: файлы разметки со ссылками, выбор боевой вручную, сведения о разметке.
//
//   var frame = NML.frame.mount(element, {
//     video: 'D:/video/plant_cam5.avi',  // путь к видео на компьютере сервера (обязательно)
//     jsonsDir: 'D:/markup/plant',        // каталог боевых JSON; нет — только «рядом с видео»
//     productionKey: 'plant_cam5',        // боевая, выбранная вручную; нет — подбирается
//     variant: 'sidecar',                 // что показать; нет — «рядом с видео», если есть, иначе боевую
//     entry: { sidecar, production },     // уже известные файлы разметки; нет — запрашиваются
//     details: true,                      // панель сведений справа от кадра
//     editable: true,                     // карандаш редактора
//     onProductionKey: function (key) {}, // боевая выбрана вручную (key) или сброшена (null)
//     onEntry: function (entry) {},       // обновились сведения о файлах разметки
//     onVariant: function (variant) {},   // переключён показываемый вариант
//     onSaved: function (variant, location) {},
//   });
//   frame.refresh(); frame.destroy();
//
// Нужны neuro_markup_lab.css, _shapes.js и _editor.js (редактор открывается карандашом).
window.NML = window.NML || {};
NML.frame = (function () {
  var C = NML.common, esc = C.esc;
  // Адреса API по умолчанию (от корня редактора)
  var DEFAULT_URLS = { markup: 'api/markup', frame: 'frame', locations: 'api/locations' };
  var VARIANTS = ['sidecar', 'production'];

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

    // ---- отрисовка
    function render() {
      if (!state.alive || !state.entry) return;
      C.renderSwitch(switchHost, state.entry, state.variant, pickVariant);
      if (editBtn) {
        editBtn.disabled = !state.variant;
        editBtn.title = state.variant ? 'Редактировать разметку' : 'Нет ни JSON рядом с видео, ни боевого JSON';
      }
      var old = box.querySelector('.nml-preview-svg');
      if (old) old.remove();
      var svg = state.doc ? C.buildOverlay(state.doc) : null;
      if (svg) box.insertBefore(svg, switchHost);
      if (info) renderInfo();
    }
    function fileRow(variant) {
      var loc = state.entry[variant] || {};
      var value = loc.exists
        ? '<a href="#" class="nml-link" data-open-variant="' + variant + '" title="Открыть в программе по умолчанию">' + esc(loc.path) + '</a>'
        : '<span class="muted">' + esc(loc.path ? 'нет файла ' + loc.name : (loc.reason || '—')) + '</span>';
      var actions = '';
      if (variant === 'production' && jsonsDir) {
        actions = '<div class="nml-info-actions"><button type="button" class="nml-btn nml-btn-small" data-choose-production>Выбрать файл…</button>'
          + (loc.manual ? '<button type="button" class="nml-btn nml-btn-small" data-auto-production title="Вернуть подбор по каталогу">Подбирать автоматически</button>' : '')
          + '</div>';
      }
      var mark = loc.manual ? ' <span class="nml-tag">выбрана вручную</span>' : '';
      return '<div class="nml-info-file"><div class="nml-info-label">' + esc(C.VARIANT_LABELS[variant]) + mark + '</div>'
        + '<div class="nml-info-value">' + value + '</div>' + actions + '</div>';
    }
    function docSection() {
      if (!state.variant) return '<div class="muted">Разметки нет: ни рядом с видео, ни боевой.</div>';
      if (state.error) return '<div class="nml-error-text">Разметка не открыта: ' + esc(state.error) + '</div>';
      var doc = state.doc;
      if (!doc) return '<div class="muted">Загрузка…</div>';
      var shapes = doc.shapes || [], labels = {}, order = [];
      shapes.forEach(function (s) {
        var label = (s.attributes || {}).label;
        label = label == null || label === '' ? '(без метки)' : String(label);
        if (!(label in labels)) { labels[label] = 0; order.push(label); }
        labels[label] += 1;
      });
      var rows = [['Фигур', shapes.length + (order.length ? ': ' + order.map(function (l) { return l + ' ' + labels[l]; }).join(', ') : '')]];
      if (doc.image_width && doc.image_height) rows.push(['Кадр', doc.image_width + '×' + doc.image_height]);
      if (doc.version) rows.push(['LabelMe', String(doc.version)]);
      var report = doc.report || {}, conv = (report.conversions || []).length, probs = (report.problems || []).length;
      var check = !conv && !probs ? '<span class="nml-ok-text">типы полей в порядке</span>'
        : (probs ? '<span class="nml-error-text">' + probs + ' ' + plural(probs, 'значение', 'значения', 'значений') + ' не привести — правка в редакторе</span>' : '')
          + (probs && conv ? '<br>' : '')
          + (conv ? '<span class="nml-warn-text">' + conv + ' ' + plural(conv, 'значение', 'значения', 'значений') + ' будет приведено при сохранении</span>' : '');
      rows.push(['Проверка', check]);
      return rows.map(function (r) {
        return '<div class="nml-kv"><span>' + esc(r[0]) + '</span><div>' + (r[0] === 'Проверка' ? r[1] : esc(r[1])) + '</div></div>';
      }).join('');
    }
    function renderInfo() {
      var e = state.entry;
      var video = '<div class="nml-kv"><span>Файл</span><div class="nml-info-path">' + esc(o.video) + '</div></div>'
        + (e.factory ? '<div class="nml-kv"><span>Производство</span><div>' + esc(e.factory) + '</div></div>' : '');
      info.innerHTML = '<section class="nml-info-sec"><div class="nml-info-h">Файлы разметки</div>' + VARIANTS.map(fileRow).join('') + '</section>'
        + '<section class="nml-info-sec"><div class="nml-info-h">Разметка' + (state.variant ? ': ' + esc(C.VARIANT_LABELS[state.variant].toLowerCase()) : '') + '</div>' + docSection() + '</section>'
        + '<section class="nml-info-sec"><div class="nml-info-h">Видео</div>' + video + '</section>';
    }

    // ---- действия
    function pickVariant(variant) {
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
      var link = t.closest('[data-open-variant]');
      if (link) { e.preventDefault(); e.stopPropagation(); C.openFile(o.video, link.getAttribute('data-open-variant'), jsonsDir, state.key); return; }
      if (t.closest('[data-choose-production]')) { e.stopPropagation(); chooseProduction(); return; }
      if (t.closest('[data-auto-production]')) { e.stopPropagation(); autoProduction(); }
    }
    host.addEventListener('click', onClick);

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
      destroy: function () { state.alive = false; host.removeEventListener('click', onClick); host.innerHTML = ''; host.classList.remove('nml-frame'); },
      get variant() { return state.variant; },
      get entry() { return state.entry; },
      get productionKey() { return state.key; },
    };
  }

  return { mount: mount };
})();
