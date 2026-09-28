/* ─── Launcher home — the two widgets beside the grid ─────────────────────
   spec: docs/superpowers/specs/2026-09-23-launcher-home-redesign-design.md §5.5–5.6

   왼쪽은 지금 사실인 것 (이 PC 의 DX-M1), 오른쪽은 그 장치에서 잰 것.

   장치 값의 주인은 여기 하나다. 예전에는 15초 poll (refreshHeroDevice) 이 칩을 칠했는데,
   startSharedHwStream 이 같은 장치를 SSE (없으면 3초 poll) 로 이미 뿌리고 있어 두 곳이 같은
   자리를 번갈아 덮어썼을 것이다. 스트림은 studio 가 준비된 뒤 켜지므로, 그 전에는
   hw_status 를 한 번만 읽는다.

   카운트업 · 맥박 · 막대 전환은 효과 단계 (P6) 가 여기에 더한다.
   계약: tests/launcher/test_home_widgets_contract.py, test_home_widgets_browser.py */
(function () {
  'use strict';

  var ns = window.DXLauncher = window.DXLauncher || {};

  function $(id) { return document.getElementById(id); }
  function _t(key) {
    return (window.DXI18n && window.DXI18n.T) ? window.DXI18n.T(key) : key;
  }
  function _fmt(n) {
    return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }
  function _open(app) {
    if (ns.launch) ns.launch(app);
  }
  function _bindOpen(el, app) {
    if (!el) return;
    el.addEventListener('click', function (e) { e.preventDefault(); _open(app); });
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); _open(app); }
    });
  }

  /* ── 상태: DX-M1 ─────────────────────────────────────────── */

  var _hw = null;

  function _line(npu) {
    var parts = [];
    var temps = npu.temperatures || [];
    var temp = typeof npu.temp_avg === 'number' ? npu.temp_avg
      : (temps.length ? Math.max.apply(null, temps) : null);
    if (typeof temp === 'number') parts.push(Math.round(temp) + '°C');
    if (typeof npu.clock_avg === 'number') parts.push(_fmt(npu.clock_avg) + ' MHz');
    if (typeof npu.power_est_mW === 'number') parts.push(_fmt(npu.power_est_mW) + ' mW');
    return parts.join(' · ');
  }

  function _paintCores(box, npu) {
    var n = (npu && npu.cores) || 0;
    var util = (npu && npu.utilization) || [];
    if (box.children.length !== n) {
      box.innerHTML = '';
      for (var i = 0; i < n; i++) {
        var core = document.createElement('span');
        core.className = 'dev-core';
        core.appendChild(document.createElement('i'));
        var label = document.createElement('b');
        label.textContent = String(i);
        core.appendChild(label);
        box.appendChild(core);
      }
    }
    for (var j = 0; j < n; j++) {
      var u = Math.max(0, Math.min(100, Number(util[j]) || 0));
      box.children[j].style.setProperty('--u', String(u));
    }
  }

  function paintDevice(hw) {
    _hw = hw;
    var box = $('homeDevice');
    var chip = $('heroDeviceChip');
    var cores = $('homeCores');
    var line = $('homeDeviceLine');
    if (!box || !chip || !cores || !line) return;
    chip.removeAttribute('data-i18n');   // 살아 있는 값은 사전 키가 아니다

    var npu = hw && hw.npus && hw.npus[0];
    var live = !!(hw && hw.available && hw.count > 0 && npu);
    var mock = !!(hw && hw.mock && npu);
    /* 없음은 색으로 외치지 않고 조명을 끈다 (spec §5.5). */
    box.classList.toggle('is-off', !live && !mock);

    if (live || mock) {
      chip.className = 'ws-device' + (live ? ' is-live' : '');
      chip.textContent = mock ? _t('Mock data') : '';
      chip.hidden = !mock;
      _paintCores(cores, npu);
      line.textContent = _line(npu);
    } else {
      chip.className = 'ws-device is-missing';
      chip.textContent = _t('No DX-M1 connected');
      chip.hidden = false;
      cores.innerHTML = '';
      line.textContent = '';
    }
  }

  /* ── 증거: 이 장치에서 잰 것 ──────────────────────────────── */

  /* task 마다 사람들이 실제로 돌리는 크기 (nano) 하나. 가장 빠른 것을 뽑으면 task 가 달라
     비교할 수 없는 숫자가 된다 — 분류의 3,695 옆에 검출의 1,847 은 아무것도 말하지 않는다.
     이름 패턴으로 추측하지 않고 id 로 적는다: 무엇이 뽑히는지 여기서 읽힌다. */
  var HEADLINE = [
    ['object_detection', 'yolo26n'],
    ['instance_segmentation', 'yolo26n_seg'],
    ['pose_estimation', 'yolo26n_pose'],
    ['classification', 'yolo26n_cls'],
    ['obb_detection', 'yolo26n_obb'],
    ['depth_estimation', 'yolo26_depth_n'],
  ];
  /* Model Zoo 사전 (i18n-dict-shared.js) 과 같은 키 — 용어가 모듈마다 갈라지지 않게. */
  var TASK_LABEL = {
    object_detection: 'Object Detection',
    instance_segmentation: 'Instance Segmentation',
    pose_estimation: 'Pose Estimation',
    classification: 'Classification',
    obb_detection: 'OBB Detection',
    depth_estimation: 'Depth Estimation',
  };
  var ROTATE_MS = 5000;

  var _rows = [];
  var _at = 0;
  var _timer = null;
  var _held = false;

  function pickHeadline(models) {
    var byId = {};
    (models || []).forEach(function (m) { if (m && m.id) byId[m.id] = m; });
    return HEADLINE.map(function (pair) {
      var m = byId[pair[1]];
      var fps = m && m.performance && m.performance.fps;
      return fps ? { task: pair[0], fps: fps } : null;
    }).filter(Boolean);
  }

  function _paintDots(host) {
    if (host.children.length !== _rows.length) {
      host.innerHTML = '';
      _rows.forEach(function (row, i) {
        var dot = document.createElement('button');
        dot.type = 'button';
        dot.className = 'proof-dot';
        dot.setAttribute('aria-label', _t(TASK_LABEL[row.task]));
        dot.addEventListener('click', function (e) { e.stopPropagation(); _at = i; paintProof(); });
        host.appendChild(dot);
      });
    }
    Array.prototype.forEach.call(host.children, function (dot, i) {
      dot.classList.toggle('is-on', i === _at);
    });
  }

  function paintProof() {
    var body = $('homeProof');
    if (!body) return;
    if (!_rows.length) { body.hidden = true; return; }
    var row = _rows[_at % _rows.length];
    $('homeProofFps').textContent = _fmt(row.fps);
    $('homeProofModel').textContent = 'YOLO26n · ' + _t(TASK_LABEL[row.task]);
    _paintDots($('homeProofDots'));
    body.hidden = false;
  }

  function rotate() {
    if (!_rows.length) return;
    _at = (_at + 1) % _rows.length;
    paintProof();
  }

  /* 저절로 넘어가는 것도 움직임이다: 효과 줄이기를 켠 사람에게는 첫 task 에 머물고, 점을
     눌러 고른다. 가리키고 있거나 탭이 가려져 있으면 넘기지 않는다. */
  function _startRotation() {
    if (_timer || _rows.length < 2) return;
    var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (still) return;
    _timer = setInterval(function () {
      if (!_held && !document.hidden) rotate();
    }, ROTATE_MS);
  }

  function takeCatalogue(models) {
    _rows = pickHeadline(models);
    _at = 0;
    paintProof();
    _startRotation();
  }

  /* ── wiring ────────────────────────────────────────────── */

  function init() {
    _bindOpen($('homeDevice'), 'dx_monitor');
    var count = $('measuredCount');
    if (count) {
      count.addEventListener('click', function (e) { e.preventDefault(); e.stopPropagation(); _open('benchmark'); });
    }
    var proof = $('homeMeasured');
    if (proof) {
      ['mouseenter', 'focusin'].forEach(function (ev) { proof.addEventListener(ev, function () { _held = true; }); });
      ['mouseleave', 'focusout'].forEach(function (ev) { proof.addEventListener(ev, function () { _held = false; }); });
    }

    window.addEventListener('message', function (e) {
      if (e.data && e.data.type === 'dx-hw-data') paintDevice(e.data.payload);
    });
    fetch('/dx_monitor/api/hw_status', { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (hw) { if (_hw === null) paintDevice(hw); })
      .catch(function () { if (_hw === null) paintDevice(null); });

    document.addEventListener('dx-home-catalog', function (e) { takeCatalogue(e.detail); });
    if (ns._homeCatalog) takeCatalogue(ns._homeCatalog);

    if (window.DXI18n && window.DXI18n.onLangChange) {
      window.DXI18n.onLangChange(function () {
        if (_hw !== null) paintDevice(_hw);
        var dots = $('homeProofDots');
        if (dots) dots.innerHTML = '';   // 점의 이름표도 언어를 따른다
        paintProof();
      });
    }
  }

  ns._pickHeadline = pickHeadline;   // 테스트가 선택 규칙을 직접 본다
  ns._rotateHeadline = rotate;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
