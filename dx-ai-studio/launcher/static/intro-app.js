/* ─── intro · App 장면 — 빛의 선이 지나간 자리가 분할된다 ──────────────────────
   spec: docs/superpowers/specs/2026-09-30-intro-app-compiler-scenes-design.md

   실제 주행 영상의 첫 frame. 가는 빛의 선이 위에서 아래로 훑고, 지나간 자리가 DX-M1 이 낸 실제
   segmentation 으로 바뀐다. 다 바뀌면 그대로 재생된다 — mask 가 달리는 차를 따라간다 (video file).
   그림과 clip 은 scripts/intro/bake_app.py 가 굽는다.

   Stream 이 "밖으로" (pull-back) 였으니 여기는 "가로지르기", 카메라는 달리는 방향으로 아주 조금
   다가간다. 무대 (.ist-stage) 와 가장자리 (.ist-shade) 는 Stream 과 같은 것을 쓴다.

   reveal 은 compositor 로만 한다: mask 층을 감싼 틀이 위에서 내려오고 (translateY -100% → 0) 안쪽은
   반대로 움직여 (100% → 0) 그림은 제자리에 있다 — 틀의 아래 가장자리가 곧 빛의 선이다. clip-path 를
   움직이면 매 frame 다시 칠한다. */
(function () {
  'use strict';

  var BASE = '/static/img/intro/app/';
  var REVEAL_AT = 300;
  var PLAY_AT = 1450;     // reveal (1.1s) 이 끝난 뒤

  var _ready = false, _started = false, _root = null, _timers = [];

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

  /* 그림 둘만 기다린다 — clip 은 재생할 때 준비돼 있으면 돌고, 아니면 정지 mask 그림으로 남는다. */
  function prepare() {
    if (_started) return;
    _started = true;
    Promise.all([_img(BASE + 'first.webp'), _img(BASE + 'seg-first.webp')])
      .then(function () { _ready = true; }, function () { _ready = false; });
  }

  function _build(overlay) {
    var root = document.createElement('div');
    root.className = 'intro-app';
    root.setAttribute('aria-hidden', 'true');
    root.innerHTML =
      '<div class="ist-stage"><div class="iap-drift">' +
        '<div class="iap-photo"></div>' +
        '<div class="iap-reveal"><div class="iap-reveal-in"><div class="iap-seg">' +
          '<video class="iap-video" muted playsinline preload="auto"></video>' +
        '</div></div></div>' +
        '<div class="iap-line"></div>' +
      '</div></div>' +
      '<div class="ist-shade"></div>';
    root.querySelector('.iap-photo').style.backgroundImage = 'url(' + BASE + 'first.webp)';
    root.querySelector('.iap-seg').style.backgroundImage = 'url(' + BASE + 'seg-first.webp)';
    /* 영상은 첫 frame 이 실제로 화면에 나온 뒤에만 보인다 (is-playing). decode 가 실패하는 GPU 경로가
       있었다 — 그때 멈춘 video 가 흰 · 검은 면으로 정지 mask 그림을 덮었다. 실패하면 계속 숨긴다. */
    var video = root.querySelector('video');
    video.muted = true;
    function shown() { if (!video.error) root.classList.add('is-playing'); }
    video.addEventListener('playing', function () {
      if (video.requestVideoFrameCallback) video.requestVideoFrameCallback(shown);
      else shown();
    });
    video.addEventListener('error', function () { root.classList.remove('is-playing'); });
    video.src = BASE + 'seg.mp4';
    overlay.insertBefore(root, overlay.firstChild);
    return root;
  }

  /* 박자 시작에 부른다. 준비가 안 됐으면 false — 박자는 prompt 만으로 간다. */
  function play(overlay, beatMs) {
    if (!_ready || !overlay) return false;
    stop();
    var root = _root = _build(overlay);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { if (_root === root) root.classList.add('is-on'); });
    });
    _later(function () { root.classList.add('is-revealing'); }, REVEAL_AT);
    _later(function () {
      root.classList.add('is-revealed');
      var v = root.querySelector('video');
      try {
        v.currentTime = 0;
        var p = v.play();
        if (p && p.catch) p.catch(function () {});
      } catch (e) {}
    }, PLAY_AT);
    _later(function () { root.classList.add('is-out'); }, beatMs - 250);
    _later(stop, beatMs + 400);
    return true;
  }

  function stop() {
    _timers.forEach(clearTimeout);
    _timers.length = 0;
    if (_root) {
      var v = _root.querySelector('video');
      if (v) { try { v.pause(); v.removeAttribute('src'); v.load(); } catch (e) {} }
      if (_root.parentNode) _root.parentNode.removeChild(_root);
    }
    _root = null;
  }

  window.DXIntroApp = { prepare: prepare, play: play, stop: stop };
})();
