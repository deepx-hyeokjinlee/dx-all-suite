"""RecommendEngine logic tests (executed via Node.js VM)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RECOMMEND_JS = ROOT / "dx_planner/static/js/recommend.js"

_NODE_SCRIPT = r"""
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync(process.argv[1], 'utf8').replace(/^const RecommendEngine/, 'var RecommendEngine');
const ctx = { console };
vm.createContext(ctx);
vm.runInContext(code, ctx);
const RecommendEngine = ctx.RecommendEngine;

function assert(cond, msg) {
  if (!cond) {
    console.error('FAIL:', msg);
    process.exit(1);
  }
}

const bench = { throughput_fps: 276, latency_ms: 10 };
const multi = [
  { stream_count: 9, per_channel_fps: 30.7 },
  { stream_count: 10, per_channel_fps: 27.6 },
];

const measured = RecommendEngine._calcMaxChannels(bench, multi, 30, 0);
assert(measured.maxChannels === 9, '10% headroom should keep 9ch at 30fps target');
assert(measured.boundaryFlag === 'measured', 'expected measured flag');

const strict = RecommendEngine._calcMaxChannels(bench, multi, 30, 0.1);
assert(strict.maxChannels === 8, '33fps effective should theoretical floor(276/33)=8');
assert(strict.boundaryFlag === 'theoretical', 'expected theoretical under 10% headroom');

const interpolated = RecommendEngine._calcMaxChannels(bench, multi, 29, 0);
assert(interpolated.boundaryFlag === 'measured' || interpolated.maxChannels >= 9, '29fps should meet at 9+');

const platform = {
  id: 'p1',
  npu: { model: 'DX-M1', tops: 25, tdp_w: 5, price_usd: 99, dram: '1GB' },
  host: { name: 'Host', cpu: 'x', ram_gb: 8, os: 'linux' },
  benchmarks: [{
    model: 'yolo26n', task: 'object_detection', size: 'n', ort: true,
    throughput_fps: 276, latency_ms: 10,
  }],
  multi_stream: multi.map(r => ({
    model: 'yolo26n', task: 'object_detection', size: 'n', ort: true, ...r,
  })),
};

const inputs = {
  task: 'object_detection', size: 'n', cameras: 4, targetFps: 30,
  priority: 'cost', ort: true, fpsHeadroom: 0,
};
const results = RecommendEngine.recommend(inputs, [platform]);
assert(results.length === 1, 'one result expected');
assert(results[0].costPerChannelAtNeed === 24.75, 'cost at need should be 99/4');
assert(results[0].costPerChannelAtCapacity === 11, 'cost at capacity should be 99/9');
assert(results[0].meetsRequirement === true, 'should meet 4 channels');

const hotRow = {
  model: 'yolo26n', task: 'object_detection', size: 'n', ort: true,
  stream_count: 4, per_channel_fps: 35, avg_cpu_pct: 500, npu_throttled: false,
};
const hotPlatform = JSON.parse(JSON.stringify(platform));
hotPlatform.multi_stream = [hotRow];
const hotInputs = { ...inputs, cameras: 4 };
const hotResults = RecommendEngine.recommend(hotInputs, [hotPlatform]);
assert(hotResults[0].hostLimited === true, 'cpu budget should flag host-limited');
assert(hotResults[0].meetsRequirement === false, 'host limited should fail meets');

const dualM1 = JSON.parse(JSON.stringify(platform));
dualM1.topology = { device_count: 2, m1_modules: 2, h1_cards: 0, hw_config: 'M1' };
dualM1.npu.unit_price_usd = 99;
dualM1.npu.system_price_usd = 198;
dualM1.npu.price_usd = 99;
const dualResults = RecommendEngine.recommend(inputs, [dualM1]);
assert(dualResults[0].costPerChannelAtNeed === 49.5, 'dual M1 system price 198/4 = 49.5');

console.log('OK');
"""


def test_recommend_engine_node_logic():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")

    proc = subprocess.run(
        [node, "-e", _NODE_SCRIPT, str(RECOMMEND_JS)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK" in proc.stdout


def test_recommend_engine_source_contracts():
    src = RECOMMEND_JS.read_text(encoding="utf-8")
    for token in [
        "costPerChannelAtNeed",
        "costPerChannelAtCapacity",
        "_interpolateCrossing",
        "confidenceTier",
        "fpsHeadroom",
        "host-limited",
    ]:
        assert token in src
