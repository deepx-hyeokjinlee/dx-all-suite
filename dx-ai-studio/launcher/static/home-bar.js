/* ─── Launcher home — the glass bar's links, and when they can't go anywhere ─
   spec: docs/superpowers/specs/2026-09-23-launcher-home-redesign-design.md §5.7

   이 스튜디오는 공장 · 현장의 닫힌 망에서도 돈다. 그런 곳에서 막대의 링크는 눌러도 빈
   탭만 연다 — 링크를 흐리게 하고 누를 수 없게 한 뒤 "Offline" 이라고 말한다.

   알아내는 길은 둘. navigator.onLine 이 false 면 곧바로. 아니면 막대를 처음 가리킬 때
   developer.deepx.ai 에 HEAD 를 한 번 보낸다 (no-cors: 응답은 못 읽지만 네트워크 실패는
   reject 로 갈린다). 로드 때는 밖으로 나가지 않는다 — --offline 계약. 결과는 세션 동안
   sessionStorage 에 둔다.
   계약: tests/launcher/test_home_bar_contract.py, test_home_bar_browser.py */
(function () {
  'use strict';

  var KEY = 'dx-home-links';
  var PROBE = 'https://developer.deepx.ai/';

  function $(id) { return document.getElementById(id); }
  function _read() {
    try { return sessionStorage.getItem(KEY); } catch (e) { return null; }
  }
  function _write(v) {
    try {
      if (v === null) sessionStorage.removeItem(KEY); else sessionStorage.setItem(KEY, v);
    } catch (e) { /* 저장이 막혀도 이번 화면에서는 맞게 보인다 */ }
  }

  var _asked = false;

  function paint() {
    var bar = $('homeBar');
    if (!bar) return;
    var off = navigator.onLine === false || _read() === 'unreachable';
    bar.classList.toggle('is-offline', off);
    var note = $('homeBarOffline');
    if (note) note.hidden = !off;
    Array.prototype.forEach.call(bar.querySelectorAll('a[href^="http"]'), function (a) {
      if (off) a.setAttribute('aria-disabled', 'true');
      else a.removeAttribute('aria-disabled');
    });
  }

  function probe() {
    if (_asked || _read() || navigator.onLine === false) return;
    _asked = true;
    fetch(PROBE, { mode: 'no-cors', method: 'HEAD', cache: 'no-store' })
      .then(function () { _write('reachable'); })
      .catch(function () { _write('unreachable'); paint(); });
  }

  function init() {
    var bar = $('homeBar');
    if (!bar) return;
    paint();
    ['pointerenter', 'focusin'].forEach(function (ev) { bar.addEventListener(ev, probe); });
    bar.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('a[aria-disabled="true"]');
      if (a) e.preventDefault();
    });
    window.addEventListener('offline', paint);
    /* 망이 돌아오면 지난 답은 낡았다 — 다음 hover 때 다시 묻는다. */
    window.addEventListener('online', function () { _write(null); _asked = false; paint(); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
