"""gstshark.py 테스트"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "dx_stream"))


class TestGstSharkModule:
    def test_module_importable(self):
        from core.gstshark import is_installed, parse_trace
        assert callable(is_installed)
        assert callable(parse_trace)

    def test_is_installed_returns_bool(self):
        from core.gstshark import is_installed
        result = is_installed()
        assert isinstance(result, bool)

    def test_parse_trace_empty_dir(self):
        import tempfile
        from core.gstshark import parse_trace
        with tempfile.TemporaryDirectory() as tmpdir:
            result = parse_trace(tmpdir)
            assert isinstance(result, dict)

    def test_gstshark_install_marks_badge_done_immediately(self):
        script = Path(__file__).resolve().parent.parent.parent / "dx_stream" / "static" / "js" / "stream-shark.js"
        text = script.read_text(encoding="utf-8")

        assert "DXStream.shark._installCompleted" in text
        assert "DXStream.shark.markInstalled" in text
        assert "DXStream.shark.markInstalled();" in text
        assert "data.install_log.done && data.install_log.ok" in text
