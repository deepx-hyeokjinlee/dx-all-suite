/* ── Home prompt → answer ─────────────────────────────────────
 *
 * Wires the hero input to the router and renders what came back. The router is
 * pure and knows nothing about the DOM; this file knows nothing about parsing.
 *
 * The catalogue and the demo list are fetched once, lazily, and cached — never
 * per keystroke. If either is unreachable the router still runs on what it has,
 * which is how a local app should behave when a module has not been started.
 */
(function () {
  'use strict';

  var ns = window.DXLauncher = window.DXLauncher || {};
  var _catalog = null;
  var _demos = null;
  var _loading = null;

  var MODULE_PATH = {
    stream: '/stream/', zoo: '/zoo/', compiler: '/compiler/',
    planner: '/planner/', benchmark: '/benchmark/', monitor: '/dx_monitor/',
    app: '/app/', agent: '/agent/'
  };

  var KIND_LABEL = {
    run: 'Run it now', fit: 'Check it fits', models: 'Pick a model',
    verb: 'Open the tool'
  };

  function $(id) { return document.getElementById(id); }

  function _t(key) {
    return (window.DXI18n && window.DXI18n.T) ? window.DXI18n.T(key) : key;
  }

  /* One fetch per session, not per keystroke. A failure is not fatal: an empty
     catalogue just means the router has fewer terms to match against. */
  function _ensureData() {
    if (_loading) return _loading;
    _loading = Promise.all([
      fetch('/zoo/api/catalog').then(function (r) { return r.json(); })
        .catch(function () { return null; }),
      fetch('/stream/api/demos').then(function (r) { return r.json(); })
        .catch(function () { return null; })
    ]).then(function (both) {
      var cat = both[0];
      _catalog = (cat && (cat.models || cat)) || [];
      if (!Array.isArray(_catalog)) _catalog = [];
      var dem = both[1];
      _demos = (dem && (dem.demos || dem)) || [];
      if (!Array.isArray(_demos)) _demos = [];
    });
    return _loading;
  }

  function _readChips(parsed) {
    var out = [];
    function add(label, value) {
      if (value === null || value === undefined || value === '') return;
      out.push('<span class="read-chip"><b>' + label + '</b>' + value + '</span>');
    }
    add(_t('task'), parsed.task ? parsed.task.replace(/_/g, ' ') : null);
    add(_t('model'), parsed.model);
    add(_t('channels'), parsed.channels);
    add(_t('target'), parsed.fps ? parsed.fps + ' FPS' : null);
    add(_t('input'), parsed.source);
    return out.join('');
  }

  function _routeCard(route, isFirst) {
    var kind = _t(KIND_LABEL[route.kind] || 'Open');
    var name = route.title ? String(route.title).replace(/_/g, ' ') : route.module;
    var why = route.kind === 'models' && route.count
      ? route.count + ' ' + _t('models')
      : (route.why || route.model || '');
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'route-card' + (isFirst ? ' is-primary' : '');
    btn.dataset.module = route.module;
    if (route.demo !== undefined && route.demo !== null) btn.dataset.demo = route.demo;
    btn.innerHTML =
      '<span class="route-kind">' + kind + '</span>' +
      '<span class="route-name">' + name + '</span>' +
      '<span class="route-why">' + why + '</span>' +
      '<span class="route-go">' + _t('Open') + ' →</span>';
    return btn;
  }

  /* What the agent would do, said before it costs anything. Derived from what
     the router understood, so it is never a generic four lines. */
  function _planSteps(parsed) {
    var steps = [];
    if (parsed.task) {
      steps.push('<b>' + _t('Pick') + '</b> ' +
        _t('a model for') + ' ' + parsed.task.replace(/_/g, ' '));
    } else {
      steps.push('<b>' + _t('Find') + '</b> ' + _t('the closest model in the zoo'));
    }
    steps.push('<b>' + _t('Generate') + '</b> ' + _t('an app in a new session folder'));
    steps.push('<b>' + _t('Wire') + '</b> ' +
      (parsed.source ? parsed.source : _t('the input')) + ' ' + _t('and the logic you described'));
    steps.push('<b>' + _t('Run') + '</b> ' + _t('it and show you the output'));
    return steps.map(function (s) { return '<li>' + s + '</li>'; }).join('');
  }

  function _show(el, on) {
    if (!el) return;
    if (on) el.removeAttribute('hidden'); else el.setAttribute('hidden', '');
  }

  function render(text, result) {
    var panel = $('homeAnswer');
    if (!panel) return;
    var routes = result.routes || [];
    var matched = routes.length > 0;

    $('answerRead').innerHTML = _readChips(result.parsed);

    var host = $('answerRoutes');
    host.innerHTML = '';
    routes.slice(0, 3).forEach(function (r, i) { host.appendChild(_routeCard(r, i === 0)); });

    _show(host, matched);
    _show($('answerEscalate'), matched);

    var plan = $('answerAgentPlan');
    if (!matched) {
      $('answerAgentSteps').innerHTML = _planSteps(result.parsed);
      $('answerAgentEta').textContent = '~3–6 min';
    }
    _show(plan, !matched);
    _show(panel, true);
    panel.dataset.ask = text;
  }

  function ask(text) {
    if (!text || !String(text).trim()) return Promise.resolve(null);
    return _ensureData().then(function () {
      var result = window.DXHomeRouter.resolve(text, _catalog, _demos);
      render(text, result);
      return result;
    });
  }

  function _openRoute(btn) {
    var path = MODULE_PATH[btn.dataset.module];
    if (!path) return;
    if (btn.dataset.demo !== undefined) path += '#demo=' + btn.dataset.demo;
    window.location.href = path;
  }

  /* The handoff carries the sentence. Agent Dev's own input already says
     "Describe what you want to build…" — this is that field, reached from the
     front door instead of one click in. */
  function _handOffToAgent() {
    var panel = $('homeAnswer');
    var text = (panel && panel.dataset.ask) || '';
    if (ns.homeAgentStart) {
      ns.homeAgentStart(text);
      return;
    }
    /* 작업 뷰를 못 쓰는 상황이면 모듈로 넘긴다 — 문장은 그대로 실어서. */
    window.location.href = '/agent/#ask=' + encodeURIComponent(text);
  }

  function init() {
    var form = $('homeAskForm');
    if (!form) return;
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      ask($('homeAsk').value);
    });
    var chips = $('homeAskChips');
    if (chips) {
      chips.addEventListener('click', function (e) {
        var chip = e.target.closest('.ask-chip');
        if (!chip) return;
        $('homeAsk').value = chip.textContent.trim();
        ask(chip.textContent.trim());
      });
    }
    var routes = $('answerRoutes');
    if (routes) {
      routes.addEventListener('click', function (e) {
        var card = e.target.closest('.route-card');
        if (card) _openRoute(card);
      });
    }
    var esc = $('answerEscalateGo');
    if (esc) esc.addEventListener('click', _handOffToAgent);
    var go = $('answerAgentGo');
    if (go) go.addEventListener('click', _handOffToAgent);
    var no = $('answerAgentCancel');
    if (no) no.addEventListener('click', function () { _show($('homeAnswer'), false); });

    /* Every label in the panel is built in JS, so data-i18n never reaches it.
       The sentence is kept on the panel, so a language change just answers it
       again — the router is pure and the data is cached, so this is free. */
    if (window.DXI18n && DXI18n.onLangChange) {
      DXI18n.onLangChange(function () {
        var panel = $('homeAnswer');
        if (panel && !panel.hasAttribute('hidden') && panel.dataset.ask) {
          ask(panel.dataset.ask);
        }
      });
    }
  }

  ns.homeAsk = ask;
  ns.initHomeAnswer = init;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
