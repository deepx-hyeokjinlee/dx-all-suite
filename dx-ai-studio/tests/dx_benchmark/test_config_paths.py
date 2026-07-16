"""Tests for benchmark result path configuration and legacy fallback."""

from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


def test_config_output_dir_matches_benchmark_results():
    from dx_benchmark.core.config import BenchmarkConfig
    studio_root = Path(__file__).resolve().parents[2]
    assert BenchmarkConfig().get_output_dir().resolve() == (studio_root / "outputs" / "benchmark").resolve()


def test_legacy_core_results_is_read_only_fallback():
    import dx_benchmark.server as server
    assert hasattr(server, "LEGACY_RESULTS_DIR")
    assert server.LEGACY_RESULTS_DIR.name == "results"
    assert server.LEGACY_RESULTS_DIR.parent.name == "dx_benchmark"


def test_iter_result_dirs_yields_canonical_first():
    """iter_result_dirs() yields RESULTS_DIR first."""
    import dx_benchmark.server as server
    dirs = list(server.iter_result_dirs())
    assert dirs[0] == server.RESULTS_DIR


def test_iter_result_dirs_yields_legacy_only_if_exists(tmp_path):
    """iter_result_dirs() yields LEGACY_RESULTS_DIR only when it exists on disk."""
    import dx_benchmark.server as server
    fake_canonical = tmp_path / "results"
    fake_canonical.mkdir()
    fake_legacy = tmp_path / "core" / "results"
    # legacy does not exist
    with patch.object(server, "RESULTS_DIR", fake_canonical), \
         patch.object(server, "LEGACY_RESULTS_DIR", fake_legacy):
        dirs = list(server.iter_result_dirs())
        assert dirs == [fake_canonical]

    # legacy exists
    fake_legacy.mkdir(parents=True)
    with patch.object(server, "RESULTS_DIR", fake_canonical), \
         patch.object(server, "LEGACY_RESULTS_DIR", fake_legacy):
        dirs = list(server.iter_result_dirs())
        assert dirs == [fake_canonical, fake_legacy]



def _make_dataset(*, environments=None, runs=None, history=None,
                  summaries=None, snapshots=None, meta=None):
    """Helper: build a dataset dict matching aggregator output shape."""
    return {
        "meta": meta or {
            "dataset_version": "v2",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_count": 0,
            "environment_count": 0,
        },
        "environments": environments or [],
        "runs": runs or [],
        "summaries": summaries or {"model": [], "e2e_single": [],
                                    "e2e_multi_capacity": [], "ort_delta": []},
        "history": history or {"model": [], "e2e_single": [],
                                "e2e_multi_capacity": []},
        "snapshots": snapshots or [],
    }


def test_aggregate_preserves_runs_with_same_run_id_different_env():
    """Two runs with same run_id but different env_id must both survive merge."""
    import dx_benchmark.server as server

    canonical = _make_dataset(runs=[
        {"run_id": "run-001", "env_id": "env-A", "path": "/c/env-A/run-001"},
    ])
    legacy = _make_dataset(runs=[
        {"run_id": "run-001", "env_id": "env-B", "path": "/l/env-B/run-001"},
    ])

    with patch.object(server, "RESULTS_DIR", Path("/fake/canonical")), \
         patch.object(server, "LEGACY_RESULTS_DIR", Path("/fake/legacy")), \
         patch("dx_benchmark.core.aggregator.aggregate_result_directories",
               side_effect=[canonical, legacy]):
        # Force legacy to "exist"
        with patch.object(Path, "exists", return_value=True):
            merged = server._aggregate_all_result_dirs()

    run_keys = {(r["env_id"], r["run_id"]) for r in merged["runs"]}
    assert ("env-A", "run-001") in run_keys
    assert ("env-B", "run-001") in run_keys
    assert len(merged["runs"]) == 2


