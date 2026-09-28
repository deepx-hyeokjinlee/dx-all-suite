/* ============================================================
   DX AI Studio — 공유 테마 상태
   3-상태: 'dark' | 'light' | 'system'
   저장 키 'dx-theme' (언어의 'dx-lang'과 같은 규약).
   ============================================================ */
(function () {
  'use strict';

  var STORAGE_KEY = 'dx-theme';
  var DEFAULT_THEME = 'system';
  var SUPPORTED = ['dark', 'light', 'system'];
  var _callbacks = [];

  var _theme = DEFAULT_THEME;
  try {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (SUPPORTED.indexOf(stored) !== -1) _theme = stored;
  } catch (e) { /* private mode — 기본값으로 간다 */ }

  function _apply(theme) {
    var root = document.documentElement;
    if (!root) return;
    if (theme === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', theme);
  }

  // 페인트 전에 적용해 첫 프레임의 테마 깜빡임을 없앤다.
  // 그래서 이 스크립트는 <head>의 CSS 링크 뒤, 본문 스크립트 앞에 온다.
  _apply(_theme);

  function getTheme() { return _theme; }

  function resolved() {
    if (_theme !== 'system') return _theme;
    try {
      return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    } catch (e) { return 'dark'; }
  }

  /* 밤 ↔ 낮 조명 교차 (launcher spec 2026-09-23 §7 #14). <html data-dx-fade> 로 고른 문서에서만
     — 모듈은 그대로 즉시 바뀐다. 상태 (_theme · 저장) 는 곧바로 바뀌고, 화면만 교차한다.
     길이는 CSS 가 html[data-dx-fading="theme"] 로 정한다. */
  function _fade(kind, update) {
    var root = document.documentElement;
    var still = false;
    try { still = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { /* noop */ }
    if (!kind || !root || !('dxFade' in root.dataset) || still || document.readyState !== 'complete'
        || typeof document.startViewTransition !== 'function') {
      update();
      return;
    }
    root.dataset.dxFading = kind;
    var done = function () { if (root.dataset.dxFading === kind) delete root.dataset.dxFading; };
    document.startViewTransition(update).finished.then(done, done);
  }

  function setTheme(theme, opts) {
    if (SUPPORTED.indexOf(theme) === -1) return;
    var changed = theme !== _theme;
    _theme = theme;
    try { localStorage.setItem(STORAGE_KEY, theme); } catch (e) { /* noop */ }
    _fade(changed ? 'theme' : null, function () {
      _apply(theme);
      for (var i = 0; i < _callbacks.length; i++) _callbacks[i](theme);
      try {
        window.dispatchEvent(new CustomEvent('dx-theme-applied', { detail: { theme: theme } }));
      } catch (e) { /* non-DOM 환경 */ }
    });

    if (!(opts && opts.silent)) _broadcast(theme);
  }

  function cycle() {
    var next = SUPPORTED[(SUPPORTED.indexOf(_theme) + 1) % SUPPORTED.length];
    setTheme(next);
    return next;
  }

  function onThemeChange(fn) { if (typeof fn === 'function') _callbacks.push(fn); }

  /* launcher는 모듈을 iframe으로 띄운다. 부모↔자식 양방향으로 흘려보내
     허브와 모듈의 테마가 어긋나지 않게 한다. 후속 B안에서 iframe이
     사라지면 이 두 호출은 자연히 no-op이 된다. */
  function _broadcast(theme) {
    var msg = { type: 'dx-theme-change', theme: theme };
    try {
      if (window.parent && window.parent !== window) window.parent.postMessage(msg, '*');
    } catch (e) { /* cross-origin */ }
    try {
      var frames = document.querySelectorAll('iframe');
      for (var i = 0; i < frames.length; i++) {
        if (frames[i].contentWindow) frames[i].contentWindow.postMessage(msg, '*');
      }
    } catch (e) { /* noop */ }
  }

  window.addEventListener('message', function (e) {
    if (!e.data || e.data.type !== 'dx-theme-change') return;
    if (e.data.theme === _theme) return;
    // silent: 되받아 다시 쏘면 부모↔자식이 서로 메아리친다.
    setTheme(e.data.theme, { silent: true });
  });

  /* system 상태에서 OS 테마가 바뀌면 CSS는 알아서 따라가지만,
     resolved()를 읽는 쪽(차트 색 등)은 알아야 한다. */
  try {
    var mq = window.matchMedia('(prefers-color-scheme: light)');
    var onSystemChange = function () {
      if (_theme !== 'system') return;
      for (var i = 0; i < _callbacks.length; i++) _callbacks[i](_theme);
    };
    if (mq.addEventListener) mq.addEventListener('change', onSystemChange);
    else if (mq.addListener) mq.addListener(onSystemChange);
  } catch (e) { /* matchMedia 미지원 */ }

  window.DXTheme = {
    getTheme: getTheme,
    setTheme: setTheme,
    resolved: resolved,
    cycle: cycle,
    onThemeChange: onThemeChange,
    SUPPORTED: SUPPORTED
  };
})();
