# 용어 결정 대기 — 2:1 다수결 (적용하지 않음)

2026-09-21 실측 37건. **기계가 정하지 않는다** — 2:1 은 근거가 약하고,
`Accuracy`[zh-CN] 의 `精度`(정밀도)와 `准确率`(정확률)처럼 **뜻이 다른** 말이
섞여 있다. 잘못 고르면 틀린 뜻이 저장소 전체로 퍼진다.

어느 쪽이 맞는지는 **그 화면이 무엇을 재는지** 에 달렸다. 표의 `쓰인 곳` 을
열어 보고 정해 주면 적용하겠다.

| 영어 | 언어 | 후보 (횟수) | 쓰인 곳 |
|---|---|---|---|
| Accuracy | zh-CN | `精度`(2) / `准确率`(1) | dx_app/static/js/i18n.js, dx_modelzoo/static/js/i18n-dict-catalog.js |
| Available | ja | `利用可能`(2) / `使用可能`(1) | dx_app/static/js/i18n.js, dx_monitor/static/js/i18n.js |
| Device ID | ko | `장치 ID`(2) / `디바이스 ID`(1) | dx_app/static/js/i18n.js, dx_app/static/js/tutorial.js |
| Error: | es | `Error:`(2) / `Error de compilación:`(1) | dx_app/static/js/i18n.js, dx_compiler/static/js/compiler-i18n.js |
| Explorer | ja | `エクスプローラー`(2) / `詳細エクスプローラー`(1) | dx_compiler/static/js/tutorial.js, dx_planner/static/js/i18n.js |
| Frames | es | `Cuadros`(2) / `Fotogramas`(1) | dx_app/static/js/i18n.js, dx_modelzoo/static/js/i18n-dict-inference.js |
| Frames | zh-CN | `帧数`(2) / `帧`(1) | dx_app/static/js/i18n.js |
| Frames | zh-TW | `影格`(2) / `幀數`(1) | dx_app/static/js/i18n.js |
| Input Type | ko | `입력 타입 선택`(2) / `입력 유형`(1) | dx_app/static/js/i18n.js, dx_app/static/js/tutorial.js |
| Metric | ja | `指標`(2) / `メトリクス`(1) / `メトリック`(1) | dx_app/static/js/i18n.js, dx_benchmark/static/js/i18n.js |
| Metric | ko | `메트릭`(2) / `항목`(1) / `지표`(1) | dx_benchmark/static/js/i18n.js, dx_modelzoo/static/js/i18n-dict-shared.js |
| Mock Data | ko | `모의 데이터`(2) / `Mock 데이터`(1) | dx_app/static/js/i18n.js, dx_monitor/static/js/tutorial.js |
| NPU Linux Driver | es | `Controlador Linux NPU`(2) / `Controlador NPU Linux`(1) | dx_app/static/js/i18n.js, launcher/static/sdk-library-data.json |
| NPU Linux Driver | ja | `NPU Linux ドライバー`(2) / `NPU Linuxドライバー`(1) | dx_app/static/js/i18n.js, launcher/static/sdk-library-data.json |
| NPU Linux Driver | ko | `NPU 리눅스 드라이버`(2) / `NPU Linux 드라이버`(1) | dx_app/static/js/i18n.js, launcher/static/sdk-library-data.json |
| NPU Linux Driver | zh-CN | `NPU Linux驱动`(2) / `NPU Linux 驱动程序`(1) | dx_app/static/js/i18n.js, dx_stream/static/js/stream-i18n.js |
| NPU Linux Driver | zh-TW | `NPU Linux 驅動程式`(2) / `NPU Linux驅動程式`(1) | dx_app/static/js/i18n.js, launcher/static/sdk-library-data.json |
| NPU Topology | es | `Topología NPU`(2) / `Topología del NPU`(1) | dx_app/static/js/i18n.js, dx_monitor/static/js/tutorial.js |
| NPU Topology | zh-TW | `NPU拓撲`(2) / `NPU 拓樸`(1) | dx_app/static/js/i18n.js, dx_monitor/static/js/tutorial.js |
| No models found | ko | `모델을 찾을 수 없습니다`(2) / `모델이 없습니다`(1) | dx_app/static/js/i18n.js, dx_stream/static/js/stream-i18n.js |
| Segmentation | ko | `분할`(2) / `의미론적 분할`(1) | dx_benchmark/static/js/i18n.js, dx_stream/static/js/stream-i18n.js |
| Settings | es | `Configuración`(2) / `Ajustes`(1) | dx_benchmark/static/js/i18n.js, dx_benchmark/static/js/tutorial.js |
| Setup & Install | ja | `セットアップ & インストール`(2) / `セットアップ＆インストール`(1) | dx_app/static/js/i18n.js, dx_stream/static/js/stream-i18n.js |
| Setup & Install | ko | `설정 & 설치`(2) / `환경 설정 & 설치`(1) | dx_app/static/js/i18n.js, dx_app/static/js/tutorial.js |
| Setup & Install | zh-CN | `设置和安装`(2) / `设置与安装`(1) | dx_app/static/js/i18n.js, dx_app/static/js/tutorial.js |
| Source | zh-CN | `来源`(2) / `源`(1) | dx_app/static/js/i18n.js, dx_stream/static/js/stream-i18n.js |
| Task | ko | `작업`(2) / `태스크`(1) | dx_benchmark/static/js/i18n.js, dx_modelzoo/static/js/i18n-dict-detail.js |
| Task Filter | es | `Filtro de Task`(5) / `Filtro de tarea`(2) | dx_app/static/js/i18n.js, dx_benchmark/static/js/tutorial.js |
| Task Filter | ko | `Task 필터`(5) / `태스크 필터`(2) | dx_app/static/js/i18n.js, dx_benchmark/static/js/tutorial.js |
| Task Filter | zh-CN | `Task筛选`(5) / `任务筛选`(2) | dx_app/static/js/i18n.js, dx_benchmark/static/js/tutorial.js |
| Task Filter | zh-TW | `Task篩選`(5) / `任務篩選`(2) | dx_app/static/js/i18n.js, dx_benchmark/static/js/tutorial.js |
| Top Bar | zh-TW | `頂部列`(2) / `頂部欄`(1) | dx_app/static/js/tutorial.js, dx_stream/static/js/tutorial.js |
| View All | ja | `全体表示`(2) / `すべて表示`(1) | dx_app/static/js/i18n.js, dx_monitor/static/js/tutorial.js |
| ⚙️ Setup & Install | ja | `⚙️ セットアップ & インストール`(2) / `⚙️ 設定 & インストール`(1) | dx_app/static/js/i18n.js, dx_stream/static/js/tutorial.js |
| ⚙️ Setup & Install | ko | `⚙️ 설정 & 설치`(2) / `⚙️ 환경 설정 & 설치`(1) | dx_app/static/js/i18n.js, dx_app/static/js/tutorial.js |
| ⚙️ Setup & Install | zh-CN | `⚙️ 设置 & 安装`(2) / `⚙️ 设置与安装`(1) | dx_app/static/js/i18n.js, dx_app/static/js/tutorial.js |
| ⚙️ Setup & Install | zh-TW | `⚙️ 設定 & 安裝`(2) / `⚙️ 設定與安裝`(1) | dx_app/static/js/i18n.js, dx_app/static/js/tutorial.js |

## 적용 방법

정해지면 해당 값으로 통일한 뒤 `tests/i18n_audit/test_quality_checks.py` 의
`MAX_TERMINOLOGY_DRIFT` 를 내린다.