def test_aggregate_merges_legacy_summaries_and_snapshots():
    """Legacy summaries and snapshots must appear in merged dataset."""
    import dx_benchmark.server as server

    canonical = _make_dataset(
        summaries={"model": [{"env_id": "A", "metric": "fps", "value": 10}],
                   "e2e_single": [], "e2e_multi_capacity": [], "ort_delta": []},
        snapshots=[{"hw_id": "hw-A", "run_id": "run-c1"}],
    )
    legacy = _make_dataset(
        summaries={"model": [{"env_id": "B", "metric": "fps", "value": 20}],
                   "e2e_single": [{"env_id": "B", "model": "yolo-n"}],
                   "e2e_multi_capacity": [], "ort_delta": []},
        snapshots=[{"hw_id": "hw-B", "run_id": "run-l1"}],
    )

    with patch.object(server, "RESULTS_DIR", Path("/fake/canonical")), \
         patch.object(server, "LEGACY_RESULTS_DIR", Path("/fake/legacy")), \
         patch("dx_benchmark.core.aggregator.aggregate_result_directories",
               side_effect=[canonical, legacy]):
        with patch.object(Path, "exists", return_value=True):
            merged = server._aggregate_all_result_dirs()

    # summaries sublists should contain both canonical and legacy entries
    assert len(merged["summaries"]["model"]) == 2
    assert any(s["env_id"] == "B" for s in merged["summaries"]["model"])
    assert len(merged["summaries"]["e2e_single"]) == 1

    # snapshots should contain both
    snap_ids = {(s["hw_id"], s["run_id"]) for s in merged["snapshots"]}
    assert ("hw-A", "run-c1") in snap_ids
    assert ("hw-B", "run-l1") in snap_ids


def test_aggregate_canonical_first_dedup_for_summaries():
    """When canonical and legacy have same identity summary, canonical wins."""
    import dx_benchmark.server as server

    canonical = _make_dataset(
        summaries={"model": [{"env_id": "A", "model": "yolo-n",
                              "use_ort": False, "family": "throughput",
                              "value": 100}],
                   "e2e_single": [], "e2e_multi_capacity": [], "ort_delta": []},
    )
    legacy = _make_dataset(
        summaries={"model": [{"env_id": "A", "model": "yolo-n",
                              "use_ort": False, "family": "throughput",
                              "value": 50}],
                   "e2e_single": [], "e2e_multi_capacity": [], "ort_delta": []},
    )

    with patch.object(server, "RESULTS_DIR", Path("/fake/canonical")), \
         patch.object(server, "LEGACY_RESULTS_DIR", Path("/fake/legacy")), \
         patch("dx_benchmark.core.aggregator.aggregate_result_directories",
               side_effect=[canonical, legacy]):
        with patch.object(Path, "exists", return_value=True):
            merged = server._aggregate_all_result_dirs()

    # Should have only 1 model summary (canonical wins)
    assert len(merged["summaries"]["model"]) == 1
    assert merged["summaries"]["model"][0]["value"] == 100


def test_aggregate_preserves_meta():
    """Merged dataset must contain meta from canonical."""
    import dx_benchmark.server as server

    canonical = _make_dataset(meta={"dataset_version": "v2", "run_count": 5,
                                     "environment_count": 2,
                                     "generated_at": "2025-01-01T00:00:00"})
    legacy = _make_dataset(meta={"dataset_version": "v2", "run_count": 3,
                                  "environment_count": 1,
                                  "generated_at": "2024-06-01T00:00:00"})

    with patch.object(server, "RESULTS_DIR", Path("/fake/canonical")), \
         patch.object(server, "LEGACY_RESULTS_DIR", Path("/fake/legacy")), \
         patch("dx_benchmark.core.aggregator.aggregate_result_directories",
               side_effect=[canonical, legacy]):
        with patch.object(Path, "exists", return_value=True):
            merged = server._aggregate_all_result_dirs()

    assert "meta" in merged
    assert merged["meta"]["dataset_version"] == "v2"


