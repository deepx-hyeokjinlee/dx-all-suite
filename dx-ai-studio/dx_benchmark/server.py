#!/usr/bin/env python3
"""DX Benchmark 웹 서버 — 포트 8097.

YOLO26 하드웨어 벤치마크 대시보드 서버 (결과 조회·비교).
실행은 CLI (`benchmark.sh` / `python -m dx_benchmark.core run`) 사용.
DXBaseHandler 기반.
"""

import json
import os
import tempfile
from pathlib import Path

from shared.dx_server import DXBaseHandler, DXServer
from shared.chat import ChatEngine
from shared.paths import outputs_dir

DEFAULT_PORT = 8097
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
RESULTS_DIR = outputs_dir("benchmark")
LEGACY_RESULTS_DIR = BASE_DIR / "results"
DATASET_PATH = BASE_DIR / "dataset.json"
SERVER_NAME = "DX Benchmark"


def iter_result_dirs():
    """Yield result directories: canonical first, then legacy if it exists."""
    yield RESULTS_DIR
    if LEGACY_RESULTS_DIR.exists():
        yield LEGACY_RESULTS_DIR


def _without_meta_field(data, field):
    cloned = json.loads(json.dumps(data, default=str))
    if isinstance(cloned.get("meta"), dict):
        cloned["meta"].pop(field, None)
    return cloned


def _dataset_only_generated_at_changed(dataset):
    if not DATASET_PATH.exists():
        return False
    try:
        existing = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return _without_meta_field(existing, "generated_at") == _without_meta_field(dataset, "generated_at")


_chat_engine = ChatEngine(
    app_name="dx_benchmark",
    fallback_rules=[
        (["benchmark", "벤치마크", "run", "실행"], {
            "ko": "벤치마크 실행은 CLI에서 수행합니다: `cd dx_benchmark && ./benchmark.sh` 또는 `python -m dx_benchmark.core run`. 웹 UI는 Dashboard/Results에서 결과를 조회합니다.",
            "en": "Run benchmarks from the CLI: `cd dx_benchmark && ./benchmark.sh` or `python -m dx_benchmark.core run`. Use the web UI Dashboard/Results tabs to view results.",
        }),
        (["result", "결과", "report", "리포트", "대시보드", "dashboard"], {
            "ko": "Dashboard 탭에서 집계된 차트를, Results 탭에서 개별 실행 결과와 REPORT.md를 확인할 수 있습니다.",
            "en": "View aggregated charts in the Dashboard tab, and individual run results with REPORT.md in the Results tab.",
        }),
        (["yolo", "model", "모델", "YOLO26"], {
            "ko": "YOLO26 계열 모델(n/s/m/l)의 NPU 성능을 하드웨어별로 비교 측정합니다.",
            "en": "Compares NPU performance of YOLO26 models (n/s/m/l) across different hardware.",
        }),
        (["hardware", "하드웨어", "보드", "board", "device"], {
            "ko": "AI Box, ROCK5B+, OrangePi5+, Raspberry Pi, BIOSTAR 등 다양한 하드웨어를 지원합니다.",
            "en": "Supports various hardware including AI Box, ROCK5B+, OrangePi5+, Raspberry Pi, BIOSTAR, etc.",
        }),
    ]
)

