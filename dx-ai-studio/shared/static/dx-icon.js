/* ─── DX AI Studio — 아이콘 helper ─────────────────────────────────────────
   spec: docs/superpowers/specs/2026-09-29-studio-icon-system-design.md

   스튜디오의 아이콘은 shared/static/dx-icons.svg 한 벌이다. 이모지 (지구본 · 체크 · 모래시계 …) 를 textContent 로 넣던
   자리는 이것으로 SVG 를 넣는다 — 색은 currentColor 라 글자 색 · 테마 · 상태를 따라간다.

     DXIcon('check')                       → '<svg class="dx-ico" aria-hidden="true">…</svg>' (문자열)
     DXIcon('alert', { label: 'Warning' }) → 뜻이 있는 아이콘: role="img" + aria-label
     DXIcon.el('globe', { cls: 'dx-ico--lg' }) → 요소

   장식이면 (옆에 같은 뜻의 글자가 있으면) label 을 주지 않는다 — 화면 낭독기가 두 번 읽는다.
   계약: tests/shared/test_icon_system.py */
(function () {
  'use strict';

  var SPRITE = '/static/shared/dx-icons.svg#';
  var NS = 'http://www.w3.org/2000/svg';

  function _esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function DXIcon(name, opts) {
    opts = opts || {};
    var cls = 'dx-ico' + (opts.cls ? ' ' + opts.cls : '');
    var a11y = opts.label
      ? ' role="img" aria-label="' + _esc(opts.label) + '"'
      : ' aria-hidden="true" focusable="false"';
    return '<svg class="' + _esc(cls) + '"' + a11y + '><use href="' + SPRITE + _esc(name) + '"></use></svg>';
  }

  DXIcon.el = function (name, opts) {
    opts = opts || {};
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'dx-ico' + (opts.cls ? ' ' + opts.cls : ''));
    if (opts.label) {
      svg.setAttribute('role', 'img');
      svg.setAttribute('aria-label', opts.label);
    } else {
      svg.setAttribute('aria-hidden', 'true');
      svg.setAttribute('focusable', 'false');
    }
    var use = document.createElementNS(NS, 'use');
    use.setAttribute('href', SPRITE + name);
    svg.appendChild(use);
    return svg;
  };

  /* 아이콘 + 글자를 한 번에 — el.textContent = '<체크 이모지> ' + T('Done') 이던 자리 (아이콘 체계 단계 5).
     글자는 text node 로 넣는다 (번역 · 서버 메시지를 HTML 로 해석하지 않는다).
       DXIcon.label(btn, 'check', T('Use This Config'))
       DXIcon.label(h3, 'spinner', T('Compiling...'), { cls: 'dx-ico--spin' }) */
  DXIcon.label = function (el, name, text, opts) {
    if (!el) return el;
    el.textContent = '';
    if (name) {
      el.appendChild(DXIcon.el(name, opts));
      el.appendChild(document.createTextNode(' '));
    }
    el.appendChild(document.createTextNode(text == null ? '' : String(text)));
    return el;
  };

  window.DXIcon = DXIcon;
})();
