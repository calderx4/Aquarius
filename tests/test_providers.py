"""Provider tests"""

import pytest
from pathlib import Path

from eval.providers.base import AgentProvider, ProviderResult
from eval.providers.metrics import Metrics
from eval.providers import get_provider, list_providers, PROVIDERS


class TestProviderResult:
    def test_fields(self):
        result = ProviderResult(
            response="hello",
            workspace=Path("."),
            metrics=Metrics(),
            raw_output={"key": "val"},
            agent_name="test",
        )
        assert result.response == "hello"
        assert result.agent_name == "test"
        assert result.metrics.total_tokens == 0


class TestAgentProviderABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            AgentProvider()

    def test_prepare_workspace(self, tmp_path):
        class _Dummy(AgentProvider):
            name = "dummy"
            async def execute(self, prompt, workspace, config):
                return ProviderResult(
                    response="", workspace=workspace, metrics=Metrics(), raw_output={}
                )
            def get_version(self):
                return "0.0.1"

        provider = _Dummy()
        ws = provider.prepare_workspace(
            {"test.py": "print('hello')"}, "test-001"
        )
        assert ws.exists()
        assert (ws / "test.py").exists()
        assert (ws / "test.py").read_text() == "print('hello')"

        provider.cleanup()
        assert not ws.exists()


class TestMetricsComputed:
    def test_tool_success_rate_no_calls(self):
        m = Metrics()
        assert m.tool_success_rate == 1.0

    def test_tool_success_rate_with_calls(self):
        m = Metrics(tool_call_count=10, tool_success_count=8)
        assert m.tool_success_rate == 0.8

    def test_available_metrics_empty(self):
        m = Metrics()
        assert m.available_metrics == []

    def test_available_metrics_filled(self):
        m = Metrics(total_tokens=100, iterations=5, tool_call_count=3)
        assert "tokens" in m.available_metrics
        assert "iterations" in m.available_metrics
        assert "tool_calls" in m.available_metrics


class TestMetricsFromRaw:
    def test_parse_session_data(self):
        """Session data (per-thread) takes priority over trace (global)."""
        trace = [
            {"type": "round_start", "round": 1},
            {"type": "tool_call", "tool": "read_file", "status": "ok"},
            {"type": "round_end", "latency_ms": 500, "tool_calls": 1},
        ]
        session = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "name": "read_file", "args": {"path": "/tmp/a.py"}},
                {"id": "c2", "name": "write_file", "args": {"path": "/tmp/b.py"}},
            ]},
            {"role": "tool", "content": "ok", "tool_call_id": "c1"},
            {"role": "tool", "content": "[ERROR] permission denied", "tool_call_id": "c2"},
            {"role": "assistant", "content": "world"},
        ]
        m = Metrics.from_raw(trace, session, elapsed_seconds=1.5)
        assert m.source == "session"
        assert m.iterations == 2
        assert m.tool_call_count == 2
        assert m.tool_names_used == ["read_file", "write_file"]
        assert m.message_count == 5
        assert m.total_latency_ms == 1500
        assert m.final_response_length == 5  # "world"

    def test_trace_fallback(self):
        """Falls back to trace when no session data."""
        trace = [
            {"type": "round_start", "round": 1},
            {"type": "tool_call", "tool": "read_file", "status": "ok"},
            {"type": "tool_call", "tool": "write_file", "status": "error"},
            {"type": "round_end", "latency_ms": 500, "tool_calls": 2},
        ]
        m = Metrics.from_raw(trace, session=[], elapsed_seconds=1.5)
        assert m.source == "trace"
        assert m.tool_call_count == 2
        assert m.tool_success_count == 1
        assert m.tool_error_count == 1
        assert m.total_latency_ms == 1500


class TestProviderRegistry:
    def test_get_known_provider(self):
        provider = get_provider("capricorn-x")
        assert provider.name == "capricorn-x"

    def test_get_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent")

    def test_list_providers(self):
        providers = list_providers()
        assert "capricorn-x" in providers
        assert "capricorn-v" in providers
        assert "claude-code" in providers

    def test_all_providers_instantiable(self):
        for name in list_providers():
            provider = get_provider(name)
            assert provider.name == name
