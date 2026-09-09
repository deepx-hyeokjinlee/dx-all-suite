
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

  /* 인트로.
   *
   * 이전 시퀀스는 데스크톱에서 17.5초짜리 시네마틱이었다 — 로고 glitch,
   * 회로 트레이스, 파티클, 에너지 게이지, 코어 점화, 워프 점프. 애플에서
   * 잰 가장 긴 전환이 0.32s 인 화면으로 들어가는 문 치고는 다른 세계의
   * 문법이었고, 정적인 것과 움직이는 것의 톤이 갈리면 움직이는 쪽이 이긴다.
   *
   * 브랜드 순간은 남기되 영화는 아니게 한다. 워드마크가 자리를 잡고, 부제가
   * 따라오고, 여덟 모듈이 조용히 계단으로 들어온 뒤 끝난다 — 1.2초. 곡선과
   * 지속시간은 나머지 UI 와 같은 측정값(--ease / --dur)을 쓴다.
   *
   * reduced-motion 경로가 원래 2초에 끝내고 있었다는 것이, 이 화면이
   * 그만큼이면 충분하다는 증거이기도 했다. */
  var _SPLASH_STEP = 45;        // 모듈 하나가 들어오는 간격
  var _SPLASH_SETTLE = 520;     // 워드마크가 자리를 잡는 데 걸리는 시간

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
    if (overlay) overlay.classList.add('is-quiet');

    /* 움직임을 줄여 달라고 한 사람에게는 브랜드 순간도 짧게. */
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      ns._splashTimers.push(setTimeout(skipSplash, 320));
      return true;
    }

    _settleLogo();

    ns._splashTimers.push(setTimeout(function () {
      var sub = document.getElementById('splashSubtitle');
      if (sub) sub.classList.add('is-in');
    }, 260));

    var area = document.getElementById('splashModulesArea');
    var first = _SPLASH_SETTLE;
    if (area) {
      ns._SPLASH_MODULES.forEach(function (mod, i) {
        ns._splashTimers.push(setTimeout(function () {
          var el = document.createElement('div');
          el.className = 'splash-mod';
          el.innerHTML = '<span class="splash-mod-icon">' +
            (_MODULE_ICONS[mod.icon] || '') + '</span>' +
            '<span class="splash-mod-name">' + mod.name + '</span>';
          area.appendChild(el);
          requestAnimationFrame(function () { el.classList.add('is-in'); });
        }, first + i * _SPLASH_STEP));
      });
    }

    var total = first + ns._SPLASH_MODULES.length * _SPLASH_STEP + 380;
    ns._splashTimers.push(setTimeout(function () { skipSplash(); }, total));
    return true;
  }

  /* 로고는 켜지는 게 아니라 자리를 잡는다. */
  function _settleLogo() {
    var logo = document.getElementById('splashLogo');
    if (!logo) return;
    requestAnimationFrame(function () { logo.classList.add('is-settled'); });
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
