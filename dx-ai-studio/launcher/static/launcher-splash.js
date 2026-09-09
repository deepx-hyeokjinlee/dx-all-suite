
(function() {
  var ns = window.DXLauncher;

  var _MODULE_ICONS = {
    app: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/><circle cx="14" cy="10" r="1.5"/></svg>',
    stream: '<svg viewBox="0 0 24 24"><circle cx="12" cy="10" r="5"/><circle cx="12" cy="10" r="2"/><path d="M4 18 Q8 14 12 16 Q16 18 20 14"/></svg>',
    zoo: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
    compiler: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 4 V8 M12 16 V20 M4 12 H8 M16 12 H20"/><circle cx="12" cy="12" r="3"/></svg>',
    edgeguide: '<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/><line x1="6" y1="2" x2="6" y2="6"/><line x1="18" y1="2" x2="18" y2="6"/><line x1="6" y1="18" x2="6" y2="22"/><line x1="18" y1="18" x2="18" y2="22"/><path d="M20 12 L23 12"/></svg>',
    benchmark: '<svg viewBox="0 0 24 24"><path d="M12 2 A10 10 0 0 1 22 12"/><path d="M12 2 A10 10 0 0 0 2 12"/><line x1="12" y1="12" x2="17" y2="7"/><circle cx="12" cy="12" r="2"/></svg>',
    monitor: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="12" rx="2"/><path d="M8 19h8M12 15v4"/><path d="M7 9l3 3 4-4 3 3"/></svg>',
    agent: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M13 15h4"/></svg>',
  };
  ns._MODULE_ICONS = _MODULE_ICONS;

  /* 인트로 — 네 박자.
   *
   * 이전 것은 17.5초짜리 네온 시네마틱이었고, 그 앞의 것은 그냥 1.2초짜리
   * 페이드였다. 하나는 다른 제품의 문법이었고, 하나는 문법이 없었다.
   *
   * 연출의 문법은 네온이 아니다. 하나를 보여주고, 참았다가, 규모를 드러내고,
   * 마지막 프레임에서 컷 없이 다음 장면으로 넘어가는 것이다.
   *
   *   1  점 하나        검은 화면에 빛 하나. 이게 무엇이 될지는 아직 모른다.
   *   2  여덟이 된다     하나가 여덟으로 갈라져 퍼진다 — 규모의 공개.
   *   3  빛이 이름을 지난다  워드마크는 페이드인하지 않는다. 빛이 왼쪽에서
   *                      오른쪽으로 지나가며 글자를 드러낸다.
   *   4  컷이 없다       여덟 개가 흩어지지 않고, 실제 Modules 목록의 아이콘
   *                      타일 자리로 날아가 그 위에서 사라진다. 인트로의
   *                      마지막 프레임이 앱의 첫 프레임이다.
   *
   * 4박자가 이 시퀀스의 요점이다. 인트로가 끝나고 앱이 시작되는 게 아니라,
   * 인트로가 앱이 된다. 점의 색은 그 모듈의 타일 색을 실제 DOM 에서 읽어
   * 오므로, 인트로는 여덟 색을 소개하고 목록에 넘겨주는 셈이 된다.
   *
   * 곡선과 지속시간은 나머지 UI 와 같은 측정값을 쓴다. 착지 지점을 못 읽으면
   * (레이아웃이 아직 없거나 목록이 바뀌었으면) 4박자만 조용한 페이드로
   * 떨어진다 — 연출이 실패해도 문은 열려야 한다. */
  var _B1 = 380;    // 점 하나를 보여주는 시간 — 참는 구간
  var _B2 = 300;    // 여덟으로 갈라지는 시간
  var _B3 = 420;    // 빛이 이름을 지나는 시간
  var _B4 = 620;    // 타일 자리로 날아가는 시간

  /* 착지 지점. 뷰포트 밖이라고 버리지 않는다 — 짧은 창에서는 목록의 마지막
     한둘이 접힘 아래에 있고, 그걸 버리면 개수가 어긋나 연출 전체가 조용한
     페이드로 떨어진다. 실제로 800px 창에서 여덟 번째 타일이 y=868 이라
     그렇게 되고 있었다. 아래로 향하는 점은 사라지면서 화면을 벗어난다. */
  function _tiles() {
    var out = [];
    document.querySelectorAll('.orbital-card[data-app] .mod-tile').forEach(function (el) {
      var r = el.getBoundingClientRect();
      if (!r.width) return;
      out.push({
        x: r.left + r.width / 2,
        y: r.top + r.height / 2,
        tint: getComputedStyle(el).backgroundColor
      });
    });
    return out;
  }

  function initSplashV2() {
    if (sessionStorage.getItem('dx-splash-seen')) {
      var ov0 = document.getElementById('splashOverlay');
      if (ov0) ov0.remove();
      revealMainContent();
      return false;
    }
    sessionStorage.setItem('dx-splash-seen', '1');
    ns._splashActive = true;
    if (typeof ns.hideStudioBootGate === 'function') ns.hideStudioBootGate({ conceal: true });

    var overlay = document.getElementById('splashOverlay');
    var field = document.getElementById('splashModulesArea');
    var logo = document.getElementById('splashLogo');

    /* 움직임을 줄여 달라고 한 사람에게 연출은 방해다. */
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      if (logo) logo.classList.add('is-revealed');
      ns._splashTimers.push(setTimeout(skipSplash, 320));
      return true;
    }

    var n = ns._SPLASH_MODULES.length;
    var dots = [];
    if (field) {
      ns._SPLASH_MODULES.forEach(function (mod, i) {
        var d = document.createElement('span');
        d.className = 'intro-dot';
        field.appendChild(d);
        dots.push(d);
      });
    }

    /* 1 — 점 하나. 여덟 개가 같은 자리에 겹쳐 있어 하나로 보인다. */
    requestAnimationFrame(function () {
      if (overlay) overlay.classList.add('is-seeded');
    });

    /* 2 — 여덟이 된다. 가운데에서 좌우로 고르게 퍼진다. */
    ns._splashTimers.push(setTimeout(function () {
      var span = Math.min(window.innerWidth * 0.42, 340);
      dots.forEach(function (d, i) {
        var t = n > 1 ? (i / (n - 1)) - 0.5 : 0;
        d.style.transform = 'translateX(' + (t * span).toFixed(1) + 'px)';
        d.classList.add('is-spread');
      });
    }, _B1));

    /* 3 — 빛이 이름을 지난다. */
    ns._splashTimers.push(setTimeout(function () {
      if (logo) logo.classList.add('is-revealed');
    }, _B1 + _B2 - 120));

    /* 4 — 컷 없이. 점들이 실제 타일 자리로 간다. */
    var handoff = _B1 + _B2 + _B3;
    ns._splashTimers.push(setTimeout(function () {
      var targets = _tiles();
      if (!targets.length) {        // 목록이 아예 없다 — 연출을 포기한다
        skipSplash();
        return;
      }
      /* 컷이 없으려면 막을 걷었을 때 그 아래 앱이 이미 있어야 한다.
         인트로 동안 본편은 visibility:hidden 이었으므로, 막을 투명하게
         만들기 전에 먼저 켠다 — 그래야 점이 진짜 타일 위에 내려앉는다. */
      if (typeof ns.completeLauncherBoot === 'function') {
        ns.completeLauncherBoot({ revealAnimation: 'skip' });
      }
      if (overlay) overlay.classList.add('is-handing-off');
      dots.forEach(function (d, i) {
        var to = targets[i];
        if (!to) { d.classList.add('is-landing'); return; }   // 짝이 없으면 그냥 사라진다
        var from = d.getBoundingClientRect();
        d.style.background = to.tint;
        d.style.transform =
          'translate(' + (to.x - (from.left + from.width / 2)).toFixed(1) + 'px,' +
          (to.y - (from.top + from.height / 2)).toFixed(1) + 'px) scale(2.6)';
        d.classList.add('is-landing');
      });
      ns._splashTimers.push(setTimeout(function () { skipSplash(); }, _B4));
    }, handoff));

    return true;
  }

  function skipSplash(manual) {
    if (manual === undefined) manual = false;
    var ov = document.getElementById('splashOverlay');
    if (!ov || ov.classList.contains('fade-out')) return;

    ns._splashTimers.forEach(function(id) { clearTimeout(id); });
    ns._splashTimers.length = 0;
    if (ns._decodeRAF) { cancelAnimationFrame(ns._decodeRAF); ns._decodeRAF = null; }
    if (window._splashParticleCleanup) window._splashParticleCleanup();

    ov.classList.add('fade-out');
    sessionStorage.setItem('dx-splash-seen', '1');
    ns._splashActive = false;

    if (window._dxTutorial && typeof window._dxTutorial.hideTOC === 'function') {
      window._dxTutorial.hideTOC();
    }

    if (typeof ns.completeLauncherBoot === 'function') {
      ns.completeLauncherBoot({ revealAnimation: manual ? 'skip' : 'normal' });
    }

    // If the 8 module servers aren't ready yet, completeLauncherBoot is a no-op and the
    // shell stays boot-pending. Re-show the boot gate (concealed behind the splash until
    // now) so the user sees a "starting up" spinner instead of a blank screen until ready.
    if (!ns._studioReadyResolved && typeof ns.showStudioBootGate === 'function') {
      ns.showStudioBootGate();
    }

    setTimeout(function() {
      ov.remove();
      if (typeof ns.tryCompleteLauncherBoot === 'function') ns.tryCompleteLauncherBoot();
    }, 800);
  }

  function replaySplash() {
    var existing = document.getElementById('splashOverlay');
    if (existing) existing.remove();

    sessionStorage.removeItem('dx-splash-seen');

    var ov = document.createElement('div');
    ov.className = 'splash-overlay';
    ov.id = 'splashOverlay';
    ov.setAttribute('onclick', 'skipSplash(true)');
    ov.innerHTML =
      '<div class="splash-logo-hud" id="splashLogoHud">' +
        '<div class="splash-logo" id="splashLogo">DEEPX</div>' +
        '<div class="splash-subtitle" id="splashSubtitle">AI Studio</div>' +
      '</div>' +
      '<div class="splash-modules-area" id="splashModulesArea"></div>' +
      '<div class="splash-skip" data-i18n="Click to skip">Click to skip</div>';
    document.body.insertBefore(ov, document.body.firstChild);
    initSplashV2();
  }

  function showHeroSplash() {
    var hero = document.getElementById('heroSplash');
    if (!hero) { revealMainContent(); return; }

    window._heroTimer = setTimeout(dismissHeroSplash, 4000);
    setTimeout(function() { var h = document.getElementById('heroSplash'); if (h) { h.remove(); revealMainContent(); } }, 5000);
  }

  function dismissHeroSplash() {
    var hero = document.getElementById('heroSplash');
    if (!hero || hero.classList.contains('hidden')) return;
    clearTimeout(window._heroTimer);
    hero.classList.add('hidden');
    revealMainContent();
    setTimeout(function() { hero.remove(); }, 700);
  }

  function revealMainContent() {
    var main = document.querySelector('.landing-container') || document.querySelector('.top-bar') || document.getElementById('landing');
    if (main && !main.classList.contains('main-content-reveal') && !main.classList.contains('main-content-reveal-skip')) {
      main.classList.add(sessionStorage.getItem('dx-splash-seen') ? 'main-content-reveal-skip' : 'main-content-reveal');
    }
  }

  ns.initSplashV2 = initSplashV2;
  ns.skipSplash = skipSplash;
  ns.replaySplash = replaySplash;
  ns.showHeroSplash = showHeroSplash;
  ns.dismissHeroSplash = dismissHeroSplash;
  ns.revealMainContent = revealMainContent;
})();
if (typeof DXI18n !== 'undefined' && typeof DXI18n.onLangChange === 'function') {
  DXI18n.onLangChange(function() {
    if (typeof DXLauncher !== 'undefined' && typeof DXLauncher.refreshLauncherChrome === 'function') DXLauncher.refreshLauncherChrome();
    if (typeof DXI18n !== 'undefined' && DXI18n.applyLang) DXI18n.applyLang(document);
  });
}
