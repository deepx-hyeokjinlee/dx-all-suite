
(function() {
  var ns = window.DXLauncher;


  /* 인트로 — Gargantua.
   *
   * 레퍼런스는 인터스텔라다. 놀란의 문법은 네온이 아니라 규모와 침묵,
   * 그리고 중력으로 휜 빛이다. 검은 구 하나, 그 뒤를 도는 강착원반, 그리고
   * 원반의 뒷면이 구 위로 휘어 넘어오는 그 형태 — 렌즈 효과가 이 그림의
   * 전부이고, 그게 없으면 그냥 고리다.
   *
   *   1  침묵      1.4s. 별 하나가 표류한다. 아무 일도 일어나지 않는다.
   *   2  가장자리   그 점이 별이 아니라 무언가의 테두리였다. 얇은 호가
   *                휘어 들어오며 구의 실루엣이 드러난다.
   *   3  렌즈      원반의 뒷면이 구 위로 넘어온다. 도플러 비밍으로 한쪽이
   *                더 뜨겁다. 카메라가 천천히 밀고 들어간다.
   *   4  이름      원반의 뜨거운 쪽이 뒤를 지나며 워드마크를 드러낸다.
   *   5  통과      원반이 카메라를 지나쳐 확장한다. 흰 블룸, 그리고 컷.
   *                흰 화면이 걷히면 앱이다 — 페이드가 아니라 컷이다.
   *
   * 약 6.4초. 클릭하면 언제든 건너뛴다.
   *
   * 의존성이 0인 앱이라 canvas 2D 로 직접 그린다. 원반은 각도마다 짧은
   * 호를 그려 만들고, 먼 쪽 절반을 구보다 먼저 그린 뒤 구를 덮고, 가까운
   * 쪽 절반을 그 위에 다시 그린다 — 그 순서가 렌즈처럼 보이게 하는 요령의
   * 전부다. */
  var _T = { hold: 1400, edge: 1500, lens: 1500, name: 1100, through: 900 };
  var _TOTAL = _T.hold + _T.edge + _T.lens + _T.name + _T.through;

  function _ease(t) { return t < 0.5 ? 2*t*t : 1 - Math.pow(-2*t + 2, 2) / 2; }
  function _clamp01(v) { return v < 0 ? 0 : v > 1 ? 1 : v; }

  function _stars(n) {
    var out = [];
    for (var i = 0; i < n; i++) {
      out.push({
        a: Math.random() * Math.PI * 2,          // 방위
        r: 0.15 + Math.random() * 1.25,          // 중심으로부터의 거리(정규화)
        z: 0.35 + Math.random() * 0.65,          // 시차용 깊이
        m: 0.25 + Math.random() * 0.75           // 밝기
      });
    }
    return out;
  }

  /* 한 프레임. p 는 0..1 의 전체 진행도. */
  function _paint(ctx, W, H, stars, ms) {
    var cx = W / 2, cy = H / 2;
    var unit = Math.min(W, H);

    var tEdge = _clamp01((ms - _T.hold) / _T.edge);
    var tLens = _clamp01((ms - _T.hold - _T.edge) / _T.lens);
    var tName = _clamp01((ms - _T.hold - _T.edge - _T.lens) / _T.name);
    var tThru = _clamp01((ms - _TOTAL + _T.through) / _T.through);

    /* 카메라. 침묵 구간엔 거의 멈춰 있고, 마지막에 가속해 지나친다. */
    var zoom = 0.30 + _ease(_clamp01(ms / (_TOTAL - _T.through))) * 0.62
                    + Math.pow(tThru, 2.6) * 5.2;
    var R = unit * 0.115 * zoom;                 // 구 반지름
    var A = R * 2.62;                            // 원반 반장축
    var tilt = 0.148 + 0.052 * _ease(tLens);     // 기울기 → 반단축
    var B = A * tilt;
    var spin = ms / 1000 * 0.42;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, W, H);

    /* 별. 시차로 아주 느리게 흐른다. */
    var drift = ms / 1000 * 0.012;
    for (var i = 0; i < stars.length; i++) {
      var st = stars[i];
      var rr = st.r * unit * 0.62 * (0.55 + zoom * 0.5);
      var x = cx + Math.cos(st.a + drift * st.z) * rr;
      var y = cy + Math.sin(st.a + drift * st.z) * rr * 0.86;
      if (x < -4 || x > W + 4 || y < -4 || y > H + 4) continue;
      ctx.globalAlpha = st.m * 0.7 * (1 - tThru);
      ctx.fillStyle = '#fff';
      ctx.fillRect(x, y, st.z > 0.85 ? 2 : 1, st.z > 0.85 ? 2 : 1);
    }
    ctx.globalAlpha = 1;

    if (tEdge <= 0) return;

    /* 원반. additive 로 여러 겹을 쌓아야 빛이 된다 — 한 겹으로는 아무리
       칠해도 먼지 낀 고리로 보인다. 넓고 어두운 바닥, 그 위에 좁고 뜨거운
       심, 그 위에 흰 코어. 도플러 비밍으로 다가오는 쪽이 훨씬 밝다. */
    function disc(from, to, gain, widthMul) {
      var steps = 150;
      for (var k = 0; k < steps; k++) {
        var a0 = from + (to - from) * (k / steps);
        var a1 = from + (to - from) * ((k + 2.2) / steps);   // 겹쳐야 이음매가 안 보인다
        var beam = Math.pow((Math.cos(a0 + spin) + 1) / 2, 2.1);   // 0..1
        var hot = 0.16 + 0.84 * beam;

        ctx.beginPath(); ctx.ellipse(cx, cy, A, B, 0, a0, a1);
        ctx.strokeStyle = 'rgba(255,' + Math.round(120 + 60 * hot) + ',30,' +
                          (0.42 * gain * hot).toFixed(3) + ')';
        ctx.lineWidth = R * 0.46 * widthMul;
        ctx.stroke();

        ctx.beginPath(); ctx.ellipse(cx, cy, A, B, 0, a0, a1);
        ctx.strokeStyle = 'rgba(255,' + Math.round(186 + 56 * hot) + ',' +
                          Math.round(96 + 96 * hot) + ',' + (0.62 * gain * hot).toFixed(3) + ')';
        ctx.lineWidth = R * 0.22 * widthMul;
        ctx.stroke();

        if (hot > 0.42) {
          ctx.beginPath(); ctx.ellipse(cx, cy, A, B, 0, a0, a1);
          ctx.strokeStyle = 'rgba(255,252,242,' + (0.85 * gain * (hot - 0.42) / 0.58).toFixed(3) + ')';
          ctx.lineWidth = R * 0.085 * widthMul;
          ctx.stroke();
        }
      }
    }

    ctx.save();
    ctx.globalCompositeOperation = 'lighter';

    /* 원반 평면의 번짐. 이게 있어야 빛이 공간에 있는 것처럼 보인다. */
    var glow = ctx.createRadialGradient(cx, cy, R * 0.9, cx, cy, A * 1.5);
    glow.addColorStop(0, 'rgba(255,170,72,' + (0.20 * tEdge).toFixed(3) + ')');
    glow.addColorStop(0.45, 'rgba(255,138,42,' + (0.09 * tEdge).toFixed(3) + ')');
    glow.addColorStop(1, 'rgba(255,120,30,0)');
    ctx.save();
    ctx.translate(cx, cy); ctx.scale(1, tilt * 3.1); ctx.translate(-cx, -cy);
    ctx.fillStyle = glow;
    ctx.beginPath(); ctx.arc(cx, cy, A * 1.5, 0, Math.PI * 2); ctx.fill();
    ctx.restore();

    /* 먼 쪽 절반 — 구보다 먼저. */
    disc(Math.PI, Math.PI * 2, tEdge, 1);

    /* 렌즈. 원반의 뒷면이 구 위로 넘어온 상(像). 이게 Gargantua 다. */
    if (tLens > 0) {
      /* 위로 넘어오는 상과 아래로 도는 상, 둘 다 있어야 구가 빛에 감싸인
         것처럼 보인다. 위쪽 상은 구 반지름보다 확실히 높이 떠야 한다 —
         구에 붙어 있으면 뿔 두 개로 보이지 호로 안 보인다. */
      var lift = R * (1.42 + 0.10 * _ease(tLens));
      var squash = 0.86;
      [[Math.PI, Math.PI * 2, 1.0], [0, Math.PI, 0.42]].forEach(function (half) {
        for (var k2 = 0; k2 < 130; k2++) {
          var b0 = half[0] + Math.PI * (k2 / 130);
          var b1 = half[0] + Math.PI * ((k2 + 2.2) / 130);
          var bm = Math.pow((Math.cos(b0 + spin) + 1) / 2, 1.7);
          var bh = 0.18 + 0.82 * bm;
          var g = tLens * half[2];
          ctx.beginPath(); ctx.ellipse(cx, cy, lift, lift * squash, 0, b0, b1);
          ctx.strokeStyle = 'rgba(255,' + Math.round(170 + 70 * bh) + ',' +
                            Math.round(78 + 118 * bh) + ',' + (0.55 * g * bh).toFixed(3) + ')';
          ctx.lineWidth = R * 0.10;
          ctx.stroke();
          if (bh > 0.45) {
            ctx.beginPath(); ctx.ellipse(cx, cy, lift, lift * squash, 0, b0, b1);
            ctx.strokeStyle = 'rgba(255,250,238,' + (0.62 * g * (bh - 0.45) / 0.55).toFixed(3) + ')';
            ctx.lineWidth = R * 0.035;
            ctx.stroke();
          }
        }
      });
    }
    ctx.restore();

    /* 사건의 지평선. 빛이 아니라 빛의 부재다 — 원반과 맞닿는 가장자리를
       한 번 더 검게 깔아야 번짐이 구 안으로 새지 않는다. */
    var halo = ctx.createRadialGradient(cx, cy, R * 0.92, cx, cy, R * 1.34);
    halo.addColorStop(0, 'rgba(0,0,0,1)');
    halo.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = halo;
    ctx.beginPath(); ctx.arc(cx, cy, R * 1.34, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#000';
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill();

    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    /* 광자구 — 지평선을 두르는 실선. */
    ctx.beginPath(); ctx.arc(cx, cy, R * 1.035, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,226,176,' + (0.55 * tLens).toFixed(3) + ')';
    ctx.lineWidth = Math.max(1, R * 0.028);
    ctx.stroke();

    /* 가까운 쪽 절반 — 구를 덮는다. */
    disc(0, Math.PI, tEdge * 1.06, 1.04);
    ctx.restore();

    /* 통과. 흰 블룸이 화면을 씻는다. */
    if (tThru > 0) {
      var bloom = ctx.createRadialGradient(cx, cy, 0, cx, cy, unit * (0.25 + tThru * 1.5));
      var a = Math.pow(tThru, 1.5);
      bloom.addColorStop(0, 'rgba(255,248,236,' + a.toFixed(3) + ')');
      bloom.addColorStop(1, 'rgba(255,248,236,0)');
      ctx.fillStyle = bloom;
      ctx.fillRect(0, 0, W, H);
    }
    return tName;
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
    var logo = document.getElementById('splashLogo');
    var canvas = document.getElementById('splashSky');

    /* 움직임을 줄여 달라고 한 사람에게 6초짜리 카메라는 방해다. */
    if (!canvas || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      if (logo) logo.classList.add('is-revealed');
      ns._splashTimers.push(setTimeout(skipSplash, 700));
      return true;
    }

    var ctx = canvas.getContext('2d');
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var W, H;
    function size() {
      W = canvas.clientWidth; H = canvas.clientHeight;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    size();
    ns._splashResize = size;
    window.addEventListener('resize', size);

    var stars = _stars(window.innerWidth < 700 ? 130 : 260);
    var t0 = performance.now();
    var named = false;

    function frame(now) {
      if (!ns._splashActive) return;
      var ms = now - t0;
      _paint(ctx, W, H, stars, ms);
      /* 4박자: 원반의 뜨거운 쪽이 뒤를 지날 때 이름이 드러난다. */
      if (!named && ms >= _T.hold + _T.edge + _T.lens) {
        named = true;
        if (logo) logo.classList.add('is-revealed');
      }
      if (ms < _TOTAL) ns._splashRAF = requestAnimationFrame(frame);
    }
    ns._splashRAF = requestAnimationFrame(frame);

    /* 5박자: 블룸이 화면을 덮은 순간 앱을 켜고, 흰 막을 걷는다 — 컷이다. */
    ns._splashTimers.push(setTimeout(function () {
      if (typeof ns.completeLauncherBoot === 'function') {
        ns.completeLauncherBoot({ revealAnimation: 'skip' });
      }
      if (overlay) overlay.classList.add('is-through');
      ns._splashTimers.push(setTimeout(function () { skipSplash(); }, 260));
    }, _TOTAL - 90));

    return true;
  }

  function skipSplash(manual) {
    if (manual === undefined) manual = false;
    var ov = document.getElementById('splashOverlay');
    if (!ov || ov.classList.contains('fade-out')) return;

    ns._splashTimers.forEach(function(id) { clearTimeout(id); });
    ns._splashTimers.length = 0;
    /* 카메라를 멈추고 창 리스너를 거둔다 — 인트로가 끝나도 프레임이 계속
       도는 것이 오래된 스플래시들의 단골 누수였다. */
    ns._splashActive = false;
    if (ns._splashRAF) { cancelAnimationFrame(ns._splashRAF); ns._splashRAF = null; }
    if (ns._splashResize) { window.removeEventListener('resize', ns._splashResize); ns._splashResize = null; }
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
      '<canvas class="splash-sky" id="splashSky"></canvas>' +
      '<div class="splash-logo-hud" id="splashLogoHud">' +
        '<div class="splash-logo" id="splashLogo">DEEPX</div>' +
        '<div class="splash-subtitle" id="splashSubtitle">AI Studio</div>' +
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
