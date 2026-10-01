/* ─── intro · Compiler 장면 — 수백 개가 하나의 칩이 된다 ────────────────────────
   spec: docs/superpowers/specs/2026-09-30-intro-app-compiler-scenes-design.md

   Ultralytics YOLO26n 의 실제 ONNX graph (node 384 · 연결 526) 가 왼쪽에서 오른쪽으로 켜지고, compile
   의 물결이 지나가며 node 들이 가운데로 빨려 들어 DX-M1 이 된다. 그리고 칩 위로 빛이 한 번 지나간다.
   graph 는 scripts/intro/bake_compile.py 가 굽는다 (배치만 풀었고 연결은 그대로).

   Stream 은 "밖으로", App 은 "가로지르기", 여기는 "안으로". 점 384 개를 따로 움직여야 하므로 graph 는
   canvas 한 장에 rAF 로 그린다 — frame 당 1ms 안쪽이고, 다 빨려 들면 그리기를 멈춘다. 칩은 정적 SVG 를
   transform/opacity 로만 띄운다. */
(function () {
  'use strict';

  var SRC = '/static/img/intro/compile/graph.json';
  var LIGHT = 900;        // graph 가 왼쪽 → 오른쪽으로 켜지는 시간
  var PULL_AT = 1000;     // 물결이 시작하는 때
  var PULL_SPREAD = 520;  // 왼쪽 node 가 먼저 — 가로 위치만큼 늦게 출발
  var PULL_MS = 760;      // node 하나가 칩까지 가는 시간
  var FORGE_AT = 1650;    // 칩이 선다
  var LIT_AT = 2300;      // 빛이 칩을 지나간다
  var CHIP = { x: 800, y: 470, s: 300 };   // 무대 좌표 (1600×1000) — prompt 는 아래에 앉는다

  var _data = null, _ready = false, _started = false, _root = null, _timers = [], _raf = 0;

  function _later(fn, ms) { _timers.push(setTimeout(fn, ms)); }

  function prepare() {
    if (_started) return;
    _started = true;
    fetch(SRC).then(function (r) { if (!r.ok) throw r; return r.json(); })
      .then(function (d) { _data = d; _ready = true; }, function () { _ready = false; });
  }

  /* DX-M1 — package · die · NPU core 셋 · 가장자리 pin. 색은 CSS (.icp-*) 가 준다. */
  function _chipSvg() {
    var pins = '';
    for (var i = 0; i < 9; i++) {
      var p = 34 + i * 16;
      pins += '<rect class="icp-pin" x="' + p + '" y="4" width="6" height="12" rx="1.5"/>' +
              '<rect class="icp-pin" x="' + p + '" y="184" width="6" height="12" rx="1.5"/>' +
              '<rect class="icp-pin" x="4" y="' + p + '" width="12" height="6" rx="1.5"/>' +
              '<rect class="icp-pin" x="184" y="' + p + '" width="12" height="6" rx="1.5"/>';
    }
    return '<svg viewBox="0 0 200 200" aria-hidden="true">' + pins +
      '<rect class="icp-package" x="16" y="16" width="168" height="168" rx="14"/>' +
      '<rect class="icp-die" x="40" y="40" width="120" height="120" rx="6"/>' +
      '<rect class="icp-core" x="50" y="50" width="30" height="62" rx="3"/>' +
      '<rect class="icp-core" x="85" y="50" width="30" height="62" rx="3"/>' +
      '<rect class="icp-core" x="120" y="50" width="30" height="62" rx="3"/>' +
      '<rect class="icp-mem" x="50" y="120" width="100" height="10" rx="2"/>' +
      '<rect class="icp-mem" x="50" y="136" width="64" height="14" rx="2"/>' +
      '<rect class="icp-mem" x="120" y="136" width="30" height="14" rx="2"/>' +
      '<text class="icp-name" x="100" y="176" text-anchor="middle">DX-M1</text>' +
      '</svg>';
  }

  function _ease(t) { return t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t); }
  function _in(t) { return t <= 0 ? 0 : t >= 1 ? 1 : t * t * t; }   // 빨려 들 때는 끝에서 빠르게

  function _draw(canvas, t0) {
    var ctx = canvas.getContext('2d');
    var nodes = _data.nodes, edges = _data.edges, W = _data.stage[0];
    var k = canvas.width / W;
    var n = nodes.length, px = new Float32Array(n), py = new Float32Array(n), a = new Float32Array(n);
    var accent = getComputedStyle(canvas).getPropertyValue('--icp-node').trim() || 'white';   // 색은 style.css
    function frame(now) {
      var t = now - t0, done = true;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (var i = 0; i < n; i++) {
        var x = nodes[i][0], y = nodes[i][1];
        var lit = _ease((t - (x / W) * (LIGHT - 200)) / 200);
        var go = _in((t - PULL_AT - (x / W) * PULL_SPREAD) / PULL_MS);
        if (go < 1) done = false;
        px[i] = (x + (CHIP.x - x) * go) * k;
        py[i] = (y + (CHIP.y - y) * go) * k;
        a[i] = lit * (1 - go);
      }
      /* 'lighter' — 겹칠수록 밝아진다. 점마다 옅은 번짐 (halo) 을 한 번 더 그려 빛나게 한다
         (shadowBlur 는 점마다 blur 를 돌려 느리다). */
      ctx.globalCompositeOperation = 'lighter';
      ctx.lineWidth = Math.max(1, k);
      ctx.strokeStyle = accent;
      for (var e = 0; e < edges.length; e++) {
        var s = edges[e][0], d = edges[e][1], ea = Math.min(a[s], a[d]) * 0.4;
        if (ea < 0.01) continue;
        ctx.globalAlpha = ea;
        ctx.beginPath(); ctx.moveTo(px[s], py[s]); ctx.lineTo(px[d], py[d]); ctx.stroke();
      }
      ctx.fillStyle = accent;
      for (var j = 0; j < n; j++) {
        if (a[j] < 0.01) continue;
        var conv = nodes[j][2] === 'conv', r = (conv ? 4.2 : 2) * k;
        ctx.globalAlpha = a[j] * 0.16;
        ctx.beginPath(); ctx.arc(px[j], py[j], r * 2.8, 0, 6.2832); ctx.fill();
        ctx.globalAlpha = a[j] * (conv ? 1 : 0.75);
        ctx.beginPath(); ctx.arc(px[j], py[j], r, 0, 6.2832); ctx.fill();
      }
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = 'source-over';
      if (!done || t < PULL_AT) _raf = requestAnimationFrame(frame);
      else ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    _raf = requestAnimationFrame(frame);
  }

  function _build(overlay) {
    var root = document.createElement('div');
    root.className = 'intro-compile';
    root.setAttribute('aria-hidden', 'true');
    root.innerHTML =
      '<div class="ist-stage">' +
        '<canvas class="icp-graph"></canvas>' +
        '<div class="icp-chip">' + _chipSvg() + '<div class="icp-sweep"></div></div>' +
      '</div>' +
      '<div class="ist-shade"></div>';
    var S = _data.stage, chip = root.querySelector('.icp-chip');
    chip.style.left = ((CHIP.x - CHIP.s / 2) / S[0] * 100) + '%';
    chip.style.top = ((CHIP.y - CHIP.s / 2) / S[1] * 100) + '%';
    chip.style.width = (CHIP.s / S[0] * 100) + '%';
    chip.style.height = (CHIP.s / S[1] * 100) + '%';
    overlay.insertBefore(root, overlay.firstChild);
    var canvas = root.querySelector('canvas');
    canvas.dataset.nodes = String(_data.nodes.length);
    var box = root.querySelector('.ist-stage').getBoundingClientRect();
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(box.width * dpr);
    canvas.height = Math.round(box.height * dpr);
    return root;
  }

  /* 박자 시작에 부른다. 준비가 안 됐으면 false — 박자는 prompt 만으로 간다. */
  function play(overlay, beatMs) {
    if (!_ready || !overlay) return false;
    stop();
    var root = _root = _build(overlay);
    requestAnimationFrame(function (now) {
      if (_root !== root) return;
      root.classList.add('is-on');
      _draw(root.querySelector('canvas'), now);
    });
    _later(function () { root.classList.add('is-forged'); }, FORGE_AT);
    _later(function () { root.classList.add('is-lit'); }, LIT_AT);
    _later(function () { root.classList.add('is-out'); }, beatMs - 250);
    _later(stop, beatMs + 400);
    return true;
  }

  function stop() {
    _timers.forEach(clearTimeout);
    _timers.length = 0;
    if (_raf) { cancelAnimationFrame(_raf); _raf = 0; }
    if (_root && _root.parentNode) _root.parentNode.removeChild(_root);
    _root = null;
  }

  window.DXIntroCompile = { prepare: prepare, play: play, stop: stop };
})();