def _aggregate_all_result_dirs():
    """Aggregate across all result dirs (canonical-first), merging datasets."""
    from dx_benchmark.core.aggregator import aggregate_result_directories
    dirs = list(iter_result_dirs())
    merged = aggregate_result_directories(dirs[0])
    for extra_dir in dirs[1:]:
        if not extra_dir.exists():
            continue
        extra = aggregate_result_directories(extra_dir)
        # environments: dedup by hw_id, canonical-first
        if "environments" in merged and "environments" in extra:
            seen_hw = {e.get("hw_id") for e in merged["environments"]}
            for e in extra["environments"]:
                if e.get("hw_id") not in seen_hw:
                    merged["environments"].append(e)
                    seen_hw.add(e.get("hw_id"))
        # runs: dedup by (env_id, run_id), canonical-first
        if "runs" in merged and "runs" in extra:
            seen_runs = {
                (r.get("env_id"), r.get("run_id")) for r in merged["runs"]
            }
            for r in extra["runs"]:
                key = (r.get("env_id"), r.get("run_id"))
                if key not in seen_runs:
                    merged["runs"].append(r)
                    seen_runs.add(key)
        # history: dict of lists, concatenated (no dedup). Safe because legacy
        # is a frozen tracked dataset and canonical only ever accrues fresh
        # run_ids post-repoint, so canonical/legacy history entries are
        # assumed disjoint (no overlapping keys to double-count).
        if "history" in merged and "history" in extra:
            for k, v in extra["history"].items():
                if k in merged["history"]:
                    merged["history"][k] = merged["history"][k] + v
                else:
                    merged["history"][k] = v
        # summaries: dict of lists, merge each sublist canonical-first
        # Dedup keys match aggregator's _dedup_latest key fields
        _summary_keys = {
            "model": ("env_id", "model", "use_ort", "family"),
            "e2e_single": ("env_id", "model", "use_ort"),
            "e2e_multi_capacity": ("env_id", "model", "use_ort"),
            "ort_delta": ("env_id", "metric", "task", "size"),
        }
        if "summaries" in extra:
            merged.setdefault("summaries", {})
            for subkey, extra_rows in extra["summaries"].items():
                if subkey not in merged["summaries"]:
                    merged["summaries"][subkey] = list(extra_rows)
                    continue
                existing = merged["summaries"][subkey]
                key_fields = _summary_keys.get(subkey, None)
                if key_fields:
                    seen_keys = {
                        tuple(r.get(f) for f in key_fields) for r in existing
                    }
                    for r in extra_rows:
                        rk = tuple(r.get(f) for f in key_fields)
                        if rk not in seen_keys:
                            existing.append(r)
                            seen_keys.add(rk)
                else:
                    # Unknown subkey: use full-row identity
                    seen_keys = {tuple(sorted(r.items())) for r in existing}
                    for r in extra_rows:
                        rk = tuple(sorted(r.items()))
                        if rk not in seen_keys:
                            existing.append(r)
                            seen_keys.add(rk)
        # snapshots: dedup by (hw_id, run_id), canonical-first
        if "snapshots" in extra:
            merged.setdefault("snapshots", [])
            seen_snaps = {
                (s.get("hw_id"), s.get("run_id")) for s in merged["snapshots"]
            }
            for s in extra["snapshots"]:
                key = (s.get("hw_id"), s.get("run_id"))
                if key not in seen_snaps:
                    merged["snapshots"].append(s)
                    seen_snaps.add(key)
        # meta: keep canonical as-is (already in merged)
    # meta counts must reflect the final merged totals, not just canonical's own
    # (canonical starts empty post-repoint while legacy holds prior history/runs).
    if "meta" in merged:
        merged["meta"]["run_count"] = len(merged.get("runs", []))
        merged["meta"]["environment_count"] = len(merged.get("environments", []))
    return merged


