/* ── Home sections ────────────────────────────────────────────
 *
 * Fills the model row and the module cards' state line.
 *
 * Neither adds a source of truth. The models come from the catalogue the Model
 * Zoo already serves; the state comes from the health poll `checkHealth()`
 * already runs. A second poller would mean two answers to "is this module up",
 * and they would disagree.
 */
(function () {
  'use strict';

  var ns = window.DXLauncher = window.DXLauncher || {};

  /* Which tasks lead. The catalogue holds 348 entries across 15 tasks; a row of
     five has to be a choice, and these are the ones the demos and the docs are
     built around. */
  var FEATURED_TASKS = [
    'object_detection', 'pose_estimation', 'semantic_segmentation',
    'face_detection', 'classification'
  ];

  function $(id) { return document.getElementById(id); }
  function _t(key) {
    return (window.DXI18n && window.DXI18n.T) ? window.DXI18n.T(key) : key;
  }

  function _pick(models) {
    var out = [];
    FEATURED_TASKS.forEach(function (task) {
      for (var i = 0; i < models.length; i++) {
        var d = models[i].display || {};
        if (d.task === task) { out.push(models[i]); return; }
      }
    });
    /* Fewer tasks present than slots — top up rather than ship a short row. */
    for (var i = 0; i < models.length && out.length < 5; i++) {
      if (out.indexOf(models[i]) === -1) out.push(models[i]);
    }
    return out.slice(0, 5);
  }

  function _card(model) {
    var d = model.display || {};
    var spec = model.specification || {};
    var art = model.artifacts || {};
    var el = document.createElement('a');
    el.className = 'model-card';
    el.href = '/zoo/#model=' + encodeURIComponent(model.id);

    var badges = '';
    if (d.category_label) {
      badges += '<span class="mb mb-task">' + d.category_label + '</span>';
    }
    if (art.qpro_dxnn) badges += '<span class="mb mb-q">Q-Pro</span>';
    else if (art.qlite_dxnn) badges += '<span class="mb mb-q">Q-Lite</span>';

    el.innerHTML =
      '<span class="model-thumb" aria-hidden="true"></span>' +
      '<span class="model-body">' +
        '<span class="model-name">' + (d.class_name || d.name || model.id) + '</span>' +
        '<span class="model-badges">' + badges + '</span>' +
        '<span class="model-spec">' + (spec.input_resolution || '') + '</span>' +
      '</span>';
    return el;
  }

  /* Held so a language change can redraw without going back to the zoo. */
  var _models = null;

  function _paint(models) {
    var row = $('homeModelRow');
    if (!row) return;
    row.className = 'model-row';
    row.innerHTML = '';
    _pick(models).forEach(function (m) { row.appendChild(_card(m)); });
    var note = $('modelCount');
    if (note) {
      var tasks = {};
      models.forEach(function (m) {
        var t = (m.display || {}).task;
        if (t) tasks[t] = 1;
      });
      note.textContent = models.length + ' ' + _t('models') + ' · ' +
        Object.keys(tasks).length + ' ' + _t('tasks');
    }
  }

  function _empty() {
    var row = $('homeModelRow');
    if (!row) return;
    /* The zoo has not started. Say so rather than showing an empty shelf —
       and drop the five-column grid, or the sentence wraps two words wide in
       the first of five tracks. */
    row.className = 'model-row is-empty';
    row.innerHTML = '<p class="section-empty">' +
      _t('Start DX Model Zoo to browse the catalogue') + '</p>';
  }

  function renderModels() {
    var row = $('homeModelRow');
    if (!row) return;
    if (_models) { _paint(_models); return; }
    fetch('/zoo/api/catalog').then(function (r) { return r.json(); })
      .then(function (data) {
        var models = (data && data.models) || (Array.isArray(data) ? data : []);
        if (!models.length) throw new Error('empty catalogue');
        _models = models;
        _paint(models);
      })
      .catch(_empty);
  }

  /* Reads what the existing poll already fetched — no second request. */
  var STATE_LABEL = { alive: 'ready', dead: 'not running' };

  function refreshModuleState() {
    var health = ns._healthStatus;
    if (!health) return;
    var map = {
      app: 'app', stream: 'stream', zoo: 'zoo', compiler: 'compiler',
      planner: 'planner', benchmark: 'benchmark', dx_monitor: 'monitor', agent: 'agent'
    };
    document.querySelectorAll('.orbital-card[data-app]').forEach(function (card) {
      var line = card.querySelector('[data-role="state"]');
      if (!line) return;
      var key = map[card.dataset.app] || card.dataset.app;
      var entry = health[key];
      var alive = !!(entry && entry.alive);
      line.textContent = _t(STATE_LABEL[alive ? 'alive' : 'dead']);
      line.className = 'card-state' + (alive ? ' is-alive' : '');
    });
  }

  function init() {
    renderModels();
    refreshModuleState();
    /* Piggyback on the health poll's cadence instead of adding one. */
    setInterval(refreshModuleState, 5000);
    /* Both rows are built in JS, so data-i18n never reaches them: a language
       change has to redraw. The model row repaints from the held catalogue
       rather than asking the zoo again. */
    if (window.DXI18n && DXI18n.onLangChange) {
      DXI18n.onLangChange(function () {
        renderModels();
        refreshModuleState();
      });
    }
  }

  ns.renderHomeModels = renderModels;
  ns.refreshModuleState = refreshModuleState;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
