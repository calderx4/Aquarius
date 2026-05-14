"""Report tests"""

import pytest
from pathlib import Path

from eval.providers.metrics import Metrics
from eval.providers.base import ProviderResult
from eval.report import generate_markdown, generate_json
from eval.runner import EvalRun, TaskResult
from eval.scorer.base import ScoreResult
from eval.task import Task


def _make_run(passed_count: int, total: int) -> EvalRun:
    results = []
    for i in range(total):
        task = Task.from_dict({
            "id": f"task-{i:03d}",
            "name": f"Task {i}",
            "category": "code" if i < total // 2 else "general",
            "difficulty": "easy",
        })
        results.append(TaskResult(
            task=task,
            score=ScoreResult(
                task_id=task.id,
                passed=i < passed_count,
                score=1.0 if i < passed_count else 0.0,
                method="functional",
                detail="PASS" if i < passed_count else "FAIL",
            ),
            provider_result=ProviderResult(
                response="",
                workspace=Path("."),
                metrics=Metrics(total_tokens=100 * (i + 1)),
                raw_output={},
            ),
        ))
    return EvalRun(
        provider_name="test-agent",
        provider_version="1.0",
        results=results,
    )


class TestGenerateMarkdown:
    def test_contains_header(self):
        run = _make_run(2, 3)
        md = generate_markdown(run)
        assert "# Eval Report: test-agent" in md
        assert "Version:** 1.0" in md

    def test_contains_summary(self):
        run = _make_run(2, 3)
        md = generate_markdown(run)
        assert "Tasks: 3" in md
        assert "Passed: 2/3" in md

    def test_contains_task_table(self):
        run = _make_run(1, 2)
        md = generate_markdown(run)
        assert "task-000" in md
        assert "task-001" in md

    def test_by_category(self):
        run = _make_run(3, 4)
        md = generate_markdown(run)
        assert "**code**:" in md or "**general**:" in md


class TestGenerateJson:
    def test_valid_json(self):
        run = _make_run(1, 2)
        import json
        data = json.loads(generate_json(run))
        assert data["provider"]["name"] == "test-agent"
        assert data["summary"]["total"] == 2
        assert len(data["results"]) == 2
