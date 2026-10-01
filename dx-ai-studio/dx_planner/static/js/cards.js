/**
 * CardRenderer — Step 2 추천 카드 렌더링.
 * GaugeChart.draw()로 각 카드에 미니 게이지 그림.
 */
const CardRenderer = {
  _detailCb: null,

  onDetailClick(cb) { this._detailCb = cb; },
  onCompareChange() {},

  render(results, inputs) {
    const container = document.getElementById('recommend-cards');
    if (!container) return;
    container.innerHTML = '';

    // 60fps 배너
    const banner = document.getElementById('fps-banner');
    if (banner) {
      banner.style.display = inputs.targetFps >= 60 ? '' : 'none';
    }

    if (results.length === 0) {
      container.innerHTML = this._emptyState();
      this._applyLang();
      return;
    }

    results.forEach((r, i) => {
      container.appendChild(this._buildCard(r, i, inputs));
    });

    // 게이지 렌더링 (charts.js 로드 후)
    if (typeof GaugeChart !== 'undefined') {
      results.forEach((r, i) => {
        const cv = container.querySelectorAll('.gauge-canvas')[i];
        if (cv) GaugeChart.draw(cv, r.maxChannels, inputs.cameras, r.boundaryFlag);
      });
    }
    this._applyLang();
  },

  _confidenceBadge(flag) {
    const labels = {
      measured: { ko: '실측', en: 'Measured', ja: '実測', 'zh-CN': '实测', 'zh-TW': '實測', es: 'Medido' },
      '+': { ko: '실측+', en: 'Measured+', ja: '実測+', 'zh-CN': '实测+', 'zh-TW': '實測+', es: 'Medido+' },
    };
    const key = flag || 'measured';
    const text = labels[key] || labels.measured;
    const lang = typeof DXI18n !== 'undefined' ? DXI18n.lang : 'en';
    const shown = text[lang] || text.en;
    return '<span class="badge badge-confidence" data-confidence="' + key + '">' + shown + '</span>';
  },

  // 순위는 숫자 원 — 1위만 금빛 (메달 이모지는 OS 마다 다르게 그려졌다, 아이콘 체계 단계 5).
  _rankBadge(i) {
    return '<span class="rank-disc' + (i === 0 ? ' rank-disc--top' : '') + '">' + (i + 1) + '</span>';
  },

  _ico(name) {
    return (typeof window.DXIcon === 'function') ? window.DXIcon(name) : '';
  },

  _buildCard(r, idx, inputs) {
    const pid = r.platform.id;
    const meets = r.meetsRequirement;
    const confidenceBadge = this._confidenceBadge(r.boundaryFlag);

    const card = document.createElement('div');
    card.className = 'rec-card ' + (meets ? 'card-meets' : 'card-insufficient') +
      (idx === 0 ? ' rec-card--featured' : '');
    card.dataset.platformId = pid;
    card.dataset.index = idx;
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.setAttribute('aria-label', r.platform.npu.model + ' + ' + r.platform.host.name);

    const chVal = this._formatChannels(r.maxChannels, r.boundaryFlag);
    const benchmarkMeta = this._benchmarkMeta(pid);
    const statusBadge = meets
      ? '<span class="badge badge-meets">' + this._ico('check') + ' <span data-i18n="Meets">Meets</span></span>'
      : '<span class="badge badge-insufficient">' + this._ico('alert') + ' <span data-i18n="Insufficient">Insufficient</span></span>';
    const featuredBadge = idx === 0
      ? '<span class="badge badge-featured" data-i18n="Top pick">Top pick</span>'
      : '';


    const topoLine = typeof RecommendEngine !== 'undefined'
      ? RecommendEngine._topologyLabel(r.platform)
      : '';

    card.innerHTML =
      '<div class="card-rank">' + this._rankBadge(idx) + '</div>' +
      '<div class="card-header">' +
        '<h3>' + r.platform.npu.model + ' + ' + r.platform.host.name + '</h3>' +
        (topoLine ? '<p class="card-topology txt-dim txt-sm">' + this._escHtml(topoLine) + '</p>' : '') +
        '<div class="card-badges">' + featuredBadge + confidenceBadge + statusBadge + '</div>' +
      '</div>' +
      '<div class="card-metrics">' +
        this._metric(String(Math.round(r.throughputFps)), 'FPS') +
        this._metric(chVal,
          '<span data-i18n="Ch">Ch</span>') +
        this._metric(r.platform.npu.tdp_w + 'W', 'TDP') +
      '</div>' +
      benchmarkMeta +
      '<div class="card-gauge"><canvas class="gauge-canvas" width="60" height="60"></canvas></div>' +
      '<div class="card-actions">' +
        '<button class="btn-detail" data-platform-id="' + pid + '">' +
          '<span data-i18n="Details">Details</span>' +
        '</button>' +
      '</div>';

    // 이벤트
    card.querySelector('.btn-detail').addEventListener('click', () => {
      if (this._detailCb) this._detailCb(pid);
    });

    card.addEventListener('click', (event) => {
      if (event.target.closest('button')) return;
      if (this._detailCb) this._detailCb(pid);
    });

    card.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        if (this._detailCb) this._detailCb(pid);
      }
    });

    // boundaryFlag "+" 툴팁
    if (r.boundaryFlag === '+') {
      const chMetric = card.querySelectorAll('.metric')[1];
      if (chMetric) {
        chMetric.title = ({ko:'측정 범위 내 최대값', ja:'計測範囲内の最大値', 'zh-CN':'测量范围内的最大值', 'zh-TW':'測量範圍內的最大值'}[(typeof DXI18n !== 'undefined' ? DXI18n.lang : 'en')] || 'Maximum within measured range');
      }
    }

    return card;
  },

  _formatChannels(val, flag) {
    if (flag === '+') return val + '+';
    return String(val);
  },

  _formatNumber(value, digits) {
    return Number(value).toFixed(digits).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
  },

  _escHtml(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  },

  _benchmarkMeta(pid) {
    const generated = typeof DataLoader !== 'undefined' ? DataLoader.getGeneratedAt() : null;
    const benchmarkDate = typeof DataLoader !== 'undefined' ? DataLoader.getBenchmarkDate(pid) : null;
    const stale = typeof DataLoader !== 'undefined' ? DataLoader.isBenchmarkStale(pid) : false;
    const generatedText = generated ? generated.slice(0, 10) : 'N/A';
    const benchmarkText = benchmarkDate || 'N/A';
    const staleBadge = stale
      ? '<span class="badge badge-stale" data-i18n="Benchmark stale">Benchmark stale</span>'
      : '';
    return '<div class="card-release-meta">' +
      '<span data-i18n="Generated">Generated</span>: ' + generatedText +
      ' · <span data-i18n="Benchmark">Benchmark</span>: ' + benchmarkText +
      staleBadge +
    '</div>';
  },

  _emptyState() {
    return '<div class="empty-state planner-empty-recommendations">' +
      '<strong data-i18n="No matching recommendations">No matching recommendations</strong>' +
      '<p data-i18n="Try relaxing FPS, channel, or model-size requirements.">Try relaxing FPS, channel, or model-size requirements.</p>' +
    '</div>';
  },

  _metric(value, label) {
    return '<div class="metric">' +
      '<span class="metric-value">' + value + '</span>' +
      '<span class="metric-label">' + label + '</span>' +
    '</div>';
  },

  _applyLang() {
    if (typeof DXI18n !== 'undefined' && typeof DXI18n.applyLang === 'function') {
      DXI18n.applyLang();
    }
  },
};
if (typeof registerPlannerLangRefresher === 'function') {
  registerPlannerLangRefresher(function() {
    if (typeof DXI18n !== 'undefined' && DXI18n.applyLang) DXI18n.applyLang(document);
  });
}
