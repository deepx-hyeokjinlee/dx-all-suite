/* ─── intro · Stream 장면 — 16채널 pull-back ─────────────────────────────────
   spec: docs/superpowers/specs/2026-09-30-intro-stream-scene-design.md

   교차로 한 채널이 화면을 채우고 box 가 잡힌다. 카메라가 한 번 물러나며 그 화면이 4×4 wall 의
   자기 칸이 되고, 원색이 wall 의 grade 로 바뀐다. 그리고 나머지 15칸의 box 가 대각선 물결로 잡힌다.

   사진과 box 는 실제다: DEEPX 공식 sample 영상의 frame 에 공식 Model Zoo yolov5-s 320 을 DX-M1 에서
   돌린 결과 (scripts/intro/bake_stream.py). 그림은 굽고, box 는 좌표로 두어 여기서 그린다.

   좌표계는 하나다 — 16:10 무대 (1600×1000) 가 화면을 cover 로 채우고, wall · box · 시작 화면이 모두
   그 안에 있다. 그래서 pull-back 은 시작 화면의 transform 한 번으로 정확히 제 칸에 떨어진다.
   움직이는 것은 transform 과 opacity 뿐이다. */
(function () {
  'use strict';

  var BASE = '/static/img/intro/stream/';
  var PULL_AT = 900;      // 시작 화면에서 box 가 잡힌 뒤
  var RIPPLE_AT = 1800;   // pull-back 이 끝나는 때
  var STEP_TILE = 70;     // 대각선 한 칸마다
  var STEP_BOX = 18;      // 칸 안에서 box 하나마다
  var LABELS = 4;         // 시작 화면에서 이름을 붙이는 큰 box 수

  var _data = null, _ready = false, _root = null, _timers = [];

  function _later(fn, ms) { _timers.push(setTimeout(fn, ms)); }

  function _img(src) {
    return new Promise(function (resolve, reject) {
      var im = new Image();
      im.onload = function () {
        (im.decode ? im.decode() : Promise.resolve()).then(function () { resolve(im); }, function () { resolve(im); });
      };
      im.onerror = reject;
      im.src = src;
    });
  }

  /* intro 가 시작할 때 부른다 — 박자까지 3초 남짓 동안 받아 둔다. 못 받으면 박자는 prompt 만. */
  function prepare() {
    if (_ready || _data) return;
    _data = {};
    Promise.all([
      fetch(BASE + 'detections.json').then(function (r) { if (!r.ok) throw r; return r.json(); }),
      _img(BASE + 'wall.webp'),
      _img(BASE + 'hero.webp'),
    ]).then(function (got) { _data = got[0]; _ready = true; }, function () { _ready = false; });
  }

  function _tileRect(i) {
    var d = _data, cols = d.cols, gap = d.gap;
    var tw = (d.stage[0] - gap * (cols - 1)) / cols, th = (d.stage[1] - gap * (d.rows - 1)) / d.rows;
    var r = Math.floor(i / cols), c = i % cols;
    return { x: c * (tw + gap), y: r * (th + gap), w: tw, h: th, r: r, c: c };
  }

  /* box 하나 = HTML 요소 하나. 모서리 네 개는 CSS gradient 로 그린다 (style.css .ist-b).
     SVG 로 그리면 path 의 transform/opacity 가 compositor 에 가지 못해 물결 동안 무대 전체를 매
     frame 다시 칠했다 (실측: 느린 frame 48%). 요소면 box 마다 layer 라 칠하지 않고 움직인다.
     좌표는 무대 기준 % — 무대가 어떤 크기로 cover 되든 같은 자리다. 모서리 길이는 한 변의 25%
     (최소 6 단위) 를 가로 · 세로 각각의 % 로 바꿔 넘긴다. */
  function _box(parent, rect, box, delay, extra) {
    var b = box.b, S = _data.stage;
    var x0 = rect.x + b[0] * rect.w, y0 = rect.y + b[1] * rect.h;
    var w = (b[2] - b[0]) * rect.w, h = (b[3] - b[1]) * rect.h;
    var l = Math.max(6, Math.min(w, h) * 0.25);
    var el = document.createElement('i');
    el.className = extra ? 'ist-b ' + extra : 'ist-b';
    el.style.cssText = 'left:' + (x0 / S[0] * 100) + '%;top:' + (y0 / S[1] * 100) + '%;width:' +
      (w / S[0] * 100) + '%;height:' + (h / S[1] * 100) + '%';
    el.style.setProperty('--lx', (l / w * 100) + '%');
    el.style.setProperty('--ly', (l / h * 100) + '%');
    el.style.setProperty('--d', delay + 'ms');
    parent.appendChild(el);
  }

  function _layer(cls) {
    var el = document.createElement('div');
    el.className = cls;
    return el;
  }

  function _build(overlay) {
    var d = _data, heroI = d.hero, hero = _tileRect(heroI), full = { x: 0, y: 0, w: d.stage[0], h: d.stage[1] };
    var root = document.createElement('div');
    root.className = 'intro-stream';
    root.setAttribute('aria-hidden', 'true');
    root.innerHTML =
      '<div class="ist-stage"><div class="ist-drift">' +
        '<div class="ist-wall"></div>' +
        '<div class="ist-slot"></div>' +
        '<div class="ist-hero"><div class="ist-hero-photo"></div><div class="ist-labels"></div></div>' +
        '<div class="ist-scan"></div>' +
      '</div></div>' +
      '<div class="ist-shade"></div>';
    var drift = root.querySelector('.ist-drift');
    /* prepare() 가 받아 둔 바로 그 URL — cache 에서 바로 칠해진다 */
    root.querySelector('.ist-wall').style.backgroundImage = 'url(' + BASE + 'wall.webp)';
    root.querySelector('.ist-hero-photo').style.backgroundImage = 'url(' + BASE + 'hero.webp)';
    var wall = _layer('ist-boxes');
    drift.insertBefore(wall, root.querySelector('.ist-slot'));

    /* 16칸의 box — 나머지 15칸은 대각선 물결로, 시작 화면의 칸은 pull-back 이 끝날 때 (그 칸의
       큰 box 가 물러나며 걷히는 자리를 제 크기의 box 가 받는다 — 선 굵기가 줄어들지 않게) */
    d.tiles.forEach(function (tile, i) {
      var rect = _tileRect(i);
      tile.boxes.forEach(function (box, k) {
        if (i === heroI) _box(wall, rect, box, 0, 'is-hero');
        else _box(wall, rect, box, (rect.r + rect.c) * STEP_TILE + k * STEP_BOX);
      });
    });

    /* 시작 화면 — 무대 전체에 그린 뒤 transform 으로 자기 칸에 내려앉는다 */
    var heroEl = root.querySelector('.ist-hero');
    var heroBoxes = _layer('ist-hero-boxes');
    heroEl.appendChild(heroBoxes);
    var byArea = d.tiles[heroI].boxes.slice().sort(function (a, b) {
      return (b.b[2] - b.b[0]) * (b.b[3] - b.b[1]) - (a.b[2] - a.b[0]) * (a.b[3] - a.b[1]);
    });
    /* 큰 box 몇 개에 class 이름 — model 이 실제로 낸 이름 그대로 (고치지 않는다) */
    var labels = root.querySelector('.ist-labels');
    byArea.forEach(function (box, k) {
      _box(heroBoxes, full, box, 120 + k * 40);
      if (k < LABELS) {
        var tag = document.createElement('span');
        tag.className = 'ist-label';
        tag.textContent = box.c;
        tag.style.left = (box.b[0] * 100) + '%';
        tag.style.top = (box.b[1] * 100) + '%';
        tag.style.setProperty('--d', (260 + k * 40) + 'ms');
        labels.appendChild(tag);
      }
    });
    var style = root.style;
    style.setProperty('--hx', (hero.x / d.stage[0] * 100) + '%');
    style.setProperty('--hy', (hero.y / d.stage[1] * 100) + '%');
    style.setProperty('--hsx', String(hero.w / d.stage[0]));
    style.setProperty('--hsy', String(hero.h / d.stage[1]));
    overlay.insertBefore(root, overlay.firstChild);
    return root;
  }

  /* 박자 시작에 부른다. 준비가 안 됐으면 false — 박자는 prompt 만으로 간다. */
  function play(overlay, beatMs) {
    if (!_ready || !overlay) return false;
    stop();
    _root = _build(overlay);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { if (_root) _root.classList.add('is-on'); });
    });
    _later(function () { if (_root) _root.classList.add('is-pulled'); }, PULL_AT);
    _later(function () { if (_root) _root.classList.add('is-rippled'); }, RIPPLE_AT);
    _later(function () { if (_root) _root.classList.add('is-out'); }, beatMs - 250);
    _later(stop, beatMs + 400);
    return true;
  }

  function stop() {
    _timers.forEach(clearTimeout);
    _timers.length = 0;
    if (_root && _root.parentNode) _root.parentNode.removeChild(_root);
    _root = null;
  }

  window.DXIntroStream = { prepare: prepare, play: play, stop: stop };
})();
