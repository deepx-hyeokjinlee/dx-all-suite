(function() {
  'use strict';

  let _aboutData = null;
  let _aboutInitialized = false;
  let _scrollSpyObserver = null;
  let _fadeObserver = null;
  let _languageHookRegistered = false;

  const SUPPORTED_LANGS = ['en', 'ja', 'ko', 'es', 'zh-CN', 'zh-TW'];

  const ABOUT_NAV_LABELS = {
    aboutDeveloper:  { en: 'Developer',  ko: '개발자',     ja: '開発者',   es: 'Desarrollador','zh-CN': '开发者', 'zh-TW': '開發者' },
    aboutCompany:    { en: 'Company',    ko: '회사',       ja: '企業',     es: 'Empresa',    'zh-CN': '公司',   'zh-TW': '公司' },
    aboutTech:       { en: 'Technology', ko: '기술',       ja: '技術',     es: 'Tecnología', 'zh-CN': '技术',   'zh-TW': '技術' },
    aboutProducts:   { en: 'Products',   ko: '제품',       ja: '製品',     es: 'Productos',  'zh-CN': '产品',   'zh-TW': '產品' },
    aboutPartners:   { en: 'Partners',   ko: '파트너',     ja: 'パートナー', es: 'Socios',     'zh-CN': '合作伙伴', 'zh-TW': '合作夥伴' },
    aboutInvestment: { en: 'Awards',     ko: '수상',       ja: '受賞',     es: 'Premios',    'zh-CN': '奖项',   'zh-TW': '獎項' },
    aboutNews:       { en: 'News',       ko: '뉴스',       ja: 'ニュース', es: 'Noticias',   'zh-CN': '新闻',   'zh-TW': '新聞' }
  };

  function currentLang() {
    if (typeof DXI18n !== 'undefined' && DXI18n.lang) return DXI18n.lang;
    return localStorage.getItem('dx-lang') || 'en';
  }

  function T(map) {
    var lang = currentLang();
    if (typeof map === 'string') return map;
    return map[lang] || map.en || '';
  }

  function L(field) {
    if (!field) return '';
    if (typeof field === 'string') return field;
    return T(field);
  }

  function stripUrlHost(url) {
    return String(url).replace(/^https?:\/\//, '');
  }

  function renderNewsCard(item, accent) {
    var loc = item.location ? `<div class="about-news-location">${L(item.location)}</div>` : '';
    var titleHtml = L(item.title);
    if (item.url) {
      titleHtml = `<a class="about-news-link" href="${item.url}" target="_blank" rel="noopener noreferrer">${titleHtml} ↗</a>`;
    }
    return `<div class="about-news-card about-fade-in${accent ? ' about-news-card--upcoming' : ''}${item.url ? ' about-news-card--linked' : ''}">
      <div class="about-news-type">${item.type || 'event'}</div>
      <div class="about-news-title">${titleHtml}</div>
      <div class="about-news-meta">${item.date || ''}</div>${loc}
    </div>`;
  }

  function renderDeveloperHub(container, data) {
    const d = data.developer;
    if (!d) return;
    const mz = d.modelZooSnapshot || {};
    const rel = d.sdkRelease || {};
    const el = document.createElement('section');
    el.className = 'about-section about-developer-hub';
    el.id = 'aboutDeveloper';
    el.innerHTML = `
      <div class="about-section-divider"></div>
      <h2 class="about-section-title">${L(d.title)}</h2>
      <p class="about-section-subtitle">${L(d.subtitle)}</p>

      <div class="about-dev-banner about-fade-in">
        <div class="about-dev-banner-item">
          <span class="about-dev-banner-k">${rel.version || '—'}</span>
          <span class="about-dev-banner-v">${L(rel.summary)}</span>
        </div>
        <div class="about-dev-banner-item">
          <span class="about-dev-banner-k">${mz.count || '—'}</span>
          <span class="about-dev-banner-v">${T({en:'Model Zoo models',ko:'Model Zoo 모델',ja:'Model Zooモデル','zh-CN':'Model Zoo 模型','zh-TW':'Model Zoo 模型',es:'Modelos Model Zoo'})} · ${T({en:'as of',ko:'기준',ja:'時点', 'zh-CN':'截至','zh-TW':'截至',es:'a'})} ${mz.asOf || '—'}</span>
        </div>
        <a class="about-dev-support" href="mailto:${d.supportEmail}">${d.supportEmail}</a>
      </div>

      <div class="about-action-grid">
        ${d.links.map(function (link) {
          return `<a class="about-action-card about-fade-in" href="${link.url}" target="_blank" rel="noopener noreferrer">
            <span class="about-action-icon">${link.icon}</span>
            <span class="about-action-label">${L(link.label)}</span>
            <span class="about-action-desc">${L(link.desc)}</span>
          </a>`;
        }).join('')}
      </div>

      ${d.ctas && d.ctas.length ? `
      <div class="about-cta-row about-fade-in">
        ${d.ctas.map(function (cta) {
          return `<a class="about-cta-btn${cta.primary ? ' about-cta-btn--primary' : ''}" href="${cta.url}" target="_blank" rel="noopener noreferrer">${L(cta.label)}</a>`;
        }).join('')}
      </div>` : ''}

      ${data.distribution ? `
      <h3 class="about-tech-title about-fade-in">${L(data.distribution.title)}</h3>
      <div class="about-distribution-row about-fade-in">
        ${data.distribution.channels.map(function (c) {
          const inner = `<div class="about-distribution-name">${c.name}</div>
            <div class="about-distribution-region">${L(c.region)}</div>`;
          return c.url
            ? `<a class="about-distribution-card" href="${c.url}" target="_blank" rel="noopener noreferrer">${inner}</a>`
            : `<div class="about-distribution-card">${inner}</div>`;
        }).join('')}
      </div>` : ''}
    `;
    container.appendChild(el);
  }

  async function loadData() {
    if (_aboutData) return _aboutData;
    // Guard against a pending fetch (e.g. the launcher still saturated during early boot)
    // turning into an infinite loading spinner — abort after 10s so the catch in
    // initAboutView surfaces a retry instead of hanging forever.
    const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const timer = ctrl ? setTimeout(function () { ctrl.abort(); }, 10000) : null;
    try {
      const opts = { cache: 'no-store' };
      if (ctrl) opts.signal = ctrl.signal;
      const r = await fetch('/static/about-data.json', opts);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      _aboutData = await r.json();
      return _aboutData;
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  function renderHero(container, data) {
    const hero = data.hero;
    const el = document.createElement('section');
    el.className = 'about-hero';
    el.id = 'aboutHero';
    el.innerHTML = `
      <h1 class="about-hero-slogan">${L(hero.slogan)}</h1>
      <p class="about-hero-subtitle">${L(hero.subtitle)}</p>
      <div class="about-hero-stats">
        ${hero.stats.map(s => `
          <div class="about-hero-stat">
            <div class="about-hero-stat-value">${s.value}</div>
            <div class="about-hero-stat-label">${L(s.label)}</div>
          </div>
        `).join('')}
      </div>
      <div class="about-scroll-hint">▼</div>
    `;
    container.appendChild(el);
  }

  function renderCompany(container, data) {
    const c = data.company;
    const el = document.createElement('section');
    el.className = 'about-section';
    el.id = 'aboutCompany';
    el.innerHTML = `
      <div class="about-section-divider"></div>
      <h2 class="about-section-title">${T({en:'Company Story', ko:'회사 이야기', ja:'企業ストーリー', 'zh-CN':'公司故事', 'zh-TW':'公司故事', es:'Historia de la empresa'})}</h2>
      <p class="about-section-subtitle">${T({en:'The journey of making AI accessible everywhere', ko:'AI를 어디서나 접근 가능하게 만드는 여정', ja:'あらゆる場所でAIをアクセス可能にする旅', 'zh-CN':'让AI无处不在的旅程', 'zh-TW':'讓AI無處不在的旅程', es:'El camino para hacer la IA accesible en todas partes'})}</p>

      <div class="about-quote about-fade-in">
        <div class="about-quote-text">"${L(c.vision_quote.text)}"</div>
        <div class="about-quote-author">— ${c.vision_quote.author}</div>
      </div>

      <p class="about-overview-text about-fade-in">${L(c.overview)}</p>

      <div class="about-values-grid">
        ${c.values.map(v => `
          <div class="about-value-card about-fade-in">
            <div class="about-value-icon">${v.icon}</div>
            <div class="about-value-title">${L(v.title)}</div>
            <div class="about-value-desc">${L(v.desc)}</div>
          </div>
        `).join('')}
      </div>

      <h3 class="about-tech-title about-fade-in">${T({en:'Milestones', ko:'마일스톤', ja:'マイルストーン', 'zh-CN':'里程碑', 'zh-TW':'里程碑', es:'Hitos'})}</h3>
      <div class="about-timeline about-fade-in">
        ${c.timeline.map(t => `
          <div class="about-timeline-item">
            <div class="about-timeline-dot"></div>
            <div class="about-timeline-year">${t.year}</div>
            <div class="about-timeline-event">${L(t.event)}</div>
          </div>
        `).join('')}
      </div>

      <h3 class="about-tech-title about-fade-in">${T({en:'Global Offices', ko:'글로벌 오피스', ja:'グローバルオフィス', 'zh-CN':'全球办公室', 'zh-TW':'全球辦公室', es:'Oficinas globales'})}</h3>
      <div class="about-offices-grid">
        ${c.offices.map(o => `
          <div class="about-office-card about-fade-in">
            <div class="about-office-city">${L(o.city)}</div>
            <div class="about-office-country">${L(o.country)}</div>
            ${o.address ? `<div class="about-office-address">${o.address}</div>` : ''}
          </div>
        `).join('')}
      </div>

      ${data.contact ? `
      <div class="about-contact-block about-fade-in">
        <h3 class="about-tech-title">${L(data.contact.label)}</h3>
        <a class="about-contact-email" href="mailto:${data.contact.email}">${data.contact.email}</a>
        <a class="about-contact-portal" href="${data.contact.portalUrl}" target="_blank" rel="noopener noreferrer">${T({en:'Developer Portal →', ko:'Developer Portal →', ja:'Developer Portal →', 'zh-CN':'开发者门户 →', 'zh-TW':'開發者入口 →', es:'Portal de desarrolladores →'})}</a>
      </div>` : ''}
    `;
    container.appendChild(el);
  }

  function renderTechnology(container, data) {
    const t = data.technology;
    const el = document.createElement('section');
    el.className = 'about-section';
    el.id = 'aboutTech';
    el.innerHTML = `
      <div class="about-section-divider"></div>
      <h2 class="about-section-title">${T({en:'Technology', ko:'기술', ja:'技術', 'zh-CN':'技术', 'zh-TW':'技術', es:'Tecnología'})}</h2>
      <p class="about-section-subtitle">${T({en:'Purpose-built AI silicon and complete deployment toolchain', ko:'목적 설계 AI 실리콘과 완전한 배포 툴체인', ja:'専用設計AIシリコンと完全なデプロイツールチェーン', 'zh-CN':'专用AI芯片与完整部署工具链', 'zh-TW':'專用AI晶片與完整部署工具鏈', es:'Silicio de IA diseñado a medida y cadena completa de despliegue'})}</p>

      <div class="about-tech-block about-fade-in">
        <h3 class="about-tech-title">${L(t.iq8.title)}</h3>
        <div class="about-quote">
          <div class="about-quote-text">"${L(t.iq8.quote.text)}"</div>
          <div class="about-quote-author">— ${t.iq8.quote.author}</div>
        </div>
        <p class="about-tech-desc">${L(t.iq8.description)}</p>
        <div class="about-stats-row">
          ${t.iq8.stats.map(s => `
            <div class="about-stat-card">
              <div class="about-stat-value">${s.value}</div>
              <div class="about-stat-label">${L(s.label)}</div>
            </div>
          `).join('')}
        </div>
      </div>

      ${t.npu ? `
      <div class="about-tech-block about-fade-in">
        <h3 class="about-tech-title">${L(t.npu.title)}</h3>
        <p class="about-tech-desc">${L(t.npu.description)}</p>
        <div class="about-stats-row">
          ${t.npu.stats.map(s => `
            <div class="about-stat-card">
              <div class="about-stat-value">${s.value}</div>
              <div class="about-stat-label">${L(s.label)}</div>
            </div>
          `).join('')}
        </div>
      </div>` : ''}

      <div class="about-tech-block about-fade-in">
        <h3 class="about-tech-title">${L(t.sdk.title)}</h3>
        <p class="about-tech-desc">${L(t.sdk.description)}</p>
        ${t.sdk.components ? `<p class="about-tech-desc about-sdk-components">${t.sdk.components.map(function (c) { return L(c); }).join(' · ')}</p>` : ''}
        <div class="about-sdk-steps">
          ${t.sdk.steps.map(s => `
            <div class="about-sdk-step">
              <div class="about-sdk-step-num">${s.num}</div>
              <div class="about-sdk-step-title">${L(s.title)}</div>
              <div class="about-sdk-step-desc">${L(s.desc)}</div>
            </div>
          `).join('')}
        </div>
        <div class="about-stats-row">
          ${t.sdk.stats.map(s => `
            <div class="about-stat-card">
              <div class="about-stat-value">${s.value}</div>
              <div class="about-stat-label">${L(s.label)}</div>
            </div>
          `).join('')}
        </div>
        ${t.sdk.release ? `<p class="about-sdk-release about-fade-in"><strong>${t.sdk.release.version}</strong> — ${L(t.sdk.release.summary)}</p>` : ''}
        ${t.sdk.versions ? `<p class="about-sdk-versions about-fade-in">dx-com ${t.sdk.versions.dxCom} · dx-rt ${t.sdk.versions.dxRt}</p>` : ''}
        ${t.sdk.startHere ? `<a class="about-start-here about-fade-in" href="${t.sdk.startHere.url}" target="_blank" rel="noopener noreferrer">${L(t.sdk.startHere.label)} →</a>` : ''}
      </div>
    `;
    container.appendChild(el);
  }

  function renderProducts(container, data) {
    const p = data.products;
    const el = document.createElement('section');
    el.className = 'about-section';
    el.id = 'aboutProducts';

    function productCard(item) {
      let html = `<div class="about-product-card ${item.highlight ? 'highlight' : ''} about-fade-in">
        <div class="about-product-name">${item.name}</div>
        <div class="about-product-type">${L(item.type)}</div>
        <div class="about-product-spec"><span class="about-product-spec-label">${T({en:'Performance', ko:'성능', ja:'性能', 'zh-CN':'性能', 'zh-TW':'效能', es:'Rendimiento'})}</span><span class="about-product-spec-value">${item.tops}</span></div>
        <div class="about-product-spec"><span class="about-product-spec-label">${T({en:'Power', ko:'전력', ja:'電力', 'zh-CN':'功耗', 'zh-TW':'功耗', es:'Potencia'})}</span><span class="about-product-spec-value">${item.power}</span></div>
        <div class="about-product-spec"><span class="about-product-spec-label">${T({en:'Memory', ko:'메모리', ja:'メモリ', 'zh-CN':'内存', 'zh-TW':'記憶體', es:'Memoria'})}</span><span class="about-product-spec-value">${L(item.memory)}</span></div>
        <div class="about-product-spec"><span class="about-product-spec-label">${T({en:'Interface', ko:'인터페이스', ja:'インターフェース', 'zh-CN':'接口', 'zh-TW':'介面', es:'Interfaz'})}</span><span class="about-product-spec-value">${item.interface}</span></div>`;
      if (item.os) html += `<div class="about-product-spec"><span class="about-product-spec-label">${T({en:'OS', ko:'OS', ja:'OS', 'zh-CN':'操作系统', 'zh-TW':'作業系統', es:'SO'})}</span><span class="about-product-spec-value">${L(item.os)}</span></div>`;
      if (item.temp) html += `<div class="about-product-spec"><span class="about-product-spec-label">${T({en:'Temp', ko:'온도', ja:'温度', 'zh-CN':'温度', 'zh-TW':'溫度', es:'Temp.'})}</span><span class="about-product-spec-value">${L(item.temp)}</span></div>`;
      html += `<div class="about-product-spec" style="border:none"><span class="about-product-spec-label">${T({en:'Form Factor', ko:'폼팩터', ja:'フォームファクタ', 'zh-CN':'规格', 'zh-TW':'規格', es:'Formato'})}</span><span class="about-product-spec-value">${L(item.form)}</span></div>`;
      if (item.badge) html += `<div class="about-product-badge">${typeof item.badge === 'object' ? L(item.badge) : item.badge}</div>`;
      html += `</div>`;
      return html;
    }

    function category(title, items) {
      return `<div class="about-product-category about-fade-in">
        <div class="about-product-category-title">${title}</div>
        <div class="about-products-scroll">${items.map(productCard).join('')}</div>
      </div>`;
    }

    el.innerHTML = `
      <div class="about-section-divider"></div>
      <h2 class="about-section-title">${T({en:'Products', ko:'제품', ja:'製品', 'zh-CN':'产品', 'zh-TW':'產品', es:'Productos'})}</h2>
      <p class="about-section-subtitle">${T({en:'Complete lineup from chips to PCIe cards', ko:'칩부터 PCIe 카드까지 완전한 라인업', ja:'チップからPCIeカードまでの完全なラインナップ', 'zh-CN':'从芯片到PCIe卡的完整产品线', 'zh-TW':'從晶片到PCIe卡的完整產品線', es:'Línea completa desde chips hasta tarjetas PCIe'})}</p>
      ${category(T({en:'Chips', ko:'칩', ja:'チップ', 'zh-CN':'芯片', 'zh-TW':'晶片', es:'Chips'}), p.chips)}
      ${category(T({en:'Modules', ko:'모듈', ja:'モジュール', 'zh-CN':'模块', 'zh-TW':'模組', es:'Módulos'}), p.modules)}
      ${category(T({en:'PCIe Cards', ko:'PCIe 카드', ja:'PCIeカード', 'zh-CN':'PCIe 卡', 'zh-TW':'PCIe 卡', es:'Tarjetas PCIe'}), p.cards)}
      ${p.systems && p.systems.length ? category(T({en:'Systems', ko:'시스템', ja:'システム', 'zh-CN':'系统', 'zh-TW':'系統', es:'Sistemas'}), p.systems) : ''}

      ${p.useCases && p.useCases.length ? `
      <h3 class="about-tech-title about-fade-in">${T({en:'Use Cases', ko:'활용 사례', ja:'ユースケース', 'zh-CN':'应用场景', 'zh-TW':'應用場景', es:'Casos de uso'})}</h3>
      <div class="about-solutions-grid">
        ${p.useCases.map(function (uc) {
          return `<div class="about-solution-card about-fade-in">
            <div class="about-solution-icon">${uc.icon}</div>
            <div class="about-solution-title">${L(uc.title)}</div>
            <div class="about-solution-desc">${L(uc.desc)}</div>
          </div>`;
        }).join('')}
      </div>` : ''}
    `;
    container.appendChild(el);
  }

  function renderInvestment(container, data) {
    const inv = data.investment;
    const showRounds = inv.showRounds !== false;
    const el = document.createElement('section');
    el.className = 'about-section';
    el.id = 'aboutInvestment';
    el.innerHTML = `
      <div class="about-section-divider"></div>
      <h2 class="about-section-title">${showRounds
        ? T({en:'Investment & Awards', ko:'투자 & 수상', ja:'投資 & 受賞', 'zh-CN':'投资与奖项', 'zh-TW':'投資與獎項', es:'Inversión y premios'})
        : T({en:'Awards & Recognition', ko:'수상 & 인정', ja:'受賞 & 表彰', 'zh-CN':'奖项与认可', 'zh-TW':'獎項與認可', es:'Premios y reconocimientos'})}</h2>
      <p class="about-section-subtitle">${T({en:'Recognized excellence in AI semiconductor innovation', ko:'AI 반도체 혁신의 인정받은 탁월함', ja:'AI半導体イノベーションにおける卓越性', 'zh-CN':'AI半导体创新的卓越成就', 'zh-TW':'AI半導體創新的卓越成就', es:'Excelencia reconocida en innovación de semiconductores de IA'})}</p>

      ${showRounds ? `
      <div class="about-rounds-row about-fade-in">
        ${inv.rounds.map(r => `
          <div class="about-round-card">
            <div class="about-round-name">${r.name}</div>
            <div class="about-round-status">✓ ${L(r.status)}</div>
            ${r.note ? `<div class="about-round-note">${L(r.note)}</div>` : ''}
          </div>
        `).join('')}
      </div>` : ''}

      <div class="about-awards-grid">
        ${inv.awards.map(a => `
          <div class="about-award-card about-fade-in">
            <div class="about-award-icon">${a.icon}</div>
            <div class="about-award-info">
              <div class="about-award-name">${a.name}</div>
              <div class="about-award-year">${a.year}</div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
    container.appendChild(el);
  }

  function renderPartners(container, data) {
    const pt = data.partners;
    const el = document.createElement('section');
    el.className = 'about-section';
    el.id = 'aboutPartners';
    el.innerHTML = `
      <div class="about-section-divider"></div>
      <h2 class="about-section-title">${T({en:'Solutions & Partners', ko:'솔루션 & 파트너', ja:'ソリューション & パートナー', 'zh-CN':'解决方案与合作伙伴', 'zh-TW':'解決方案與合作夥伴', es:'Soluciones y socios'})}</h2>
      <p class="about-section-subtitle">${T({en:'AI solutions across industries with global partners', ko:'글로벌 파트너와 함께하는 산업별 AI 솔루션', ja:'グローバルパートナーとの産業別AIソリューション', 'zh-CN':'携手全球合作伙伴的跨行业AI解决方案', 'zh-TW':'攜手全球合作夥伴的跨產業AI解決方案', es:'Soluciones de IA para diversas industrias con socios globales'})}</p>

      <div class="about-solutions-grid">
        ${pt.solutions.map(s => `
          <div class="about-solution-card about-fade-in">
            <div class="about-solution-icon">${s.icon}</div>
            <div class="about-solution-title">${L(s.title)}</div>
            <div class="about-solution-desc">${L(s.desc)}</div>
          </div>
        `).join('')}
      </div>

      ${pt.alliance ? `
      <div class="about-alliance-block about-fade-in">
        <h3 class="about-tech-title">${L(pt.alliance.title)}</h3>
        <p class="about-tech-desc">${L(pt.alliance.desc)}</p>
        <div class="about-partners-grid">
          ${pt.alliance.members.map(function (m) { return `<div class="about-partner-chip">${m}</div>`; }).join('')}
        </div>
      </div>` : ''}

      ${pt.distribution && pt.distribution.length ? `
      <div class="about-partners-label about-fade-in">${T({en:'Distribution', ko:'유통', ja:'流通', 'zh-CN':'分销', 'zh-TW':'分銷', es:'Distribución'})}</div>
      <div class="about-distribution-row about-fade-in">
        ${pt.distribution.map(function (d) {
          return `<div class="about-distribution-card about-distribution-card--static">
            <div class="about-distribution-name">${d.name}</div>
            <div class="about-distribution-region">${L(d.role)}</div>
          </div>`;
        }).join('')}
      </div>` : ''}

      ${pt.ecosystem && pt.ecosystem.length ? `
      <div class="about-partners-label about-fade-in">${T({en:'Ecosystem', ko:'생태계', ja:'エコシステム', 'zh-CN':'生态', 'zh-TW':'生態', es:'Ecosistema'})}</div>
      <div class="about-partners-grid about-fade-in">
        ${pt.ecosystem.map(function (name) { return `<div class="about-partner-chip">${name}</div>`; }).join('')}
      </div>` : (pt.logos ? `
      <div class="about-partners-label about-fade-in">${T({en:'Partner Ecosystem', ko:'파트너 생태계', ja:'パートナーエコシステム', 'zh-CN':'合作伙伴生态', 'zh-TW':'合作夥伴生態', es:'Ecosistema de socios'})}</div>
      <div class="about-partners-grid about-fade-in">
        ${pt.logos.map(l => `<div class="about-partner-chip">${l.name}</div>`).join('')}
      </div>` : '')}
    `;
    container.appendChild(el);
  }

  function renderNews(container, data) {
    const n = data.news;
    const upcoming = n.upcoming || [];
    const past = n.past || n.events || [];
    const el = document.createElement('section');
    el.className = 'about-section';
    el.id = 'aboutNews';
    el.innerHTML = `
      <div class="about-section-divider"></div>
      <h2 class="about-section-title">${T({en:'News & Media', ko:'뉴스 & 미디어', ja:'ニュース & メディア', 'zh-CN':'新闻与媒体', 'zh-TW':'新聞與媒體', es:'Noticias y medios'})}</h2>
      <p class="about-section-subtitle">${T({en:'Upcoming events, recent highlights, and media coverage', ko:'예정 이벤트, 최근 소식, 미디어 보도', ja:'今後のイベント、最近のハイライト、メディア報道', 'zh-CN':'即将举行的活动、近期动态与媒体报道', 'zh-TW':'即將舉行的活動、近期動態與媒體報導', es:'Próximos eventos, novedades y cobertura mediática'})}</p>

      ${upcoming.length ? `
      <h3 class="about-tech-title about-fade-in">${T({en:'Upcoming Events', ko:'예정 이벤트', ja:'今後のイベント', 'zh-CN':'即将举行', 'zh-TW':'即將舉行', es:'Próximos eventos'})}</h3>
      <div class="about-news-grid about-news-grid--upcoming">
        ${upcoming.map(function (e) { return renderNewsCard(e, true); }).join('')}
      </div>` : ''}

      ${past.length ? `
      <h3 class="about-tech-title about-fade-in">${T({en:'Recent News & Events', ko:'최근 뉴스 & 이벤트', ja:'最近のニュース & イベント', 'zh-CN':'近期新闻与活动', 'zh-TW':'近期新聞與活動', es:'Noticias y eventos recientes'})}</h3>
      <div class="about-news-grid">
        ${past.map(function (e) { return renderNewsCard(e, false); }).join('')}
      </div>` : ''}

      <h3 class="about-tech-title about-fade-in">${T({en:'Media Coverage', ko:'미디어 보도', ja:'メディア報道', 'zh-CN':'媒体报道', 'zh-TW':'媒體報導', es:'Cobertura mediática'})}</h3>
      <div class="about-news-grid">
        ${(n.media || []).map(m => `
          <div class="about-news-card about-fade-in${m.url ? ' about-news-card--linked' : ''}">
            <div class="about-news-type">${m.source}</div>
            <div class="about-news-title">${m.url ? `<a class="about-news-link" href="${m.url}" target="_blank" rel="noopener noreferrer">${L(m.title)} ↗</a>` : L(m.title)}</div>
            <div class="about-news-meta">${m.date || ''}</div>
          </div>
        `).join('')}
      </div>
    `;
    container.appendChild(el);

    const meta = data.meta || {};
    const verified = meta.lastVerified ? T({en:'Data as of', ko:'기준일', ja:'基準日', 'zh-CN':'数据截至', 'zh-TW':'資料截至', es:'Datos a'}) + ' ' + meta.lastVerified : '';
    const nextUpdate = meta.lastVerified ? T({en:'refreshed with each release', ko:'다음 릴리즈에서 업데이트됩니다', ja:'次のリリースで更新されます', 'zh-CN':'将在下个版本更新', 'zh-TW':'將在下個版本更新', es:'se actualiza con cada versión'}) : '';
    const footer = document.createElement('div');
    footer.className = 'about-footer about-fade-in';
    footer.innerHTML = `
      <div>© 2026 DEEPX Co., Ltd. All Rights Reserved.</div>
      ${verified ? `<div class="about-footer-meta">${verified}${nextUpdate ? ' · ' + nextUpdate : ''}${meta.sources ? ' · ' + meta.sources.map(stripUrlHost).join(', ') : ''}</div>` : ''}
    `;
    container.appendChild(footer);
  }

  function setupScrollSpy(scrollEl) {
    const nav = document.getElementById('aboutNav');
    if (!nav) return;
    const tabs = nav.querySelectorAll('.about-nav-tab');
    const sections = Array.from(tabs).map(t =>
      document.getElementById(t.dataset.section)
    ).filter(Boolean);

    _scrollSpyObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          tabs.forEach(t => t.classList.remove('active'));
          const tab = nav.querySelector(`[data-section="${entry.target.id}"]`);
          if (tab) tab.classList.add('active');
        }
      });
    }, { root: scrollEl, rootMargin: '-20% 0px -60% 0px', threshold: 0 });

    sections.forEach(s => _scrollSpyObserver.observe(s));

    tabs.forEach(tab => {
      if (!tab.dataset.clickBound) {
        tab.addEventListener('click', () => {
          const target = document.getElementById(tab.dataset.section);
          if (target) target.scrollIntoView({ behavior: 'smooth' });
        });
        tab.dataset.clickBound = '1';
      }
      if (!tab.dataset.keyboardBound) {
        tab.addEventListener('keydown', function(e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            tab.click();
          }
        });
        tab.dataset.keyboardBound = '1';
      }
    });
  }

  function setupFadeIn(scrollEl) {
    const items = scrollEl.querySelectorAll('.about-fade-in');
    if (!items.length) return;

    function reveal(el) {
      el.classList.add('visible');
    }

    if (typeof IntersectionObserver === 'undefined') {
      items.forEach(reveal);
      return;
    }

    _fadeObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          reveal(entry.target);
          _fadeObserver.unobserve(entry.target);
        }
      });
    }, { root: scrollEl, rootMargin: '0px 0px -5% 0px', threshold: 0.05 });

    items.forEach(function (item) {
      _fadeObserver.observe(item);
      // Hero and first viewport items may not fire IO until scroll — reveal if already visible.
      try {
        var rect = item.getBoundingClientRect();
        var rootRect = scrollEl.getBoundingClientRect();
        if (rect.top < rootRect.bottom && rect.bottom > rootRect.top) {
          reveal(item);
          _fadeObserver.unobserve(item);
        }
      } catch (e) { /* ignore */ }
    });
  }

  function renderAboutNavLabels() {
    var nav = document.getElementById('aboutNav');
    if (!nav) return;
    var tabs = nav.querySelectorAll('.about-nav-tab');
    var lang = currentLang();
    tabs.forEach(function(tab) {
      var section = tab.dataset.section;
      var labels = ABOUT_NAV_LABELS[section];
      if (labels) tab.textContent = labels[lang] || labels.en || tab.textContent;
    });
  }

  function renderAboutLoading() {
    var scrollEl = document.getElementById('aboutScroll');
    if (!scrollEl) return;
    scrollEl.innerHTML = '<div class="about-loading" role="status" aria-live="polite">' +
      '<div class="about-loading-spinner" aria-hidden="true"></div>' +
      '<span>' + T({en:'Loading About DEEPX…', ko:'DEEPX 소개 불러오는 중…', ja:'DEEPXについてを読み込み中…', 'zh-CN':'正在加载关于 DEEPX…', 'zh-TW':'正在載入關於 DEEPX…', es:'Cargando Acerca de DEEPX…'}) + '</span>' +
      '</div>';
  }
  function renderAboutError(error) {
    var scrollEl = document.getElementById('aboutScroll');
    if (!scrollEl) return;
    scrollEl.innerHTML = '<div class="about-error" style="text-align:center;padding:4rem 1rem;">' +
      '<p style="font-size:1.2rem;color:var(--text-muted,#888);">' +
      T({en:'Failed to load About data.', ko:'데이터 로드에 실패했습니다.', ja:'データの読み込みに失敗しました。', 'zh-CN':'数据加载失败。', 'zh-TW':'資料載入失敗。', es:'No se pudieron cargar los datos de About.'}) +
      '</p>' +
      '<p style="color:var(--text-muted,#666);font-size:0.9rem;">' + (error || '') + '</p>' +
      '<button class="about-retry-btn" style="margin-top:1rem;padding:0.5rem 1.5rem;cursor:pointer;">' +
      T({en:'Retry', ko:'재시도', ja:'再試行', 'zh-CN':'重试', 'zh-TW':'重試', es:'Reintentar'}) +
      '</button></div>';
    var btn = scrollEl.querySelector('.about-retry-btn');
    if (btn) btn.addEventListener('click', function() {
      _aboutInitialized = false;
      _aboutData = null;
      initAboutView();
    });
  }

  function revealAboutFadeIns() {
    var scrollEl = document.getElementById('aboutScroll');
    if (!scrollEl) return;
    scrollEl.querySelectorAll('.about-fade-in').forEach(function(el) {
      el.classList.add('visible');
    });
  }

  function refreshAboutFadeInObserver() {
    var scrollEl = document.getElementById('aboutScroll');
    var aboutView = document.getElementById('about-view');
    if (!scrollEl || !aboutView || !aboutView.classList.contains('visible')) return;
    if (!scrollEl.querySelector('.about-fade-in')) return;
    setupFadeIn(scrollEl);
  }

  function onAboutViewShown() {
    var scrollEl = document.getElementById('aboutScroll');
    if (_aboutInitialized && scrollEl && scrollEl.querySelector('.about-hero')) {
      requestAnimationFrame(function() {
        revealAboutFadeIns();
        refreshAboutFadeInObserver();
      });
      return;
    }
    initAboutView();
  }

  function renderAboutView(options) {
    options = options || {};
    var scrollEl = document.getElementById('aboutScroll');
    if (!scrollEl || !_aboutData) return;

    if (_scrollSpyObserver) _scrollSpyObserver.disconnect();
    if (_fadeObserver) _fadeObserver.disconnect();

    var scrollPos = options.preserveScroll ? scrollEl.scrollTop : 0;
    scrollEl.innerHTML = '';

    renderHero(scrollEl, _aboutData);
    renderDeveloperHub(scrollEl, _aboutData);
    renderCompany(scrollEl, _aboutData);
    renderTechnology(scrollEl, _aboutData);
    renderProducts(scrollEl, _aboutData);
    renderInvestment(scrollEl, _aboutData);
    renderPartners(scrollEl, _aboutData);
    renderNews(scrollEl, _aboutData);

    setupScrollSpy(scrollEl);
    setupFadeIn(scrollEl);
    renderAboutNavLabels();

    if (options.preserveScroll) scrollEl.scrollTop = scrollPos;
  }

  function registerLanguageHooks() {
    if (_languageHookRegistered) return;
    if (typeof DXI18n !== 'undefined' && typeof DXI18n.onLangChange === 'function') {
      DXI18n.onLangChange(function() {
        if (_aboutData) renderAboutView({ preserveScroll: true });
      });
      _languageHookRegistered = true;
    }
  }

  async function initAboutView() {
    var scrollEl = document.getElementById('aboutScroll');
    if (_aboutInitialized && scrollEl && scrollEl.querySelector('.about-hero')) {
      revealAboutFadeIns();
      return;
    }

    renderAboutLoading();

    try {
      var data = await loadData();
      if (!data) throw new Error('No data returned');
      renderAboutView();
      _aboutInitialized = true;
      registerLanguageHooks();
      revealAboutFadeIns();
    } catch (e) {
      _aboutInitialized = false;
      renderAboutError(e.message || String(e));
    }
  }

  function closeAboutPanel() {
    // In-view reset only (Escape scroll-to-top). Navigation away keeps scroll via setVisibleView.
    const scrollEl = document.getElementById('aboutScroll');
    if (scrollEl) scrollEl.scrollTop = 0;
    const nav = document.getElementById('aboutNav');
    if (nav) nav.querySelectorAll('.about-nav-tab').forEach(t => t.classList.remove('active'));
  }

  // Cross-tab language change fallback
  window.addEventListener('storage', function(e) {
    if (e.key === 'dx-lang' && _aboutData) {
      renderAboutView({ preserveScroll: true });
    }
  });

  window.AboutDeepX = {
    init: initAboutView,
    onShown: onAboutViewShown,
    refresh: function () { if (_aboutData) renderAboutView({ preserveScroll: true }); },
    reset: function () { _aboutInitialized = false; _aboutData = null; }
  };
  window.initAboutView = initAboutView;
  window.closeAboutPanel = closeAboutPanel;
  Object.defineProperty(window, '_aboutHasActivePanel', {
    get: function() {
      var aboutView = document.getElementById('about-view');
      if (!aboutView || !aboutView.classList.contains('visible')) return false;
      var scrollEl = document.getElementById('aboutScroll');
      // scrollTop > 0 means user has scrolled into a panel section;
      // Escape should reset to top rather than leaving About entirely.
      return !!(scrollEl && scrollEl.scrollTop > 0);
    }
  });
})();
