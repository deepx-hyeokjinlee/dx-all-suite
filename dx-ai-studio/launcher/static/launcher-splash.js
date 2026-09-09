
(function() {
  var ns = window.DXLauncher;

  /* 인트로.
   *
   * 앞선 시도들은 전부 장르를 빌려왔다 — 네온 회로, 그리고 강착원반을 두른
   * 블랙홀. 레퍼런스를 "어떻게 판단할지"가 아니라 "무엇을 그릴지"로 받으면
   * 매번 남의 영화 포스터를 제품 앞에 붙이게 된다.
   *
   * 그래서 이번엔 애플 광고의 문법을 찾아 읽고 그대로 적용했다:
   *
   *   · 피사체는 하나, 무대는 검은 여백 (요소 주변 최소 20%)
   *   · 카메라는 한 번만 움직이고, 그 움직임이 무언가를 드러낸다
   *   · transform 과 opacity 만 애니메이션한다 (compositor-friendly)
   *   · 스프링: damping 1.0, response 0.3–0.4s. 급히 시작하거나 멈추지 않는다
   *   · 큰 글자는 자간을 조이고(-0.02em), 타입은 마지막에 온다
   *   · 시그니처는 표면을 훑고 지나가는 하드 스페큘러
   *   · reduced motion 은 opacity 크로스페이드로 대체
   *
   * 피사체는 우리 워드마크다. 그림을 그리지 않고, 마크를 기계 가공된 물체로
   * 다뤄 빛이 그 위를 지나가게 한다. 카메라의 한 번의 움직임은 아주 얕은
   * rotateY 이고, 스페큘러는 그 회전이 만드는 반사다.
   *
   * 전체가 CSS 다 — canvas 도, 별도, 고리도 없다. 움직이는 건 transform 과
   * opacity 뿐이라 합성기에서만 돈다. */
  var _INTRO = 3600;

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

    /* 움직임을 줄여 달라고 한 사람에게는 크로스페이드. */
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      if (overlay) overlay.classList.add('is-still');
      ns._splashTimers.push(setTimeout(skipSplash, 700));
      return true;
    }

    /* 한 프레임 뒤에 시작해야 초기 상태가 실제로 칠해진 뒤 전환이 걸린다.

       그리고 컷의 시계는 여기서, 시퀀스가 실제로 시작한 프레임에서 출발한다.
       initSplashV2 가 불린 순간부터 재면 부팅이 메인 스레드를 붙잡고 있는 동안
       예산이 흘러가 버린다 — 실측으로 첫 프레임까지 1.2초가 걸렸고, 3.6초짜리
       인트로가 2.4초만에 잘렸다. 느린 기기일수록 더 잘린다. */
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        if (overlay) overlay.classList.add('is-running');

        ns._splashTimers.push(setTimeout(function () {
          if (typeof ns.completeLauncherBoot === 'function') {
            ns.completeLauncherBoot({ revealAnimation: 'skip' });
          }
          if (overlay) overlay.classList.add('is-through');
          ns._splashTimers.push(setTimeout(function () { skipSplash(); }, 300));
        }, _INTRO));
      });
    });

    return true;
  }

  function skipSplash(manual) {
    if (manual === undefined) manual = false;
    var ov = document.getElementById('splashOverlay');
    if (!ov || ov.classList.contains('fade-out')) return;

    ns._splashTimers.forEach(function(id) { clearTimeout(id); });
    ns._splashTimers.length = 0;
    ns._splashActive = false;
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
      '<div class="mark" id="splashMark">' +
        '<span class="mark-face" aria-hidden="true"></span>' +
        '<span class="mark-sweep" aria-hidden="true">' +
          '<span class="mark-shine"></span>' +
        '</span>' +
        '<span class="mark-floor" aria-hidden="true">' +
          '<span class="mark-face"></span>' +
        '</span>' +
        '<span class="mark-a11y">DEEPX</span>' +
      '</div>' +
      '<p class="mark-sub" id="splashSubtitle">AI Studio</p>' +
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
