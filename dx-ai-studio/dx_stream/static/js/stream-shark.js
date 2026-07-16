(function() {
    'use strict';
    DXStream.shark = {};
    DXStream.shark._installCompleted = false;

    DXStream.shark.markInstalled = function() {
        DXStream.shark._installCompleted = true;
        var badge = DXStream.$('setup-badge-gstshark');
        if (badge) {
            badge.textContent = '✅ ' + T('Done');
            badge.className = 'comp-status-badge cs-ok';
        }
        var btn = DXStream.$('shark-install-btn');
        if (btn) btn.style.display = 'none';
        var panel = DXStream.$('shark-panel');
        if (panel) panel.style.display = '';
    };

    DXStream.shark.checkStatus = function() {
        DXStream.api('/api/gstshark/status').then(function(data) {
            var badge = DXStream.$('setup-badge-gstshark');
            var btn = DXStream.$('shark-install-btn');
            if (data.installed || DXStream.shark._installCompleted) {
                DXStream.shark.markInstalled();
            } else {
                if (badge) {
                    badge.textContent = '⚠️ ' + T('Not installed');
                    badge.className = 'comp-status-badge cs-warn';
                }
            }
        });
    };

    DXStream.shark.install = async function() {
        var pw = await DXStream.inputModal(
            DXStream._L('🔒 sudo 인증','🔒 sudo Authentication','🔒 sudo認証','🔒 sudo认证','🔒 sudo認證'),
            { description: DXStream._L('GstShark 설치에 관리자 권한이 필요합니다.','GstShark installation requires administrator privileges.','GstSharkのインストールには管理者権限が必要です。','GstShark安装需要管理员权限。','GstShark安裝需要管理員權限。'),
              type: 'password',
              placeholder: DXStream._L('비밀번호 입력','Enter password','パスワード入力','输入密码','輸入密碼') }
        );
        if (!pw) {
            DXStream.toast(T('Cancelled'), 'info');
            return;
        }
        var btn = DXStream.$('shark-install-btn');
        if (btn) { btn.disabled = true; btn.textContent = '⏳ ' + T('Installing...'); }
        var badge = DXStream.$('setup-badge-gstshark');
        if (badge) { badge.textContent = '⏳'; badge.className = 'comp-status-badge cs-warn'; }
        var logEl = DXStream.$('setup-log-gstshark');
        if (logEl) { logEl.style.display = ''; logEl.textContent = T('Preparing…') + '\n'; }
        DXStream.postJ('/api/gstshark/install', { password: pw })
        .then(function() {
            DXStream.shark.pollInstall();
        });
    };

    DXStream.shark.pollInstall = function() {
        var logEl = DXStream.$('setup-log-gstshark');
        DXStream.api('/api/gstshark/status').then(function(data) {
            if (data.install_log) {
                if (logEl && data.install_log.log) {
                    logEl.style.display = '';
                    logEl.textContent = data.install_log.log;
                    logEl.scrollTop = logEl.scrollHeight;
                }
                if (!data.install_log.done) {
                    setTimeout(DXStream.shark.pollInstall, 2000);
                } else {
                    var btn = DXStream.$('shark-install-btn');
                    if (btn) {
                        btn.disabled = false;
                        btn.innerHTML = '<span class="ko">📊 설치</span><span class="en">📊 Install</span><span class="es">📊 Instalar</span><span class="ja">📊 インストール</span><span class="zh-CN">📊 安装</span><span class="zh-TW">📊 安裝</span>';
                    }
                    if (data.install_log.done && data.install_log.ok) {
                        DXStream.shark.markInstalled();
                    }
                    DXStream.shark.checkStatus();
                }
            } else {
                DXStream.shark.checkStatus();
            }
        });
    };

    DXStream.shark.loadTrace = function() {
        DXStream.api('/api/gstshark/trace').then(function(data) {
            if (data.error || Object.keys(data).length === 0) {
                DXStream.$('shark-no-data').style.display = '';
                return;
            }
            DXStream.$('shark-no-data').style.display = 'none';
            DXStream.shark.renderCharts(data);
        });
    };

    DXStream.shark.renderCharts = function(data) {
        var labels = Object.keys(data);
        var cpuData = labels.map(function(e) { return (data[e].cpuusage || 0); });
        var fpsData = labels.map(function(e) { return (data[e].framerate || 0); });

        var cpuCtx = DXStream.$('shark-cpu-chart');
        if (cpuCtx && window.Chart) {
            if (DXStream.shark._cpuChart) DXStream.shark._cpuChart.destroy();
            DXStream.shark._cpuChart = new Chart(cpuCtx, {
                type: 'bar',
                data: { labels: labels, datasets: [{ label: 'CPU %', data: cpuData, backgroundColor: 'rgba(99,140,255,0.6)' }] },
                options: { responsive: true, scales: { y: { beginAtZero: true } } }
            });
        }

        var fpsCtx = DXStream.$('shark-fps-chart');
        if (fpsCtx && window.Chart) {
            if (DXStream.shark._fpsChart) DXStream.shark._fpsChart.destroy();
            DXStream.shark._fpsChart = new Chart(fpsCtx, {
                type: 'bar',
                data: { labels: labels, datasets: [{ label: 'FPS', data: fpsData, backgroundColor: 'rgba(76,175,80,0.6)' }] },
                options: { responsive: true, scales: { y: { beginAtZero: true } } }
            });
        }
    };

    document.addEventListener('click', function(e) {
        if (e.target.closest('#shark-toggle')) {
            var body = DXStream.$('shark-body');
            body.style.display = body.style.display === 'none' ? '' : 'none';
            if (body.style.display !== 'none') DXStream.shark.loadTrace();
        }
    });

    DXStream.shark.checkStatus();
})();
if (typeof registerStreamLangRefresher === 'function') {
  registerStreamLangRefresher(function() {
    if (typeof DXI18n !== 'undefined' && DXI18n.applyLang) DXI18n.applyLang(document);
    if (typeof DXStream !== 'undefined' && DXStream.S && DXStream.S.currentPage && typeof DXStream.nav === 'function') {
      DXStream.nav(DXStream.S.currentPage);
    }
  });
}