def test_aggregate_legacy_history_and_counts_when_canonical_empty():
    """When canonical is empty (post-repoint) and legacy holds prior runs/history,
    the merged dataset must surface legacy history and meta.run_count /
    meta.environment_count must reflect the merged totals, not 0."""
    import dx_benchmark.server as server

    canonical = _make_dataset()  # empty: no runs, no environments, no history
    legacy = _make_dataset(
        environments=[{"hw_id": "hw-1"}],
        runs=[{"run_id": "run-1", "env_id": "env-1", "path": "/l/env-1/run-1"}],
        history={"model": [{"env_id": "env-1", "ts": "t1"}],
                 "e2e_single": [], "e2e_multi_capacity": []},
    )

    with patch.object(server, "RESULTS_DIR", Path("/fake/canonical")), \
         patch.object(server, "LEGACY_RESULTS_DIR", Path("/fake/legacy")), \
         patch("dx_benchmark.core.aggregator.aggregate_result_directories",
               side_effect=[canonical, legacy]):
        with patch.object(Path, "exists", return_value=True):
            merged = server._aggregate_all_result_dirs()

    assert merged["history"]["model"] == [{"env_id": "env-1", "ts": "t1"}]
    assert merged["meta"]["run_count"] == 1
    assert merged["meta"]["environment_count"] == 1


def test_aggregate_history_concat_disjoint_keys_no_duplication():
    """With disjoint canonical+legacy history entries, the merged history for a
    subkey must contain both sides' entries exactly once each (concatenation,
    no dedup, no duplication of either side)."""
    import dx_benchmark.server as server

    canonical = _make_dataset(
        history={"model": [{"env_id": "env-A", "ts": "t-canonical"}],
                 "e2e_single": [], "e2e_multi_capacity": []},
    )
    legacy = _make_dataset(
        history={"model": [{"env_id": "env-B", "ts": "t-legacy"}],
                 "e2e_single": [], "e2e_multi_capacity": []},
    )

    with patch.object(server, "RESULTS_DIR", Path("/fake/canonical")), \
         patch.object(server, "LEGACY_RESULTS_DIR", Path("/fake/legacy")), \
         patch("dx_benchmark.core.aggregator.aggregate_result_directories",
               side_effect=[canonical, legacy]):
        with patch.object(Path, "exists", return_value=True):
            merged = server._aggregate_all_result_dirs()

    model_history = merged["history"]["model"]
    assert len(model_history) == 2
    assert {"env_id": "env-A", "ts": "t-canonical"} in model_history
    assert {"env_id": "env-B", "ts": "t-legacy"} in model_history
    assert model_history.count({"env_id": "env-A", "ts": "t-canonical"}) == 1
    assert model_history.count({"env_id": "env-B", "ts": "t-legacy"}) == 1


def test_aggregate_runs_dedup_by_env_and_run_id_still_holds():
    """Sibling category (runs) must still dedup by (env_id, run_id),
    canonical-first, even though history now concatenates without dedup."""
    import dx_benchmark.server as server

    canonical = _make_dataset(runs=[
        {"run_id": "run-1", "env_id": "env-1", "path": "/c/env-1/run-1"},
    ])
    legacy = _make_dataset(runs=[
        {"run_id": "run-1", "env_id": "env-1", "path": "/l/env-1/run-1"},
    ])

    with patch.object(server, "RESULTS_DIR", Path("/fake/canonical")), \
         patch.object(server, "LEGACY_RESULTS_DIR", Path("/fake/legacy")), \
         patch("dx_benchmark.core.aggregator.aggregate_result_directories",
               side_effect=[canonical, legacy]):
        with patch.object(Path, "exists", return_value=True):
            merged = server._aggregate_all_result_dirs()

    assert len(merged["runs"]) == 1
    assert merged["runs"][0]["path"] == "/c/env-1/run-1"


def test_regenerate_dataset_does_not_rewrite_when_only_generated_at_changes(tmp_path):
    """Launcher startup must not dirty tracked dataset.json when data is unchanged."""
    import json
    import dx_benchmark.server as server

    old_dataset = _make_dataset(meta={
        "dataset_version": "v2",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "run_count": 0,
        "environment_count": 0,
    })
    new_dataset = _make_dataset(meta={
        "dataset_version": "v2",
        "generated_at": "2026-02-01T00:00:00+00:00",
        "run_count": 0,
        "environment_count": 0,
    })
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(old_dataset, indent=2), encoding="utf-8")

    with patch.object(server, "BASE_DIR", tmp_path), \
         patch.object(server, "DATASET_PATH", dataset_path), \
         patch.object(server, "_aggregate_all_result_dirs", return_value=new_dataset):
        server._regenerate_dataset()

    saved = json.loads(dataset_path.read_text(encoding="utf-8"))
    assert saved["meta"]["generated_at"] == "2026-01-01T00:00:00+00:00"
