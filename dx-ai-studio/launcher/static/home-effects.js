/* ─── Launcher home — the effects ───────────────────────────────────────
   spec: docs/superpowers/specs/2026-09-23-launcher-home-redesign-design.md §7

   규칙: transform · opacity 만 움직인다. JS 가 움직이는 것은 Web Animations API 로 —
   class 를 떼고 reflow 로 다시 붙이는 트릭은 키 입력마다 layout 을 부른다.
   효과 줄이기를 켠 사람에게는 시작하지 않는다 (CSS 쪽은 dx-base.css 의 전역 규칙).

   정지한 효과 (무대 조명 · 책 · 포스터 pill) 는 home-stage.css 가 혼자 한다. 여기에는 JS 가
   있어야 하는 것만 둔다.
   계약: tests/launcher/test_home_effects_contract.py, test_home_effects_browser.py */
(function () {
  'use strict';

  var EASE = 'cubic-bezier(.2, .8, .2, 1)';   // 튕기지 않는다 (spec §7)

  function still() {
    try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; }
  }

  /* #3 입력창 — 키를 누를 때마다 가장자리 빛이 차올랐다가 focus 의 밝기로 240ms 에 가라앉는다.
     쉴 때 · focus 때의 밝기는 CSS (.ask-box::after, :focus-within) 가 정한다. 여기서는 그 위에
     한 번의 물결만 얹는다 — 끝나면 animation 이 사라져 CSS 값으로 돌아간다. */
  function inputRipple() {
    var input = document.getElementById('homeAsk');
    var box = input && input.closest('.ask-box');
    if (!box || typeof box.animate !== 'function') return;
    var wave = null;
    input.addEventListener('input', function () {
      if (still()) return;
      if (wave) wave.cancel();
      var rest = parseFloat(getComputedStyle(box, '::after').opacity) || 0;
      wave = box.animate([{ opacity: 1 }, { opacity: rest }],
        { duration: 240, easing: EASE, pseudoElement: '::after' });
      wave.onfinish = function () { wave = null; };
    });
  }

  /* #4 placeholder — 검증된 요청과 모듈로 바로 가는 요청 (home-prompts.js DXHomePlaceholders) 을
     돌아가며 친다: 다 보인 채 1.8s → 20ms/자 로 지움 → 다음 문장을 45ms/자 로 침.
     포커스하면 멈추고 비운다 (쓰려는 사람 앞에서 글자가 움직이지 않게). 떠나면 다시.
     도는 동안에는 i18n 이 placeholder 를 되돌려 놓지 못하게 data-i18n-placeholder 를 떼고,
     언어는 여기서 따라간다. */
  var TYPE_MS = 45, HOLD_MS = 1800, ERASE_MS = 20;

  function placeholderCycle() {
    var input = document.getElementById('homeAsk');
    var cycle = window.DXHomePlaceholders;
    if (!input || !cycle || !cycle.length || still()) return;
    input.removeAttribute('data-i18n-placeholder');

    var at = 0, chars = [], n = 0, phase = 'hold', timer = null;
    function say(i) {
      var key = cycle[i];
      return Array.from((window.DXI18n && window.DXI18n.T) ? window.DXI18n.T(key) : key);
    }
    function show() { input.placeholder = chars.slice(0, n).join(''); }
    function busy() { return document.activeElement === input || input.value !== ''; }
    function later(ms) { clearTimeout(timer); timer = setTimeout(step, ms); }

    function step() {
      if (document.hidden || busy()) return;
      if (phase === 'hold') { phase = 'erase'; return later(ERASE_MS); }
      if (phase === 'erase') {
        if (n > 0) { n -= 1; show(); return later(ERASE_MS); }
        at = (at + 1) % cycle.length;
        chars = say(at);
        phase = 'type';
        return later(TYPE_MS);
      }
      n += 1;
      show();
      if (n >= chars.length) { phase = 'hold'; return later(HOLD_MS); }
      later(TYPE_MS);
    }

    /* 지금 문장을 다 보인 채로 다시 시작한다. */
    function restart() {
      chars = say(at);
      n = chars.length;
      phase = 'hold';
      show();
      later(HOLD_MS);
    }

    input.addEventListener('focus', function () { clearTimeout(timer); input.placeholder = ''; });
    input.addEventListener('blur', function () { if (!busy()) restart(); });
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) clearTimeout(timer);
      else if (!busy()) later(phase === 'type' ? TYPE_MS : HOLD_MS);
    });
    if (window.DXI18n && window.DXI18n.onLangChange) {
      window.DXI18n.onLangChange(function () { if (!busy()) restart(); });
    }
    restart();
  }

  /* #16 커서 조명 — 무대 아래의 빛 (.stage-light > i) 을 커서 자리로 옮긴다. 옮기는 것은
     transform 하나, 한 frame 에 한 번 (rAF). 첫 움직임에 켜지고 창을 떠나면 꺼진다. */
  function cursorLight() {
    var wrap = document.querySelector('#landing .stage-light');
    var dot = wrap && wrap.firstElementChild;
    if (!dot) return;
    var x = 0, y = 0, queued = false, half = 0;

    function paint() {
      queued = false;
      if (!document.body.classList.contains('home-visible')) return;
      var r = wrap.getBoundingClientRect();
      if (!half) half = dot.getBoundingClientRect().width / 2;
      dot.style.transform = 'translate3d(' + (x - r.left - half) + 'px, ' + (y - r.top - half) + 'px, 0)';
      wrap.classList.add('is-on');   // 자리를 잡은 뒤에 켠다 — 모서리에서 떠오르지 않게
    }
    document.addEventListener('pointermove', function (e) {
      if (e.pointerType === 'touch' || still()) return;
      x = e.clientX;
      y = e.clientY;
      if (!queued) { queued = true; requestAnimationFrame(paint); }
    }, { passive: true });
    document.addEventListener('pointerout', function (e) {
      if (!e.relatedTarget) wrap.classList.remove('is-on');
    });
  }

  /* ── 움직임 (P6c) ───────────────────────────────────────────────────── */

  var STAGGER_MS = 60, ENTRY_MS = 500, TILE_STAGGER_MS = 16, SWEEP_MS = 900, FLY_MS = 600;
  var NEAR_PX = 120, MAX_SCALE = 1.18, PRESS_SCALE = .96;

  function lightLayer() { return document.querySelector('#landing .stage-light'); }

  /* 빛 층의 요소 el 의 가운데가 화면 좌표 (x, y) 에 오게 하는 transform. */
  function at(el, x, y) {
    var r = lightLayer().getBoundingClientRect();
    return 'translate3d(' + (x - r.left - el._dxW / 2) + 'px, ' + (y - r.top - el._dxH / 2) + 'px, 0)';
  }
  /* 빛 요소의 크기는 CSS 가 고정한다 — 한 번 재어 둔다. */
  function sized(el) {
    if (!el._dxW) {
      var b = el.getBoundingClientRect();
      el._dxW = b.width;
      el._dxH = b.height;
    }
    return el;
  }
  function centre(el) {
    var r = el.getBoundingClientRect();
    return [r.left + r.width / 2, r.top + r.height / 2];
  }

  /* #1 첫 진입 — 세션에 한 번. 화면 순서대로 떠오르고 (60ms 간격, 타일끼리는 16ms), 빛이 제목
     뒤를 왼→오로 훑은 뒤 막대를 한 번 스친다. 셸이 드러나는 순간 (launcher-boot-pending 이 빠지고
     home 이 보일 때) 에 시작한다 — 인트로가 끝나기 전에 끝나 버리지 않게. */
  var ENTERED = 'dx-home-entered';

  function firstEntry() {
    try { if (sessionStorage.getItem(ENTERED)) return; } catch (e) { return; }
    function ready() {
      return !document.documentElement.classList.contains('launcher-boot-pending')
        && document.body.classList.contains('home-visible');
    }
    function play() {
      try { sessionStorage.setItem(ENTERED, '1'); } catch (e) { /* noop */ }
      if (still()) return;
      var order = ['#homeTour', '#homeStage .stage-title', '#homeStage .stage-sub', '#homeStage .stage-films',
        '#homeAskForm .ask-box', '#homeAskChips', '#homeDevice'];
      var delay = 0;
      function rise(el, d) {
        var a = el.animate([{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'none' }],
          { duration: ENTRY_MS, delay: d, easing: EASE, fill: 'backwards' });
        a.id = 'entry';
      }
      order.forEach(function (sel, i) {
        var el = document.querySelector(sel);
        delay = i * STAGGER_MS;
        if (el) rise(el, delay);
      });
      var tiles = document.querySelectorAll('#studioGrid > *');
      Array.prototype.forEach.call(tiles, function (el, j) { rise(el, (order.length) * STAGGER_MS + j * TILE_STAGGER_MS); });
      delay = order.length * STAGGER_MS + Math.max(0, tiles.length - 1) * TILE_STAGGER_MS;
      ['#homeMeasured', '#homeBar'].forEach(function (sel, i) {
        var el = document.querySelector(sel);
        if (el) rise(el, delay + (i + 1) * STAGGER_MS);
      });
      sweep();
    }
    if (ready()) { play(); return; }
    var watch = new MutationObserver(function () {
      if (!ready()) return;
      watch.disconnect();
      play();
    });
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    watch.observe(document.body, { attributes: true, attributeFilter: ['class'] });
  }

  function sweep() {
    var band = document.querySelector('#landing .stage-sweep');
    var title = document.querySelector('#homeStage .stage-title');
    var bar = document.getElementById('homeBar');
    if (!band || !title) return;
    sized(band);
    var t = title.getBoundingClientRect();
    var ty = t.top + t.height / 2;
    var a = band.animate([
      { transform: at(band, t.left, ty), opacity: 0 },
      { opacity: 1, offset: .2 },
      { opacity: 1, offset: .75 },
      { transform: at(band, t.right, ty), opacity: 0 }
    ], { duration: SWEEP_MS, delay: 150, easing: EASE });
    a.id = 'sweep';
    if (!bar) return;
    var b = bar.getBoundingClientRect();
    var by = b.top + b.height / 2;
    var g = band.animate([
      { transform: at(band, b.left, by) + ' scaleY(.5)', opacity: 0 },
      { opacity: .7, offset: .3 },
      { transform: at(band, b.right, by) + ' scaleY(.5)', opacity: 0 }
    ], { duration: 500, delay: 150 + SWEEP_MS, easing: EASE });
    g.id = 'sweep';
  }

  /* #5 보내기 — 빛이 입력창에서 떨어져 라우팅된 모듈 아이콘에 닿고, 아이콘이 켜진다. 여러 곳이면
     순서대로. render() 가 답을 열면 무대가 Dock 으로 바뀌므로, 그 배치가 끝난 frame 에서 잰다. */
  var TILE_OF = { monitor: 'dx_monitor' };

  function routedLight() {
    document.addEventListener('dx-home-routed', function (e) {
      if (still()) return;
      var routes = (e.detail || []).map(function (r) { return r && r.module; }).filter(Boolean);
      var seen = {};
      routes = routes.filter(function (m) { return seen[m] ? false : (seen[m] = true); });
      if (!routes.length) return;
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { fly(routes); });
      });
    });
  }

  function fly(modules) {
    var orb = document.querySelector('#landing .stage-orb');
    var box = document.querySelector('#homeAskForm .ask-box');
    if (!orb || !box) return;
    sized(orb);
    var from = centre(box);
    modules.forEach(function (m, i) {
      var tile = document.querySelector('.orbital-card[data-app="' + (TILE_OF[m] || m) + '"] .mod-tile');
      if (!tile) return;
      var to = centre(tile);
      var start = i * (FLY_MS + 120);
      var a = orb.animate([
        { transform: at(orb, from[0], from[1]) + ' scale(.6)', opacity: 0 },
        { opacity: 1, offset: .15 },
        { transform: at(orb, to[0], to[1]) + ' scale(1)', opacity: .9 }
      ], { duration: FLY_MS, delay: start, easing: EASE });
      a.id = 'orb';
      var lit = tile.animate([{ opacity: 0 }, { opacity: 1, offset: .3 }, { opacity: 0 }],
        { duration: 700, delay: start + FLY_MS - 60, easing: EASE, pseudoElement: '::after' });
      lit.id = 'lit';
    });
  }

  /* #6 Dock 확대 — 커서에서 120px 안의 모듈 아이콘이 가까운 만큼 커진다 (최대 1.18, 누르면 .96 배).
     가장자리 specular 는 커서 쪽에서 비친다 (CSS 변수 → ::before). 읽기를 먼저 다 하고 쓰기를
     나중에 해서 한 frame 에 layout 을 한 번만 부른다. */
  function dockMagnify() {
    var tiles = Array.prototype.slice.call(document.querySelectorAll('#studioGrid .orbital-card .mod-tile'));
    if (!tiles.length) return;
    var x = -1e4, y = -1e4, queued = false, pressed = null, dirty = false;

    function paint() {
      queued = false;
      var rects = tiles.map(function (t) { return t.getBoundingClientRect(); });
      var any = false;
      tiles.forEach(function (t, i) {
        var r = rects[i];
        var d = Math.sqrt(Math.pow(x - (r.left + r.width / 2), 2) + Math.pow(y - (r.top + r.height / 2), 2));
        var k = d < NEAR_PX ? Math.pow(1 - d / NEAR_PX, 2) : 0;
        var s = 1 + (MAX_SCALE - 1) * k;
        if (pressed === t) s *= PRESS_SCALE;
        if (k > 0 || pressed === t) any = true;
        t.style.transform = s === 1 ? '' : 'scale(' + s.toFixed(4) + ')';
        t.style.setProperty('--near', k.toFixed(3));
        if (k > 0) {
          t.style.setProperty('--sx', ((x - r.left) / r.width * 100).toFixed(1) + '%');
          t.style.setProperty('--sy', ((y - r.top) / r.height * 100).toFixed(1) + '%');
        }
      });
      dirty = any;
    }
    function ask() { if (!queued) { queued = true; requestAnimationFrame(paint); } }

    document.addEventListener('pointermove', function (e) {
      if (e.pointerType === 'touch' || still()) return;
      if (!document.body.classList.contains('home-visible')) return;
      x = e.clientX;
      y = e.clientY;
      ask();
    }, { passive: true });
    document.addEventListener('pointerdown', function (e) {
      if (still()) return;
      var card = e.target.closest && e.target.closest('#studioGrid .orbital-card');
      pressed = card ? card.querySelector('.mod-tile') : null;
      if (pressed) ask();
    });
    ['pointerup', 'pointercancel'].forEach(function (ev) {
      document.addEventListener(ev, function () { if (pressed) { pressed = null; ask(); } });
    });
    document.addEventListener('pointerout', function (e) {
      if (!e.relatedTarget && dirty) { x = y = -1e4; ask(); }
    });
  }

  function init() {
    inputRipple();
    placeholderCycle();
    cursorLight();
    firstEntry();
    routedLight();
    dockMagnify();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
