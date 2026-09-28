/* ============================================================
   DX AI Studio — Shared i18n Core (Multi-Language)
   Supports N languages: EN, JA, KO, ES, ZH-CN, ZH-TW.

   Usage:
   1. Module sets window._DX_I18N_DICT before loading this script
      Dict format: { 'English key': { ko:'한국어', ja:'日本語', es:'Español', 'zh-CN':'简体', 'zh-TW':'繁體' } }
      Legacy format { 'English key': '한국어' } is also supported.
   2. <script src="/static/shared/i18n.js"></script>
   3. Use T('key') or T('english', '한국어') for translations
   ============================================================ */
(function () {
  'use strict';

  var STORAGE_KEY = 'dx-lang';
  var DEFAULT_LANG = 'en';
  var SUPPORTED_LANGS = ['en', 'ja', 'ko', 'es', 'zh-CN', 'zh-TW'];
  var LANG_LABELS = {
    'en': 'English', 'ja': '日本語', 'ko': '한국어',
    'es': 'Español', 'zh-CN': '简体中文', 'zh-TW': '繁體中文'
  };
  var LANG_SHORT = { 'en': 'EN', 'ja': 'JA', 'ko': 'KO', 'es': 'ES', 'zh-CN': '简', 'zh-TW': '繁' };

  var _dict = window._DX_I18N_DICT || {};
  var _selectors = window._DX_I18N_SELECTORS || '';
  var _placeholders = window._DX_I18N_PLACEHOLDERS || {};
  var _initCallbacks = window._DX_I18N_CALLBACKS || [];

  // Reverse dictionary: any-language-value → English key
  var _rev = {};
  for (var en in _dict) {
    if (!_dict.hasOwnProperty(en)) continue;
    var entry = _dict[en];
    if (typeof entry === 'string') {
      _rev[entry] = en;
    } else if (typeof entry === 'object') {
      for (var l in entry) {
        if (entry.hasOwnProperty(l) && entry[l]) _rev[entry[l]] = en;
      }
    }
  }

  var _lang = localStorage.getItem(STORAGE_KEY) || DEFAULT_LANG;
  if (SUPPORTED_LANGS.indexOf(_lang) === -1) _lang = DEFAULT_LANG;
  var _callbacks = [];

  // T(key) or T(en, ko) backward compat
  function T(key, koFallback) {
    var e = _dict[key];
    if (!e) {
      if (_lang === 'ko' && koFallback) return koFallback;
      return key;
    }
    if (typeof e === 'string') return _lang === 'ko' ? e : key;
    if (Object.prototype.hasOwnProperty.call(e, _lang)) return e[_lang];
    return key;
  }

  function _lookup(key) {
    var e = _dict[key];
    if (!e) return null;
    if (typeof e === 'string') return _lang === 'ko' ? e : null;
    if (Object.prototype.hasOwnProperty.call(e, _lang)) return e[_lang];
    return null;
  }

  /* 글자 교차 fade (launcher spec 2026-09-23 §7 #15). <html data-dx-fade> 로 고른 문서에서만 —
     모듈은 그대로 즉시 바뀐다. _lang · 저장은 곧바로, 화면만 교차한다. 길이는 CSS 가
     html[data-dx-fading="lang"] 로 정한다. dx-theme.js 의 _fade 와 같은 규칙. */
  function _fade(kind, update) {
    var root = document.documentElement;
    var still = false;
    try { still = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (_) { /* noop */ }
    if (!kind || !root || !('dxFade' in root.dataset) || still || document.readyState !== 'complete'
        || typeof document.startViewTransition !== 'function') {
      update();
      return;
    }
    root.dataset.dxFading = kind;
    var done = function () { if (root.dataset.dxFading === kind) delete root.dataset.dxFading; };
    document.startViewTransition(update).finished.then(done, done);
  }

  function setLang(lang) {
    if (SUPPORTED_LANGS.indexOf(lang) === -1) return;
    var changed = lang !== _lang;
    _lang = lang;
    localStorage.setItem(STORAGE_KEY, lang);
    _fade(changed ? 'lang' : null, function () {
      SUPPORTED_LANGS.forEach(function (l) {
        document.body.classList.remove('lang-' + l);
      });
      document.body.classList.add('lang-' + lang);
      if (document.documentElement) document.documentElement.lang = lang;
      _applyDOM();
      var i;
      for (i = 0; i < _callbacks.length; i++) _callbacks[i](lang);
      for (i = 0; i < _initCallbacks.length; i++) _initCallbacks[i](lang);
      try {
        window.dispatchEvent(new CustomEvent('dx-lang-applied', { detail: { lang: lang } }));
      } catch (_) { /* non-DOM environments */ }
    });
  }

  function toggleLang() {
    // Cycle: en → ja → ko → es → zh-CN → zh-TW → en
    var idx = SUPPORTED_LANGS.indexOf(_lang);
    var next = SUPPORTED_LANGS[(idx + 1) % SUPPORTED_LANGS.length];
    setLang(next);
  }

  function _queryAll(scope, selector) {
    var items = Array.prototype.slice.call(scope.querySelectorAll(selector));
    if (scope.nodeType === 1 && scope.matches && scope.matches(selector)) {
      items.unshift(scope);
    }
    return items;
  }

  function _applyDOM(root) {
    var scope = root || document;
    if (_selectors) {
      _queryAll(scope, _selectors).forEach(function (el) {
        _translateEl(el);
      });
    }

    _queryAll(scope, '[data-i18n]').forEach(function (el) {
      var key = el.getAttribute('data-i18n');
      var translated = _lookup(key);
      if (_lang === 'en') {
        el.textContent = key;
      } else if (translated !== null) {
        el.textContent = translated;
      }
    });

    _queryAll(scope, '[data-i18n-html]').forEach(function (el) {
      var key = el.getAttribute('data-i18n-html');
      var e = _dict[key];
      if (!e || typeof e !== 'object') return;
      var val = Object.prototype.hasOwnProperty.call(e, _lang) ? e[_lang] : null;
      if (val !== null) el.innerHTML = val;
      else if (_lang === 'en') el.innerHTML = key;
    });

    _queryAll(scope, 'input[placeholder], textarea[placeholder]').forEach(function (el) {
      if (_lang === 'en') {
        var orig = el.getAttribute('data-i18n-ph-orig');
        if (orig) el.setAttribute('placeholder', orig);
        return;
      }
      var origKey = el.getAttribute('data-i18n-ph-orig');
      var ph = el.getAttribute('placeholder');
      var enPh = (origKey && _placeholders.hasOwnProperty(origKey)) ? origKey
               : (ph && _placeholders.hasOwnProperty(ph)) ? ph : null;
      if (enPh === null) return;
      var phEntry = _placeholders[enPh];
      var target;
      if (typeof phEntry === 'string') target = _lang === 'ko' ? phEntry : null;
      else if (typeof phEntry === 'object') target = phEntry[_lang];
      if (target) {
        el.setAttribute('data-i18n-ph-orig', enPh);
        el.setAttribute('placeholder', target);
      }
    });

    _queryAll(scope, '[data-i18n-placeholder]').forEach(function (el) {
      var key = el.getAttribute('data-i18n-placeholder');
      if (!key) return;
      var translated = _lookup(key);
      el.setAttribute('placeholder', translated !== null ? translated : key);
    });

    _queryAll(scope, '[data-i18n-title]').forEach(function (el) {
      var key = el.getAttribute('data-i18n-title');
      if (!key) return;
      var translated = _lookup(key);
      el.setAttribute('title', translated !== null ? translated : key);
    });

    _queryAll(scope, '[data-i18n-aria-label]').forEach(function (el) {
      var key = el.getAttribute('data-i18n-aria-label');
      if (!key) return;
      var translated = _lookup(key);
      el.setAttribute('aria-label', translated !== null ? translated : key);
    });

    SUPPORTED_LANGS.forEach(function (l) {
      _queryAll(scope, 'span.' + l + ', small .' + l).forEach(function (el) {
        el.style.display = l === _lang ? '' : 'none';
      });
    });

    // 5b. Dynamic span injection for languages without HTML spans
    //     When _lang is ja/zh-CN/zh-TW and parent has .en+.ko but no ._lang span:
    //     → create span from dict, or show .en as fallback
    if (_lang !== 'en' && _lang !== 'ko') {
      var _enSpans = _queryAll(scope, 'span.en');
      for (var _si = 0; _si < _enSpans.length; _si++) {
        var _enSp = _enSpans[_si];
        var _par = _enSp.parentNode;
        if (!_par) continue;
        var _koSp = _par.querySelector('span.ko');
        if (!_koSp) continue;
        var _hasTarget = false;
        for (var _ci = 0; _ci < _par.children.length; _ci++) {
          if (_par.children[_ci].classList && _par.children[_ci].classList.contains(_lang)) {
            _hasTarget = true;
            break;
          }
        }
        if (_hasTarget) continue;
        var _enKey = _enSp.textContent.trim();
        var _tr = _lookup(_enKey);
        if (_tr !== null) {
          var _newSp = document.createElement('span');
          _newSp.className = _lang;
          _newSp.textContent = _tr;
          _par.insertBefore(_newSp, _enSp.nextSibling);
        } else {
          // No translation: show English as fallback
          _enSp.style.display = '';
        }
      }
    }

    var langEl = document.querySelector('#langToggle');
    if (langEl) {
      var langCodeEl = langEl.querySelector('.dx-lang-code');
      if (langCodeEl) {
        langCodeEl.textContent = LANG_SHORT[_lang] || _lang.toUpperCase();
      }
      langEl.querySelectorAll('.dx-lang-item').forEach(function (it) {
        it.classList.toggle('active', it.dataset.lang === _lang);
      });
      // Dual-toggle fallback
      var opts = langEl.querySelectorAll('.dx-toggle-opt');
      if (opts.length > 0) {
        for (var oi = 0; oi < opts.length; oi++) {
          if (opts[oi].dataset.val === _lang) opts[oi].classList.add('active');
          else opts[oi].classList.remove('active');
        }
      }
    }
  }

  function _translateEl(el) {
    if (!el.childNodes.length) return;
    if (el.querySelector('.ko, .en, .ja, .es, .zh-CN, .zh-TW')) return;
    // 이 아래는 el.textContent 를 통째로 갈아끼운다 — 자식 엘리먼트가 같이
    // 지워진다. 자기 key 를 든 자식이 있으면 번역의 주인은 그쪽이다.
    // (.legend-item 은 색 점 span + 라벨 span 인데, 여기서 평평해지면
    //  점이 사라진다.)
    if (el.querySelector('[data-i18n], [data-i18n-html]')) return;
    var text = el.textContent.trim();
    if (!text) return;
    if (!el.dataset.i18nOrig) el.dataset.i18nOrig = text;
    var orig = el.dataset.i18nOrig;
    if (_lang === 'en') {
      el.textContent = _rev[el.textContent.trim()] || el.dataset.i18nOrig || el.textContent;
    } else {
      var translated = _lookup(orig);
      el.textContent = translated !== null ? translated : orig;
    }
  }

  function onLangChange(cb) {
    _callbacks.push(cb);
    return function unsubscribeLangChange() {
      var idx = _callbacks.indexOf(cb);
      if (idx !== -1) _callbacks.splice(idx, 1);
    };
  }

  // postMessage listener (launcher → sub-app sync)
  window.addEventListener('message', function (e) {
    if (e.data && e.data.type === 'dx-lang-change') {
      setLang(e.data.lang);
    }
  });

  function _init() {
    SUPPORTED_LANGS.forEach(function (l) {
      document.body.classList.remove('lang-' + l);
    });
    document.body.classList.add('lang-' + _lang);
    if (document.documentElement) document.documentElement.lang = _lang;
    setTimeout(_applyDOM, 50);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }

  /** 나중에 주입되는 조각이 자기 번역을 들고 올 수 있게 한다.
   *
   *  hw_widget 은 launcher 프록시가 호스트 페이지에 꽂는다. 사전은 모듈마다
   *  따로라, 이 위젯의 라벨을 data-i18n 으로 쓰려면 여덟 모듈 사전에 같은
   *  항목을 아홉 개씩 복사해야 했다 — 그래서 언어 span 아홉 벌로 남아 있었다.
   *  이미 있는 key 는 덮지 않는다: 모듈이 정한 문구가 우선이다. */
  function register(extra) {
    if (!extra) return;
    for (var key in extra) {
      if (!Object.prototype.hasOwnProperty.call(extra, key)) continue;
      if (Object.prototype.hasOwnProperty.call(_dict, key)) continue;
      _dict[key] = extra[key];
      var entry = extra[key];
      if (typeof entry === 'string') _rev[entry] = key;
      else if (typeof entry === 'object') {
        for (var l in entry) {
          if (Object.prototype.hasOwnProperty.call(entry, l) && entry[l]) _rev[entry[l]] = key;
        }
      }
    }
    _applyDOM();
  }

  window.DXI18n = {
    T: T,
    register: register,
    get lang() { return _lang; },
    setLang: setLang,
    toggleLang: toggleLang,
    applyLang: _applyDOM,
    onLangChange: onLangChange,
    dict: _dict,
    rev: _rev,
    SUPPORTED_LANGS: SUPPORTED_LANGS,
    LANG_LABELS: LANG_LABELS,
    LANG_SHORT: LANG_SHORT
  };

  window.T = T;
})();
