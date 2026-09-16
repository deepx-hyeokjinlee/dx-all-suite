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

  /* 각 모듈이 자기 숫자를 든다. 여덟 행이 이름 + 산문 한 줄로만 되어 있으면 서로
     구별되지 않아 목록이 한 덩어리로 읽힌다.

     모듈마다 함수를 한 벌씩 두지 않는다 — 다음 모듈이 생길 때 또 한 벌이 늘고,
     그건 이 저장소에서 이미 두 번 고친 모양이다. 응답 모양은 제각각이라 파싱은
     각자 갖되(`pick`), 그리는 일은 _paintFacts 한 곳에서 한다.

     compiler 와 planner 는 없다. 셀 API 가 없고(각각 listdir/mkdir, hb 뿐),
     숫자를 붙이자고 엔드포인트를 만드는 것은 이 작업이 아니다. 그 둘은 출하 시
     산문을 유지한다 — 비대칭을 그대로 두는 편이 정직하다.
     계약: tests/launcher/test_home_module_facts.py */
  var MODULE_FACTS = [
    { app: 'zoo', url: '/zoo/api/catalog', pick: function (d) {
        var models = (d && d.models) || (Array.isArray(d) ? d : []);
        if (!models.length) return null;
        var tasks = {};
        models.forEach(function (m) { var t = (m.display || {}).task; if (t) tasks[t] = 1; });
        _counts = { models: models.length, tasks: Object.keys(tasks).length };
        _models = models;
        _paintPerf(models);
        return [[models.length, 'models'], [Object.keys(tasks).length, 'tasks']];
      } },
    { app: 'app', url: '/app/api/demos', pick: function (d) {
        var demos = (d && d.demos) || [];
        if (!demos.length) return null;
        var groups = {};
        demos.forEach(function (x) { if (x.group) groups[x.group] = 1; });
        return [[demos.length, 'demos'], [Object.keys(groups).length, 'groups']];
      } },
    { app: 'stream', url: '/stream/api/demos', pick: function (d) {
        var n = Array.isArray(d) ? d.length : 0;
        return n ? [[n, 'demos']] : null;
      } },
    { app: 'agent', url: '/agent/api/agent/showcases', pick: function (d) {
        var n = ((d && d.showcases) || []).length;
        return n ? [[n, 'showcases']] : null;
      } },
    { app: 'benchmark', url: '/benchmark/api/results', pick: function (d) {
        var rows = Array.isArray(d) ? d : [];
        if (!rows.length) return null;
        var runs = 0;
        rows.forEach(function (r) { runs += ((r && r.runs) || []).length; });
        return [[rows.length, 'platforms'], [runs, 'runs']];
      } },
    { app: 'dx_monitor', url: '/dx_monitor/api/hw_status', pick: function (d) {
        var npu = ((d && d.npus) || [])[0];
        if (!npu) return null;
        var out = [];
        if (npu.cores) out.push([npu.cores, 'cores']);
        var temps = npu.temperatures || [];
        if (temps.length) {
          out.push([Math.round(Math.max.apply(null, temps)) + '\u00B0C', '']);
        }
        return out.length ? out : null;
      } },
  ];

  /* 그린 값은 언어가 바뀌면 다시 그려야 한다 (JS 로 쓰므로 data-i18n 이 닿지 않는다). */
  var _facts = {};

  function _paintFacts() {
    MODULE_FACTS.forEach(function (f) {
      var parts = _facts[f.app];
      if (!parts) return;
      var card = document.querySelector('.orbital-card[data-app="' + f.app + '"] .card-desc');
      if (!card) return;
      card.removeAttribute('data-i18n');   // a live number is not a dictionary key
      card.textContent = parts.map(function (p) {
        return p[1] ? p[0] + ' ' + _t(p[1]) : String(p[0]);
      }).join(' \u00B7 ');
    });
  }

  function _paintCount() { _paintFacts(); }

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

  /* 지금 걸린 필터. 기본(둘 다 비어 있음)은 예전과 같은 화면이다. */
  var _perfQuery = '';
  var _perfTask = '';
  var PERF_LIMIT = 8;

  function _perfRowsFor(models) {
    var q = _perfQuery.trim().toLowerCase();
    if (!q && !_perfTask) {
      /* 기본: task 당 하나씩, 그 task 에서 가장 빠른 것. 제일 빠른 것만 뽑으면
         super-resolution 이 표를 독차지하는데 그건 이 칩으로 무엇을 할 수 있는지에
         대한 대답이 아니다. */
      var best = {};
      models.forEach(function (m) {
        var d = m.display || {};
        var fps = (m.performance || {}).fps;
        if (!fps || HEADLINE_TASKS.indexOf(d.task) === -1) return;
        if (!best[d.task] || fps > best[d.task].fps) {
          best[d.task] = { fps: fps, name: d.class_name || d.name || m.id, id: m.id, task: d.task };
        }
      });
      return HEADLINE_TASKS.map(function (t) { return best[t]; }).filter(Boolean);
    }
    /* 거르는 중에는 task 당 하나로 줄이지 않는다 — "내 모델이 몇 FPS 인가" 가
       질문이므로 같은 task 안의 여러 개를 비교할 수 있어야 한다. */
    var hits = [];
    models.forEach(function (m) {
      var d = m.display || {};
      var fps = (m.performance || {}).fps;
      if (!fps) return;
      if (_perfTask && d.task !== _perfTask) return;
      if (q) {
        var hay = ((d.class_name || '') + ' ' + (d.name || '') + ' ' + m.id).toLowerCase();
        if (hay.indexOf(q) === -1) return;
      }
      hits.push({ fps: fps, name: d.class_name || d.name || m.id, id: m.id, task: d.task });
    });
    hits.sort(function (a, b) { return b.fps - a.fps; });
    return hits.slice(0, PERF_LIMIT);
  }

  function _paintPerfRows(models) {
    var body = $('perfRows');
    var empty = $('measuredEmpty');
    if (!body) return;
    var rows = _perfRowsFor(models);
    body.innerHTML = '';
    if (empty) empty.hidden = rows.length > 0;
    rows.forEach(function (r) {
      var tr = document.createElement('tr');
      tr.dataset.modelId = r.id;
      tr.innerHTML =
        '<td class="perf-name">' + r.name + '</td>' +
        '<td class="perf-task">' + r.task.replace(/_/g, ' ') + '</td>' +
        '<td class="perf-fps"><b>' + _fmt(r.fps) + '</b> FPS</td>';
      tr.addEventListener('click', function () {
        window.location.href = '/zoo/#model=' + encodeURIComponent(r.id);
      });
      body.appendChild(tr);
    });
  }

  function _paintPerfCats(models) {
    var box = $('measuredCats');
    if (!box) return;
    var counts = {};
    models.forEach(function (m) {
      var d = m.display || {};
      if (!(m.performance || {}).fps || !d.task) return;
      counts[d.task] = (counts[d.task] || 0) + 1;
    });
    var tasks = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; });
    /* 22개를 다 늘어놓으면 표보다 칩이 길어진다. 많은 순으로 몇 개만. */
    tasks = tasks.slice(0, 6);
    box.innerHTML = '';
    var mk = function (task, label) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'perf-cat' + (_perfTask === task ? ' is-on' : '');
      b.dataset.task = task;
      b.textContent = label;
      b.addEventListener('click', function () {
        _perfTask = (_perfTask === task) ? '' : task;
        _paintPerfCats(models);
        _paintPerfRows(models);
      });
      box.appendChild(b);
    };
    mk('', _t('All'));
    tasks.forEach(function (t) { mk(t, t.replace(/_/g, ' ')); });
  }

  function _paintPerf(models) {
    var block = $('measured');
    if (!block || !$('perfRows')) return;

    _paintPerfCats(models);
    _paintPerfRows(models);

    var measured = 0;
    var tasks = {};
    models.forEach(function (m) {
      var d = m.display || {};
      if (d.task) tasks[d.task] = 1;
      if ((m.performance || {}).fps) measured += 1;
    });
    var note = $('measuredCount');
    if (note) {
      note.textContent = _fmt(measured) + ' ' + _t('measured') + ' · ' +
        Object.keys(tasks).length + ' ' + _t('tasks');
    }

    var search = $('measuredSearch');
    if (search && !search._dxBound) {
      search._dxBound = true;
      search.addEventListener('input', function () {
        _perfQuery = search.value || '';
        _paintPerfRows(models);
      });
    }
    block.hidden = false;
  }

  function loadCatalogueSize() {
    MODULE_FACTS.forEach(function (f) {
      if (_facts[f.app]) return;            // 이미 알고 있으면 다시 묻지 않는다
      fetch(f.url).then(function (r) { return r.json(); })
        .then(function (data) {
          var parts = f.pick(data);
          if (!parts || !parts.length) return;
          _facts[f.app] = parts;
          _paintFacts();
        })
        .catch(function () {
          /* 그 모듈이 돌지 않는다. 카드는 출하 시 설명을 유지한다 — 서버가 떠
             있든 아니든 참인 문장이다. 한 모듈의 실패가 나머지를 막지 않는다. */
        });
    });
  }

  /* ── which modules are up ────────────────────────────────── */

  function refreshModuleState() {
    var health = ns._healthStatus;
    if (!health) return;

    var cards = document.querySelectorAll('.orbital-card[data-app]');
    var up = [];
    var down = 0;
    cards.forEach(function (card) {
      var key = HEALTH_KEY[card.dataset.app] || card.dataset.app;
      if (!(health[key] && health[key].alive)) down += 1;
    });

    /* "start →" 여덟 개는 행동 유도가 여덟 개라는 뜻이고, 그러면 아무것도 행동
       유도가 아니다. 상태 라벨도 같다 — 전부 돌 때(평상시) "Running" 여덟 개는
       아무것도 말하지 않으면서 행마다 같은 폭을 차지하고, 그 사실은 목록 위
       "8 of 8 running" 이 이미 말한다. 그러니 예외가 있을 때만 말한다.
       점은 그대로 둔다 — 점은 한 글자도 차지하지 않으면서 상태를 말한다.
       계약: tests/launcher/test_home_density_browser.py */
    var exceptional = down > 0;

    cards.forEach(function (card) {
      var key = HEALTH_KEY[card.dataset.app] || card.dataset.app;
      var alive = !!(health[key] && health[key].alive);
      card.classList.toggle('is-up', alive);
      var line = card.querySelector('[data-role="state"]');
      if (line) {
        line.textContent = (exceptional && alive) ? _t('Running') : '';
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
    /* 전부 돌면 이 패널은 목록이 이미 말한 것을 되풀이할 뿐이다. 무언가 꺼져
       있을 때에만 "그래도 이것들은 돌고 있다" 가 정보가 된다. */
    if (panel) panel.hidden = !up.length || !exceptional;
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
  /* 카드의 data-app 과 health 키가 다르다(dx_monitor → monitor). 계약 테스트가
     그 매핑을 손으로 베끼면 조용히 어긋나므로, 진짜를 내보낸다. */
  ns._HEALTH_KEY = HEALTH_KEY;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
