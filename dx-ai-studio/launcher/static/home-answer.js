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

  function _esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  /* 문장 하나를 통째로 번역한다 — 조각을 이어 붙이면 어순이 다른 언어 (ko · ja) 에서 문장이 깨졌다
     (release audit L-15: "선택 에 맞는 모델을 object detection"). {x} 는 값, **…** 는 굵게. */
  function _tpl(key, vals) {
    var out = _esc(_t(key)).replace(/\{(\w+)\}/g, function (_, k) { return _esc((vals || {})[k]); });
    return out.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  }

  /* 라우터의 task id → 화면의 이름. 모르는 id 는 사람이 읽는 모양으로. */
  var TASK_NAME = {
    object_detection: 'Object Detection', pose_estimation: 'Pose Estimation', segmentation: 'Segmentation',
    face_detection: 'Face Detection', classification: 'Classification',
    instance_segmentation: 'Instance Segmentation', semantic_segmentation: 'Semantic Segmentation'
  };
  function _taskName(id) {
    if (!id) return '';
    var key = TASK_NAME[id] || String(id).replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    return _t(key);
  }
  var SOURCE_NAME = { webcam: 'Webcam', video: 'Video file', rtsp: 'RTSP stream' };
  function _sourceName(id) { return id ? _t(SOURCE_NAME[id] || id) : ''; }
  var VERB_NAME = { compile: 'DX Compiler', benchmark: 'DX Benchmark', monitor: 'DX Monitor' };

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
    add(_t('task'), parsed.task ? _esc(_taskName(parsed.task)) : null);
    add(_t('model'), parsed.model ? _esc(parsed.model) : null);
    add(_t('channels'), parsed.channels);
    add(_t('target'), parsed.fps ? parsed.fps + ' FPS' : null);
    add(_t('input'), parsed.source ? _esc(_sourceName(parsed.source)) : null);
    return out.join('');
  }

  function _routeCard(route, isFirst) {
    var kind = _t(KIND_LABEL[route.kind] || 'Open');
    var name = route.kind === 'verb' ? (VERB_NAME[route.title] || route.title)
      : route.kind === 'models' && route.task ? _taskName(route.task)
      : route.kind === 'run' && route.task ? _taskName(route.task)
      : (route.title ? String(route.title).replace(/_/g, ' ') : route.module);
    var why = route.kind === 'models' && route.count
      ? _t('{n} models').replace('{n}', route.count)
      : route.kind === 'run' && route.channels
      ? _t('{n}-channel').replace('{n}', route.channels)
      : (route.why || route.model || '');
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'route-card' + (isFirst ? ' is-primary' : '');
    btn.dataset.module = route.module;
    if (route.demo !== undefined && route.demo !== null) btn.dataset.demo = route.demo;
    btn.innerHTML =
      '<span class="route-kind">' + _esc(kind) + '</span>' +
      '<span class="route-name">' + _esc(name) + '</span>' +
      '<span class="route-why">' + _esc(why) + '</span>' +
      '<span class="route-go">' + _t('Open') + ' →</span>';
    return btn;
  }

  /* What the agent would do, said before it costs anything. Derived from what
     the router understood, so it is never a generic four lines. */
  function _planSteps(parsed) {
    var steps = [];
    if (parsed.task) steps.push(_tpl('**Pick** a model for {task}', { task: _taskName(parsed.task) }));
    else steps.push(_tpl('**Find** the closest model in the zoo'));
    steps.push(_tpl('**Generate** an app in a new session folder'));
    steps.push(_tpl('**Wire** {input} and the logic you described',
      { input: parsed.source ? _sourceName(parsed.source) : _t('the input') }));
    steps.push(_tpl('**Run** it and show you the output'));
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
      $('answerAgentEta').textContent = _t('about 3–6 min');
    }
    _show(plan, !matched);
    _show(panel, true);
    panel.dataset.ask = text;
    /* 보낸 요청이 어디로 갔는지 — home-effects.js 가 그 모듈 아이콘으로 빛을 날린다 (spec §7 #5). */
    document.dispatchEvent(new CustomEvent('dx-home-routed', { detail: routes.slice(0, 3) }));
  }

  function ask(text) {
    if (!text || !String(text).trim()) return Promise.resolve(null);
    _saveDraft('');
    return _ensureData().then(function () {
      var result = window.DXHomeRouter.resolve(text, _catalog, _demos);
      render(text, result);
      return result;
    });
  }

  /* home 에서 나가는 길이 둘인데 하나만 파괴적이었다. 모듈 카드는 셸 안에서
     pushState 로 움직여 문서가 그대로인데, 여기는 location.href 로 SPA 를 떠났다 —
     그래서 돌아오면 새 문서였고 쓰던 문장이 사라졌다. 카드와 같은 길을 쓴다.
     그 다음 판도 새고 있었다: 모듈 이름 (문자열) 을 iframe 을 받는 loadAppIframeIfNeeded 에
     넘겨 에러가 났고, catch 가 결국 location.href 로 문서를 새로 불렀다. 이제는 아이콘과 똑같이
     launch 하나 — 누른 카드 자리에서 열리고, #demo=N 같은 hash 는 모듈까지 간다 (P7).
     location.href 는 셸이 없을 때만.
     계약: tests/launcher/test_home_draft_browser.py, test_home_open_browser.py */
  function _leaveHome(path, fromEl) {
    if (!path) return;
    var ns2 = window.DXLauncher;
    var parts = path.split('#');
    var key = (ns2 && typeof ns2.appFromPath === 'function') ? ns2.appFromPath(parts[0]) : null;
    if (key && typeof ns2.launch === 'function') {
      ns2.launch(key, { from: fromEl || null, hash: parts[1] ? '#' + parts[1] : '' });
      return;
    }
    window.location.href = path;
  }

  function _openRoute(btn) {
    var path = MODULE_PATH[btn.dataset.module];
    if (!path) return;
    if (btn.dataset.demo !== undefined) path += '#demo=' + btn.dataset.demo;
    _leaveHome(path, btn);
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
    _leaveHome('/agent/#ask=' + encodeURIComponent(text), $('answerEscalateGo'));
  }

  /* 쓰다 만 문장은 작업이다. 모듈에 다녀오거나 새로고침해도 잃지 않게 저장한다 —
     보내고 나면 지운다(보낸 문장이 다음에 또 떠 있으면 그건 남은 게 아니라 고장이다).
     sessionStorage 라 탭을 닫으면 사라진다: 초안이지 기록이 아니다. */
  var DRAFT_KEY = 'dxHome.ask.draft';

  function _saveDraft(text) {
    try {
      if (text && text.trim()) sessionStorage.setItem(DRAFT_KEY, text);
      else sessionStorage.removeItem(DRAFT_KEY);
    } catch (e) { /* storage off — 저장이 안 될 뿐 입력은 동작한다 */ }
  }

  function _restoreDraft() {
    var box = $('homeAsk');
    if (!box) return;
    try {
      var saved = sessionStorage.getItem(DRAFT_KEY);
      if (saved && !box.value) box.value = saved;
    } catch (e) { /* storage off */ }
  }

  function init() {
    var form = $('homeAskForm');
    if (!form) return;
    _restoreDraft();
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      ask($('homeAsk').value);
    });
    /* 여러 줄을 쓸 수 있게 textarea 로 열었으므로 Enter 가 줄바꿈이 된다. 프롬프트
       입력의 관례대로 Enter 는 보내고, 줄을 바꾸려면 Shift+Enter 를 쓴다. */
    var box = $('homeAsk');
    if (box) {
      box.addEventListener('input', function () { _saveDraft(box.value); });
      box.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
          e.preventDefault();
          ask(box.value);
        }
      });
    }
    /* 예시는 실제로 만들어진 showcase 의 원문 (home-prompts.js) 이다. 채우고 기다린다 —
       예전처럼 곧바로 실행하면 긴 원문을 읽거나 고칠 틈 없이 답이 뜨고 무대가 Dock 으로
       바뀐다. 원문은 번역하지 않는다: 검증된 것은 영어 원문이다 (spec 2026-09-23 §5.2). */
    var chips = $('homeAskChips');
    if (chips) {
      chips.addEventListener('click', function (e) {
        var more = e.target.closest('#homeAskMore');
        if (more) {
          Array.prototype.forEach.call(chips.querySelectorAll('.ask-chip[hidden]'), function (c) {
            c.hidden = false;
          });
          more.hidden = true;
          return;
        }
        var chip = e.target.closest('.ask-chip');
        if (!chip) return;
        var prompts = window.DXHomePrompts || {};
        var text = prompts[chip.dataset.prompt] || chip.textContent.trim();
        var input = $('homeAsk');
        input.value = text;
        _saveDraft(text);
        input.focus();
        input.setSelectionRange(0, 0);
        input.scrollTop = 0;
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
    var closeBtn = $('answerClose');
    if (closeBtn) closeBtn.addEventListener('click', closeHomeAnswer);

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

  /* 답을 닫고 무대를 되돌린다 (닫기 버튼 · Esc). 닫혀 있으면 아무것도 하지 않는다. */
  function closeHomeAnswer() {
    var panel = $('homeAnswer');
    if (!panel || panel.hidden) return false;
    _show(panel, false);
    return true;
  }

  ns.closeHomeAnswer = closeHomeAnswer;
  ns.homeAsk = ask;
  /* 작업 뷰도 같은 길로 나간다 — 나가는 방법이 둘이면 하나는 반드시 낡는다. */
  ns.homeLeaveTo = _leaveHome;
  ns.initHomeAnswer = init;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
