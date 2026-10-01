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

  var NS = 'http://www.w3.org/2000/svg';

  /* sprite URL — server 가 <meta name="dx-icons"> 에 내용 hash 붙은 URL 을 적는다 (dx_server
     _render_sprite_refs). hash URL 은 immutable cache 라 재방문에 왕복이 없다. <use> 와 load() 가 같은
     URL 을 써야 cache 한 항목으로 끝난다. meta 가 없는 문서 (정적 미리보기 등) 는 hash 없는 경로. */
  var _sprite = null;
  function _spriteUrl() {
    if (_sprite) return _sprite;
    var meta = document.querySelector('meta[name="dx-icons"]');
    _sprite = (meta && meta.getAttribute('content')) || '/static/shared/dx-icons.svg';
    return _sprite;
  }

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
    return '<svg class="' + _esc(cls) + '"' + a11y + '><use href="' + _esc(DXIcon.url(name)) + '"></use></svg>';
  }

  /* <use href> 값 — 직접 <svg> 를 짜는 곳 (dx-tabs 등) 도 이것을 쓴다 */
  DXIcon.url = function (name) {
    return _spriteUrl() + '#' + name;
  };

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
    use.setAttribute('href', DXIcon.url(name));
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

  /* canvas 에 그리기 — <use> 가 닿지 않는 자리 (파이프라인 노드 등, 아이콘 체계 단계 5).
     sprite 를 한 번 읽어 symbol 마다 Path2D 로 바꿔 둔다. 아직 못 읽었으면 false 를 돌려주고 읽기를
     시작한다 — 다 읽으면 window 에 'dx-icons-ready' 를 보낸다 (그리는 쪽이 다시 그린다).
       DXIcon.draw(ctx, 'play', x, y, 16, color)  // x, y 는 왼쪽 위, color 는 CSS 색 */
  var _shapes = null, _loading = null;
  function _toPath(node) {
    var tag = node.tagName.toLowerCase(), p = new Path2D();
    if (tag === 'path') p = new Path2D(node.getAttribute('d') || '');
    else if (tag === 'circle') {
      var cx = +node.getAttribute('cx'), cy = +node.getAttribute('cy'), r = +node.getAttribute('r');
      p.arc(cx, cy, r, 0, Math.PI * 2);
    } else if (tag === 'rect') {
      var x = +node.getAttribute('x'), y = +node.getAttribute('y'), w = +node.getAttribute('width'),
          h = +node.getAttribute('height'), rx = +(node.getAttribute('rx') || 0);
      if (p.roundRect) p.roundRect(x, y, w, h, rx); else p.rect(x, y, w, h);
    } else return null;
    var t = node.getAttribute('transform');
    if (t && typeof DOMMatrix === 'function') {
      var out = new Path2D();
      out.addPath(p, new DOMMatrix(t.replace(/scale\(([^)]+)\)/, function (m, a) { return 'scale(' + a.trim().replace(/\s+/g, ',') + ')'; })
        .replace(/translate\(([^)]+)\)/, function (m, a) { return 'translate(' + a.trim().replace(/\s+/g, 'px,') + 'px)'; })));
      return out;
    }
    return p;
  }
  DXIcon.load = function () {
    if (_loading) return _loading;
    _loading = fetch(_spriteUrl()).then(function (r) { return r.text(); }).then(function (text) {
      var doc = new DOMParser().parseFromString(text, 'image/svg+xml'), map = {};
      Array.prototype.forEach.call(doc.querySelectorAll('symbol'), function (sym) {
        var one = { fill: [], line: [] };
        ['f', 'l'].forEach(function (cls) {
          var g = sym.querySelector('g.' + cls);
          if (!g) return;
          Array.prototype.forEach.call(g.children, function (n) {
            var path = _toPath(n);
            if (path) one[cls === 'f' ? 'fill' : 'line'].push(path);
          });
        });
        map[sym.id] = one;
      });
      _shapes = map;
      try { window.dispatchEvent(new Event('dx-icons-ready')); } catch (e) {}
      return map;
    }).catch(function () { _loading = null; return null; });
    return _loading;
  };
  DXIcon.draw = function (ctx, name, x, y, size, color) {
    if (!_shapes) { DXIcon.load(); return false; }
    var shape = _shapes[name];
    if (!shape) return false;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(size / 24, size / 24);
    ctx.fillStyle = color; ctx.strokeStyle = color;
    var a = ctx.globalAlpha;
    ctx.globalAlpha = a * 0.24;
    shape.fill.forEach(function (p) { ctx.fill(p); });
    ctx.globalAlpha = a;
    ctx.lineWidth = 2; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    shape.line.forEach(function (p) { ctx.stroke(p); });
    ctx.restore();
    return true;
  };

  window.DXIcon = DXIcon;
})();
