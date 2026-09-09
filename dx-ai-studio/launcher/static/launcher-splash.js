
(function() {
  var ns = window.DXLauncher;

  /* 인트로.
   *
   * 앞선 시도들은 전부 장르를 빌려왔다 — 네온 회로, 그리고 강착원반을 두른
   * 블랙홀. 레퍼런스를 "어떻게 판단할지"가 아니라 "무엇을 그릴지"로 받으면
   * 매번 남의 영화 포스터를 제품 앞에 붙이게 된다.
   *
   * 그래서 애플과 구글 광고의 문법을 찾아 읽고 그대로 적용했다.
   *
   * 애플: hero reveal → detail → context shot(제품이 실제로 쓰이는 장면) → 주장
   * 하나. 파는 것은 광고가 아니라 제품이다. 그리고:
   *
   *   · 피사체는 하나, 무대는 검은 여백 (요소 주변 최소 20%)
   *   · 카메라는 한 번만 움직이고, 그 움직임이 무언가를 드러낸다
   *   · transform 과 opacity 만 애니메이션한다 (compositor-friendly)
   *   · 스프링: damping 1.0, response 0.3–0.4s. 급히 시작하거나 멈추지 않는다
   *   · 큰 글자는 자간을 조이고(-0.02em), 타입은 마지막에 온다
   *   · 시그니처는 표면을 훑고 지나가는 하드 스페큘러
   *   · reduced motion 은 opacity 크로스페이드로 대체
   *
   * 구글 〈Parisian Love〉: 60초 전체를 배우도 대사도 그림도 없이, 제품의
   * 입력창에 타이핑되는 문장들만으로 끌고 간다. 추론이 일을 한다.
   *
   * 두 레퍼런스가 같은 곳을 가리킨다. 이 제품의 전제가 "원하는 걸 말하면
   * 만들어준다"이므로, 애플의 context shot 과 구글의 검색어 시퀀스는 같은
   * 장면이다 — 제품이 일하는 장면. 그래서 인트로는 세 박자다:
   *
   *   1. hero    로고타입이 가공된 물체로 도착하고, 빛이 표면을 훑는다
   *   2. work    프롬프트 셋이 타이핑되고, 스튜디오가 모듈로 답한다
   *   3. close   프롬프트가 걷히고 마크가 이름과 함께 남는다
   *
   * 2번의 문구는 지어낸 카피가 아니다 — 홈의 Build 예시 칩에 이미 있고 이미
   * 6개 언어로 번역돼 있는 실제 프롬프트다. 답은 그 요청을 실제로 맡는 모듈
   * 이름이고, 모듈명은 고유명사라 번역이 필요 없다. 광고가 주장하는 것이
   * 아니라 제품이 하는 일을 그대로 보여주는 것이다. */

  /* 타이핑은 setTimeout 스케줄이지 프레임 루프가 아니다. 글자 수가 언어마다
     다르므로 글자당 속도가 아니라 총 시간을 고정한다 — 한국어와 영어가 같은
     박자로 끝나야 시퀀스가 어긋나지 않는다. */
  var _TYPE_MS = 900;
  var _BEAT = 1950;
  var _WORK = [
    { ask: '4-channel CCTV object detection', by: 'Stream' },
    { ask: 'segment a video file',            by: 'App' },
    { ask: 'compile yolo26n to DXNN',         by: 'Compiler' }
  ];
  /* hero 의 부제("AI Studio")는 CSS 가 1.9s 에 띄운다. work 는 그게 자리를
     잡고 한 박자 쉰 다음에 시작해야 한다 — 처음엔 2.8s 로 잡았더니 부제가
     250ms 만에 밀려나서, 있었는지도 모르게 지나갔다. */
  var _WORK_IN  = 3400;
  var _CLOSE    = _WORK_IN + _BEAT * 3;       /* 9250 */
  var _INTRO    = _CLOSE + 1650;              /* 10900 */

  function _t(key) {
    return (window.DXI18n && window.DXI18n.T) ? window.DXI18n.T(key) : key;
  }

  function _later(fn, ms) { ns._splashTimers.push(setTimeout(fn, ms)); }

  function _type(el, text) {
    var i = 0;
    var step = Math.max(18, Math.round(_TYPE_MS / Math.max(text.length, 1)));
    el.textContent = '';
    (function tick() {
      if (i >= text.length) return;
      i += 1;
      el.textContent = text.slice(0, i);
      _later(tick, step);
    })();
  }

  /* 한 박자: 요청이 타이핑되고, 스튜디오가 답하고, 둘 다 물러난다. */
  function _beat(item, index, at) {
    var cue = document.getElementById('splashCue');
    var text = document.getElementById('splashCueText');
    var answer = document.getElementById('splashCueAnswer');
    if (!cue || !text || !answer) return;
    _later(function () {
      cue.classList.remove('is-answered', 'is-out');
      cue.setAttribute('data-beat', String(index));
      answer.textContent = item.by;
      _type(text, _t(item.ask));
    }, at);
    _later(function () { cue.classList.add('is-answered'); }, at + _TYPE_MS + 260);
    _later(function () { cue.classList.add('is-out'); }, at + _BEAT - 260);
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

        /* 2. work — 이름이 물러나고 그 자리에서 제품이 일한다. */
        _later(function () { if (overlay) overlay.classList.add('is-working'); }, _WORK_IN - 400);
        for (var i = 0; i < _WORK.length; i++) {
          _beat(_WORK[i], i, _WORK_IN + _BEAT * i);
        }

        /* 3. close — 프롬프트가 걷히고 마크가 이름과 함께 남는다. */
        _later(function () {
          if (!overlay) return;
          overlay.classList.remove('is-working');
          overlay.classList.add('is-closed');
        }, _CLOSE);

        /* 마지막: 앱을 켜고 마크째로 나간다 — 페이드가 아니라 컷이다. */
        _later(function () {
          if (typeof ns.completeLauncherBoot === 'function') {
            ns.completeLauncherBoot({ revealAnimation: 'skip' });
          }
          if (overlay) overlay.classList.add('is-through');
          _later(function () { skipSplash(); }, 300);
        }, _INTRO);
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
      '<div class="mark-slot">' +
        '<p class="mark-sub" id="splashSubtitle">AI Studio</p>' +
      '<div class="mark-cue" id="splashCue" aria-hidden="true">' +
        '<div class="cue-scene" aria-hidden="true">' +
          '<img class="cue-shot" data-beat="0" src="/static/img/intro/scene-detect.svg" alt="Four camera channels with people and vehicles boxed as they are detected">' +
          '<img class="cue-shot" data-beat="1" src="/static/img/intro/scene-segment.svg" alt="A street segmented into road, vehicle, person and vegetation classes">' +
          '<img class="cue-shot" data-beat="2" src="/static/img/intro/scene-silicon.svg" alt="The DX-M1 die the models are compiled down to">' +
        '</div>' +
        '<span class="cue-line"><span class="cue-text" id="splashCueText"></span>' +
        '<i class="cue-caret"></i></span>' +
        '<span class="cue-answer" id="splashCueAnswer"></span>' +
      '</div>' +
      '</div>' +
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
