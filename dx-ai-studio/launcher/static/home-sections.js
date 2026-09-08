/* ── Workspace state ──────────────────────────────────────────
 *
 * Fills the two things on the home that are facts rather than layout: what the
 * catalogue holds, and which modules are up.
 *
 * Neither adds a source of truth. The count comes from the catalogue the Model
 * Zoo already serves; the state comes from the health poll `checkHealth()`
 * already runs. A second poller would mean two answers to "is this module up",
 * and they would eventually disagree.
 *
 * This used to render a five-across model row in a Models section. The section
 * is gone — the home is a workspace, and 348 models belong in the module that
 * exists to browse them. What survives is the one number worth seeing from the
 * front door, on the card that opens that module.
 */
(function () {
  'use strict';

  var ns = window.DXLauncher = window.DXLauncher || {};

  /* card data-app → the key checkHealth() files it under */
  var HEALTH_KEY = {
    app: 'app', stream: 'stream', zoo: 'zoo', compiler: 'compiler',
    planner: 'planner', benchmark: 'benchmark', dx_monitor: 'monitor', agent: 'agent'
  };

  function $(id) { return document.getElementById(id); }
  function _t(key) {
    return (window.DXI18n && window.DXI18n.T) ? window.DXI18n.T(key) : key;
  }

  /* ── the catalogue's size, on the card that opens it ─────── */

  var _counts = null;

  function _paintCount() {
    var card = document.querySelector('.orbital-card[data-app="zoo"] .card-desc');
    if (!card || !_counts) return;
    card.removeAttribute('data-i18n');   // a live number is not a dictionary key
    card.textContent = _counts.models + ' ' + _t('models') + ' · ' +
      _counts.tasks + ' ' + _t('tasks');
  }

  function loadCatalogueSize() {
    if (_counts) { _paintCount(); return; }
    fetch('/zoo/api/catalog').then(function (r) { return r.json(); })
      .then(function (data) {
        var models = (data && data.models) || (Array.isArray(data) ? data : []);
        if (!models.length) return;
        var tasks = {};
        models.forEach(function (m) {
          var t = (m.display || {}).task;
          if (t) tasks[t] = 1;
        });
        _counts = { models: models.length, tasks: Object.keys(tasks).length };
        _paintCount();
      })
      .catch(function () {
        /* The zoo is not running. The card keeps the description it shipped
           with, which is true whether or not the server is up. */
      });
  }

  /* ── which modules are up ────────────────────────────────── */

  function refreshModuleState() {
    var health = ns._healthStatus;
    if (!health) return;

    var up = [];
    document.querySelectorAll('.orbital-card[data-app]').forEach(function (card) {
      var key = HEALTH_KEY[card.dataset.app] || card.dataset.app;
      var alive = !!(health[key] && health[key].alive);
      card.classList.toggle('is-up', alive);
      var line = card.querySelector('[data-role="state"]');
      if (line) {
        line.textContent = _t(alive ? 'ready' : 'start');
        line.className = 'card-state' + (alive ? ' is-alive' : '');
      }
      if (alive) {
        var name = card.querySelector('.orbital-name');
        up.push(name ? name.textContent.trim() : card.dataset.app);
      }
    });

    var count = $('moduleUpCount');
    if (count) {
      count.textContent = up.length + ' ' + _t('of') + ' 8 ' + _t('running');
    }

    var list = $('wsRunning');
    if (!list) return;
    list.innerHTML = '';
    if (!up.length) {
      var none = document.createElement('li');
      none.className = 'is-none';
      /* "Nothing running" is the state this app opens in, so say what to do
         about it rather than reporting a failure. */
      none.textContent = _t('nothing yet — pick a module');
      list.appendChild(none);
      return;
    }
    up.forEach(function (name) {
      var li = document.createElement('li');
      li.textContent = name;
      list.appendChild(li);
    });
  }

  function init() {
    loadCatalogueSize();
    refreshModuleState();
    /* Piggyback on the health poll's cadence instead of adding one. */
    setInterval(refreshModuleState, 5000);
    /* Both are written in JS, so data-i18n never reaches them: a language
       change has to redraw. The count repaints from the held numbers rather
       than asking the zoo again. */
    if (window.DXI18n && DXI18n.onLangChange) {
      DXI18n.onLangChange(function () {
        _paintCount();
        refreshModuleState();
      });
    }
  }

  ns.refreshModuleState = refreshModuleState;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