def _regenerate_dataset():
    """Aggregate results/ into dataset.json using atomic write."""
    try:
        dataset = _aggregate_all_result_dirs()
        if _dataset_only_generated_at_changed(dataset):
            return
        fd, tmp = tempfile.mkstemp(dir=str(BASE_DIR), suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(dataset, f, indent=2, default=str)
            os.rename(tmp, str(DATASET_PATH))
        except Exception:
            os.unlink(tmp)
            raise
    except Exception as e:
        print(f"  [Benchmark] Dataset regeneration failed: {e}")


class DXBenchmarkHandler(DXBaseHandler):
    """DX Benchmark HTTP 요청 핸들러."""

    server_name = SERVER_NAME
    static_dir = STATIC_DIR
    templates_dir = TEMPLATES_DIR
    log_silent = True

    def route(self):
        if self.handle_chat_routes(_chat_engine):
            return

        if self.route_common():
            return

        path = self.url_path

        if self.command == "GET":
            if path == "/api/health":
                return self.send_json({"status": "ok"})
            if path == "/api/hb":
                return self.send_json({"ok": True})
            if path == "/api/dataset":
                return self._serve_dataset()
            if path == "/api/results":
                return self._serve_results_list()
            if path.startswith("/api/results/"):
                return self._serve_result_detail(path)
            if path == "/api/config":
                return self._serve_config()

        if self.command == "POST":
            if path == "/api/config":
                return self._handle_config_save()

        self.route_legacy()

    def _serve_dataset(self):
        if DATASET_PATH.exists():
            return self.send_file(DATASET_PATH, "application/json")
        return self.send_json({"environments": [], "runs": [], "history": {}})

    def _serve_results_list(self):
        # Canonical-first deduplication: track seen (hw_id, run_id) pairs
        seen_runs = {}  # {hw_id: {run_id: run_info}}
        for results_dir in iter_result_dirs():
            if not results_dir.exists():
                continue
            for hw_dir in sorted(results_dir.iterdir()):
                if hw_dir.is_dir() and not hw_dir.name.startswith("."):
                    hw_id = hw_dir.name
                    if hw_id not in seen_runs:
                        seen_runs[hw_id] = {}
                    for run_dir in sorted(hw_dir.iterdir(), reverse=True):
                        if run_dir.is_dir() and not run_dir.name.startswith("."):
                            if run_dir.name not in seen_runs[hw_id]:
                                seen_runs[hw_id][run_dir.name] = {
                                    "run_id": run_dir.name,
                                    "has_report": (run_dir / "REPORT.md").exists(),
                                }
        results = []
        for hw_id in sorted(seen_runs):
            runs = sorted(seen_runs[hw_id].values(),
                          key=lambda r: r["run_id"], reverse=True)
            if runs:
                results.append({"hw_id": hw_id, "runs": runs})
        return self.send_json(results)

    def _serve_result_detail(self, path):
        parts = path.replace("/api/results/", "").strip("/").split("/")
        if len(parts) < 2:
            return self.send_error_json(400, "Need hw_id/run_id")
        hw_id, run_id = parts[0], parts[1]
        # Find first matching run across result dirs (canonical first)
        run_dir = None
        for results_dir in iter_result_dirs():
            candidate = results_dir / hw_id / run_id
            if candidate.exists():
                run_dir = candidate
                break
        if run_dir is None:
            return self.send_error_json(404, "Run not found")
        if len(parts) == 3 and parts[2] == "report":
            report_path = run_dir / "REPORT.md"
            if report_path.exists():
                return self.send_json({"markdown": report_path.read_text(errors="replace")})
            return self.send_error_json(404, "Report not found")
        detail = {}
        for fname in ["environment.json", "model_results.json", "pipeline_results.json", "multi_stream_results.json"]:
            fpath = run_dir / fname
            if fpath.exists():
                try:
                    detail[fname.replace(".json", "")] = json.loads(fpath.read_text())
                except json.JSONDecodeError:
                    detail[fname.replace(".json", "")] = None
        return self.send_json(detail)

    def _serve_config(self):
        from dx_benchmark.core.config import BenchmarkConfig
        cfg = BenchmarkConfig()
        return self.send_json({
            "model_dir": str(BASE_DIR / "assets" / "models"),
            "video_dir": str(BASE_DIR / "assets" / "videos"),
            "results_dir": str(RESULTS_DIR),
            "cooldown_temp": cfg.thermal_cooldown_abs_cap_c,
            "wait_interval": cfg.thermal_cooldown_max_sec,
            "iterations": cfg.model_latency_loops,
            "warmup": cfg.model_warmup,
            "fps_threshold": cfg.fps_threshold,
        })

    def _handle_config_save(self):
        # Settings are deployment-fixed; drain body without parsing, return 501.
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length < 0:
                length = 0
        except (ValueError, TypeError):
            length = 0
        if length > 0:
            self.rfile.read(length)
        return self.send_json(
            {"ok": False, "error": "Settings are deployment-fixed and cannot be changed at runtime"},
            501,
        )


def create_server(port=DEFAULT_PORT):
    """테스트용 서버 팩토리: HTTPServer 인스턴스를 반환."""
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", port), DXBenchmarkHandler)
    srv.daemon_threads = True
    return srv


if __name__ == "__main__":
    _regenerate_dataset()
    DXServer(DXBenchmarkHandler, SERVER_NAME, default_port=DEFAULT_PORT).start()
