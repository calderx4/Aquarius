"""Compare tests"""

import json
import pytest
from pathlib import Path

from eval.compare import compare_runs, generate_comparison_markdown, load_run
from eval.providers.metrics import Metrics
from eval.providers.base import ProviderResult
from eval.runner import EvalRun, TaskResult
from eval.scorer.base import ScoreResult
from eval.task import Task


def _make_run(provider_name: str, scores: dict[str, float]) -> EvalRun:
    results = []
    for tid, score in scores.items():
        task = Task.from_dict({
            "id": tid,
            "name": f"Task {tid}",
            "category": "code",
            "difficulty": "medium",
        })
        results.append(TaskResult(
            task=task,
            score=ScoreResult(
                task_id=tid,
                passed=score >= 0.5,
                score=score,
                method="functional",
            ),
            provider_result=ProviderResult(
                response="",
                workspace=Path("."),
                metrics=Metrics(),
                raw_output={},
            ),
        ))
    return EvalRun(
        provider_name=provider_name,
        provider_version="1.0",
        results=results,
    )


class TestCompareRuns:
    def test_two_runs(self):
        run_a = _make_run("agent-a", {"t1": 0.5, "t2": 0.8, "t3": 0.3})
        run_b = _make_run("agent-b", {"t1": 0.7, "t2": 0.6, "t3": 0.3})
        report = compare_runs([run_a, run_b])

        assert report.comparison_type == "cross-agent"
        assert len(report.task_ids) == 3

        assert abs(report.deltas["t1"][0] - 0.5) < 1e-9
        assert abs(report.deltas["t1"][1] - 0.7) < 1e-9
        assert abs(report.deltas["t1"][2] - 0.2) < 1e-9
        assert "t1" in report.improvements

        assert abs(report.deltas["t2"][2] - (-0.2)) < 1e-9
        assert "t2" in report.regressions

        assert report.deltas["t3"] == [0.3, 0.3, 0.0]
        assert "t3" not in report.improvements
        assert "t3" not in report.regressions

    def test_version_comparison(self):
        run_v1 = _make_run("capricorn-x", {"t1": 0.6})
        run_v2 = _make_run("capricorn-x", {"t1": 0.9})
        report = compare_runs([run_v1, run_v2])
        assert report.comparison_type == "version"
        assert "t1" in report.improvements

    def test_single_run(self):
        run = _make_run("agent-a", {"t1": 0.5})
        report = compare_runs([run])
        assert report.comparison_type == "single"


class TestComparisonMarkdown:
    def test_contains_runs(self):
        run_a = _make_run("agent-a", {"t1": 0.5})
        run_b = _make_run("agent-b", {"t1": 0.8})
        report = compare_runs([run_a, run_b])
        md = generate_comparison_markdown(report)

        assert "agent-a" in md
        assert "agent-b" in md
        assert "Improvements" in md


class TestLoadRun:
    def test_roundtrip(self, tmp_path):
        run = _make_run("test-agent", {"t1": 0.75, "t2": 0.5})
        data = run.to_dict()
        path = tmp_path / "result.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        loaded = load_run(path)
        assert loaded.provider_name == "test-agent"
        assert loaded.total_tasks == 2
        assert loaded.results[0].score.score == 0.75
