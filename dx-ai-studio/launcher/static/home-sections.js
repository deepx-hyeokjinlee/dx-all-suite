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
  var _models = null;

  function _paintCount() {
    var card = document.querySelector('.orbital-card[data-app="zoo"] .card-desc');
    if (!card || !_counts) return;
    card.removeAttribute('data-i18n');   // a live number is not a dictionary key
    card.textContent = _counts.models + ' ' + _t('models') + ' · ' +
      _counts.tasks + ' ' + _t('tasks');
  }

  /* 어떤 모델을 보여줄지. 제일 빠른 것만 뽑으면 super-resolution 이 19,000
     FPS 로 표를 독차지하는데, 그건 이 칩으로 무엇을 할 수 있는지에 대한
     대답이 아니다. task 당 하나씩, 그 task 에서 가장 빠른 것을 고른다 —
     사람들이 실제로 돌리는 일 다섯 가지가 각각 얼마나 나오는지가 답이다. */
  var HEADLINE_TASKS = [
    'object_detection', 'pose_estimation', 'semantic_segmentation',
    'face_detection', 'classification'
  ];

  function _fmt(n) {
    return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function _paintPerf(models) {
    var block = $('measured');
    var body = $('perfRows');
    if (!block || !body) return;

    var best = {};
    var measured = 0;
    var tasks = {};
    models.forEach(function (m) {
      var d = m.display || {};
      var fps = (m.performance || {}).fps;
      if (d.task) tasks[d.task] = 1;
      if (!fps) return;
      measured += 1;
      if (HEADLINE_TASKS.indexOf(d.task) === -1) return;
      if (!best[d.task] || fps > best[d.task].fps) {
        best[d.task] = { fps: fps, name: d.class_name || d.name || m.id, id: m.id, task: d.task };
      }
    });

    var rows = HEADLINE_TASKS.map(function (t) { return best[t]; }).filter(Boolean);
    if (!rows.length) return;

    body.innerHTML = '';
    rows.forEach(function (r) {
      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td class="perf-name">' + r.name + '</td>' +
        '<td class="perf-task">' + r.task.replace(/_/g, ' ') + '</td>' +
        '<td class="perf-fps"><b>' + _fmt(r.fps) + '</b> FPS</td>';
      tr.addEventListener('click', function () {
        window.location.href = '/zoo/#model=' + encodeURIComponent(r.id);
      });
      body.appendChild(tr);
    });

    var note = $('measuredCount');
    if (note) {
      note.textContent = _fmt(measured) + ' ' + _t('measured') + ' · ' +
        Object.keys(tasks).length + ' ' + _t('tasks');
    }
    block.hidden = false;
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
        _models = models;
        _paintPerf(models);
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
        /* "start →" 여덟 개는 행동 유도가 여덟 개라는 뜻이고, 그러면 아무것도
           행동 유도가 아니다. 행에는 이미 chevron 이 있어 누를 수 있다는 걸
           말한다. 그러니 기본값(꺼져 있음)은 아무 말도 하지 않고, 기본이
           아닌 것 — 돌고 있는 것 — 만 말한다. */
        line.textContent = alive ? _t('Running') : '';
        line.className = 'card-state' + (alive ? ' is-alive' : '');
      }
      if (alive) {
        var name = card.querySelector('.orbital-name');
        up.push(name ? name.textContent.trim() : card.dataset.app);
      }
    });

    /* 0 은 셀 것이 없다는 뜻이라 세지 않는다. */
    var count = $('moduleUpCount');
    if (count) {
      count.textContent = up.length
        ? up.length + ' ' + _t('of') + ' 8 ' + _t('running')
        : '';
    }

    var list = $('wsRunning');
    if (!list) return;
    /* 없음을 알리기 위해 패널 하나를 통째로 쓰지 않는다. 돌고 있는 것이
       생기면 그때 나타난다. */
    var panel = list.closest ? list.closest('.ws-panel') : null;
    if (panel) panel.hidden = !up.length;
    list.innerHTML = '';
    if (!up.length) return;
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
        if (_models) _paintPerf(_models);
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
