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

  function init() {
    inputRipple();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
