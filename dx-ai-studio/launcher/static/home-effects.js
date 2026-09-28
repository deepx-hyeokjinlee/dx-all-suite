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

  function init() {
    inputRipple();
    placeholderCycle();
    cursorLight();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
