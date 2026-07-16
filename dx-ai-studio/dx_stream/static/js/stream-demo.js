/**
 * DX Stream — 데모 런처
 * 데모 카드 렌더링, 시작/중지, WebRTC 연결
 */
DXStream._runningDemoId = null;
DXStream._startingDemo = false;

/* ── XSS 방지: HTML 특수문자 이스케이프 ── */
function _escHtml(s) {
    if (s == null) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

var _demoCatI18n = {
    object_detection: { en: 'Object Detection', ko: '객체 감지', es: 'Detección', ja: '物体検出', 'zh-CN': '目标检测', 'zh-TW': '物件偵測' },
    face_detection:   { en: 'Face Detection',   ko: '얼굴 감지', es: 'Rostro',    ja: '顔検出',   'zh-CN': '人脸检测', 'zh-TW': '人臉偵測' },
    pose_estimation:  { en: 'Pose Estimation',  ko: '자세 추정', es: 'Pose',      ja: '姿勢推定', 'zh-CN': '姿态估计', 'zh-TW': '姿勢估計' },
    segmentation:     { en: 'Segmentation',     ko: '분할',      es: 'Segmentación', ja: 'セグメンテーション', 'zh-CN': '分割', 'zh-TW': '分割' },
    tracking:         { en: 'Tracking',         ko: '추적',      es: 'Seguimiento', ja: '追跡', 'zh-CN': '追踪', 'zh-TW': '追蹤' },
    multi_stream:     { en: 'Multi-Stream',     ko: '멀티 스트림', es: 'Multi',    ja: 'マルチストリーム', 'zh-CN': '多路流', 'zh-TW': '多路串流' },
    secondary:        { en: 'Secondary',        ko: '2차 추론',  es: 'Secundario', ja: '二次推論', 'zh-CN': '二次推理', 'zh-TW': '二次推論' }
};
function _demoCatLabel(cat) {
    var t = _demoCatI18n[cat];
    if (!t) return cat || '';
    return t[DXStream.S.lang] || t.en || cat || '';
}

function _demoText(d, field) {
    var lang = DXStream.S.lang || 'en';
    return d[field + '_' + lang] || d[field + '_en'] || '';
}

var _demoReasonI18n = {
    missing_model: {
        en: 'Model not installed: ', ko: '모델 미설치: ', es: 'Modelo no instalado: ',
        ja: 'モデル未インストール: ', 'zh-CN': '模型未安装: ', 'zh-TW': '模型未安裝: '
    },
    missing_config_file: {
        en: 'Missing config file: ', ko: '설정 파일 없음: ', es: 'Falta el archivo de configuración: ',
        ja: '設定ファイルなし: ', 'zh-CN': '缺少配置文件: ', 'zh-TW': '缺少設定檔: '
    },
    missing_runtime_script: {
        en: 'Missing runtime script: ', ko: '런타임 스크립트 없음: ', es: 'Falta el script de runtime: ',
        ja: 'ランタイムスクリプトなし: ', 'zh-CN': '缺少运行时脚本: ', 'zh-TW': '缺少執行階段腳本: '
    },
    missing_sample_video: {
        en: 'Missing sample video: ', ko: '샘플 비디오 없음: ', es: 'Falta el video de muestra: ',
        ja: 'サンプル動画なし: ', 'zh-CN': '缺少示例视频: ', 'zh-TW': '缺少範例影片: '
    },
    missing_npu_device: {
        en: 'NPU device not found', ko: 'NPU 장치 없음', es: 'Dispositivo NPU no encontrado',
        ja: 'NPUデバイスなし', 'zh-CN': '未找到 NPU 设备', 'zh-TW': '找不到 NPU 裝置'
    },
    missing_dxstream_plugin: {
        en: 'DxStream GStreamer plugin not installed (run build.sh)',
        ko: 'DxStream GStreamer 플러그인 미설치 (build.sh 실행 필요)',
        es: 'Plugin GStreamer de DxStream no instalado (ejecute build.sh)',
        ja: 'DxStream GStreamerプラグイン未インストール（build.shを実行）',
        'zh-CN': '未安装 DxStream GStreamer 插件（运行 build.sh）',
        'zh-TW': '未安裝 DxStream GStreamer 外掛程式（執行 build.sh）'
    }
};

function _demoReasonItemText(item) {
    if (!item || !item.code) return '';
    var labels = _demoReasonI18n[item.code];
    if (!labels) return item.path ? (item.code + ': ' + item.path) : item.code;
    var label = labels[DXStream.S.lang] || labels.en || item.code;
    return item.path ? label + item.path : label;
}

function _demoUnavailableReason(availability) {
    var items = availability.reason_items || [];
    if (Array.isArray(items) && items.length > 0) {
        return items.map(_demoReasonItemText).filter(Boolean).join('; ');
    }
    return availability.reason || '';
}

DXStream.demoInit = async function () {
    var grid = DXStream.$('demo-grid');
    if (grid) grid.innerHTML = '<div class="loading-placeholder"><span class="spin"></span>' +
        '<span class="ko">데모 로드 중…</span><span class="en">Loading demos…</span></div>';
    var demos = await DXStream.api('/api/demos');
    if (demos.error) {
        if (grid) grid.innerHTML = '<div class="empty-state"><span class="txt-dim">' +
            T('Failed to load demos') + '</span></div>';
        return;
    }
    DXStream._allDemos = demos;
    _renderDemoCards(demos);
};

function _renderDemoCards(demos) {
    var grid = DXStream.$('demo-grid');
    if (!grid) return;
    if (!demos || demos.length === 0) {
        grid.innerHTML = '<div class="empty-state"><span class="txt-dim">' +
            '<span class="ko">해당하는 데모가 없습니다</span>' +
            '<span class="en">No demos found</span></span></div>';
        return;
    }
    var runId = DXStream._runningDemoId;
    grid.innerHTML = demos.map(function (d) {
        var availability = d.availability || {};
        var reason = _demoUnavailableReason(availability) || d.reason || '';
        return `
        <div class="demo-card${d.id === runId ? ' demo-running' : ''}" data-id="${d.id}" data-category="${_escHtml(d.category)}">
            <div class="demo-card-header">
                <span class="demo-card-num">#${d.id}</span>
                ${d.id === runId ? '<span class="status-pill pill-running">▶</span>' : ''}
                <span class="status-pill ${d.available ? 'pill-ok' : 'pill-warn'}">${d.available ? '✓' : '⚠'}</span>
            </div>
            <h3 class="demo-card-title">
                ${_escHtml(_demoText(d, 'name'))}
            </h3>
            <p class="txt-dim txt-sm">
                ${_escHtml(_demoText(d, 'description'))}
            </p>
            <div class="demo-card-meta">
                <span class="demo-card-model">📦 ${_escHtml(d.model)}</span>
                <span class="demo-card-cat">${_escHtml(_demoCatLabel(d.category))}</span>
            </div>
            ${!d.available && reason ? '<p class="txt-xs txt-warn demo-unavailable-reason">' + _escHtml(reason) + '</p>' : ''}
            <div class="demo-card-actions">
                <button class="btn btn-primary btn-sm" onclick="DXStream._startDemo(${d.id})"
                    ${!d.available || d.id === runId ? 'disabled' : ''} id="start-demo-${d.id}"
                    ${d.id === runId ? 'style="display:none"' : ''}>
                    <span class="ko">실행</span><span class="en">Start</span>
                </button>
                <button class="btn btn-ghost btn-sm" onclick="DXStream._stopDemo(${d.id})"
                    ${d.id !== runId ? 'style="display:none"' : ''} id="stop-demo-${d.id}">
                    <span class="ko">중지</span><span class="en">Stop</span>
                </button>
            </div>
        </div>
    `;
    }).join('');
}

DXStream._startDemo = async function (id) {
    if (DXStream._startingDemo) {
        DXStream.toast(T('Demo start already in progress'), 'warn');
        return;
    }
    DXStream._startingDemo = true;
    var startBtn = DXStream.$('start-demo-' + id);
    if (startBtn) startBtn.disabled = true;

    try {
        DXStream.toast(T('Starting demo…'), 'info');
        var webrtcPayloadTypes = await DXStream.webrtc.preferredPayloadTypes();
        var resp = await DXStream.postJ('/api/demos/' + id + '/start', {
            webrtcPayloadTypes: webrtcPayloadTypes
        });
        if (resp.error) {
            DXStream.toast(resp.error, 'error');
            return;
        }
        if (resp.output_mode === 'webrtc') {
            var status = await _waitDemoStarted(id, resp.pipeline_id);
            if (status && status.error) {
                DXStream.toast(status.error, 'error');
                return;
            }
        }
        DXStream._runningDemoId = id;
        DXStream.toast(T('Demo started'), 'success');

        // UI 토글: 실행 → 중지 버튼
        if (startBtn) startBtn.style.display = 'none';
        var stopBtn = DXStream.$('stop-demo-' + id);
        if (stopBtn) stopBtn.style.display = '';

        // 실행 중 카드 하이라이트
        var card = startBtn ? startBtn.closest('.demo-card') : null;
        if (card) card.classList.add('demo-running');

        // 비디오 연결
        if (resp.output_mode === 'mjpeg' || resp.output_mode === 'webrtc') {
            var videoSection = DXStream.$('demo-video-section');
            if (videoSection) {
                videoSection.style.display = '';
            }
            var demo = DXStream._allDemos ? DXStream._allDemos.find(function (d) { return d.id === id; }) : null;
            if (demo) {
                var titleEl = DXStream.$('demo-video-title');
                if (titleEl) titleEl.textContent = '#' + id + ' ' + _demoText(demo, 'name');
                var modelEl = DXStream.$('demo-model-info');
                if (modelEl) modelEl.textContent = '📦 ' + (demo.model || '--');
                var pipeEl = DXStream.$('demo-pipeline-info');
                if (pipeEl) pipeEl.textContent = demo.category || '';
            }

            if (resp.output_mode === 'mjpeg') {
                // MJPEG 모드: <img> 태그로 스트리밍
                var video = DXStream.$('webrtc-video');
                if (video) video.style.display = 'none';
                var mjpegImg = DXStream.$('mjpeg-stream');
                if (!mjpegImg) {
                    mjpegImg = document.createElement('img');
                    mjpegImg.id = 'mjpeg-stream';
                    mjpegImg.style.cssText = 'width:100%;height:auto;border-radius:8px;background:#000;';
                    var container = video ? video.parentNode : videoSection;
                    if (container) container.appendChild(mjpegImg);
                }
                mjpegImg.style.display = '';
                mjpegImg.src = '/api/stream/mjpeg?' + Date.now();
                // 영상 영역으로 자동 스크롤
                videoSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } else {
                var video = DXStream.$('webrtc-video');
                if (video) DXStream.webrtc.connect(video);
            }
        } else {
            DXStream.toast(T('Native display mode (fpsdisplaysink)'), 'info');
        }
    } finally {
        DXStream._startingDemo = false;
        if (startBtn && DXStream._runningDemoId == null) startBtn.disabled = false;
    }
};

function _demoStatusDelay(attempt) {
    return Math.min(250 * Math.pow(1.5, attempt), 2000);
}

async function _waitDemoStarted(id, pipelineId) {
    var deadline = Date.now() + 12000;
    var attempt = 0;
    while (Date.now() < deadline) {
        var status = await DXStream.api('/api/pipeline/status');
        if (status.error) return status;
        var pipelineMatch = !pipelineId || status.pipeline_id === pipelineId;
        if (status.running && pipelineMatch) return status;
        await new Promise(function (resolve) {
            setTimeout(resolve, _demoStatusDelay(attempt++));
        });
    }
    return { error: T('Demo start timed out. Retry or check the runtime.') };
}

DXStream._stopDemo = async function (id) {
    DXStream.webrtc.disconnect();
    var demoId = (id != null) ? id : DXStream._runningDemoId;
    if (demoId != null) {
        await DXStream.postJ('/api/demos/' + demoId + '/stop', {});
        // UI 토글: 중지 → 실행 버튼
        var startBtn = DXStream.$('start-demo-' + demoId);
        var stopBtn = DXStream.$('stop-demo-' + demoId);
        if (startBtn) { startBtn.style.display = ''; startBtn.disabled = false; }
        if (stopBtn) stopBtn.style.display = 'none';
        // 실행 중 카드 하이라이트 해제
        var card = startBtn ? startBtn.closest('.demo-card') : null;
        if (card) card.classList.remove('demo-running');
    } else {
        await DXStream.postJ('/api/pipeline/stop', {});
    }

    // 비디오 섹션 숨김 및 정리
    var videoSection = DXStream.$('demo-video-section');
    if (document.fullscreenElement === videoSection && document.exitFullscreen) {
        try { await document.exitFullscreen(); } catch (e) {}
    }
    if (videoSection) videoSection.style.display = 'none';
    var video = DXStream.$('webrtc-video');
    if (video) { video.srcObject = null; video.style.display = ''; }
    var mjpegImg = DXStream.$('mjpeg-stream');
    if (mjpegImg) { mjpegImg.src = ''; mjpegImg.style.display = 'none'; }
    var titleEl = DXStream.$('demo-video-title');
    if (titleEl) titleEl.textContent = '--';
    var statsOverlay = DXStream.$('webrtc-stats-overlay');
    if (statsOverlay) statsOverlay.textContent = '';

    DXStream._runningDemoId = null;
    DXStream.toast(T('Demo stopped'), 'info');
};

DXStream.filterDemos = function (cat, btn) {
    var bar = DXStream.$('demo-filter-bar');
    if (bar) {
        bar.querySelectorAll('.btn').forEach(function (b) { b.classList.remove('active'); });
        // btn 이 없으면 data-cat으로 찾기
        if (btn) {
            btn.classList.add('active');
        } else if (bar) {
            var match = bar.querySelector('[data-cat="' + cat + '"]');
            if (match) match.classList.add('active');
        }
    }
    if (!DXStream._allDemos) return;
    if (cat === 'all') {
        _renderDemoCards(DXStream._allDemos);
    } else {
        _renderDemoCards(DXStream._allDemos.filter(function (d) {
            return d.category === cat;
        }));
    }
};

DXStream.stopDemo = function () {
    DXStream._stopDemo(DXStream._runningDemoId);
};

DXStream.toggleFullscreen = function () {
    var target = DXStream.$('demo-video-section') || DXStream.$('demo-video') || DXStream.$('webrtc-video');
    if (!target) return;
    if (document.fullscreenElement) {
        document.exitFullscreen();
    } else {
        target.requestFullscreen().catch(function () {});
    }
};
if (typeof registerStreamLangRefresher === 'function') {
  registerStreamLangRefresher(function() {
    if (typeof DXI18n !== 'undefined' && DXI18n.applyLang) DXI18n.applyLang(document);
    if (typeof DXStream !== 'undefined' && DXStream.S && DXStream.S.currentPage && typeof DXStream.nav === 'function') {
      DXStream.nav(DXStream.S.currentPage);
    }
  });
}
