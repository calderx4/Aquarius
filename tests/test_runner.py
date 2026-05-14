"""Runner tests"""

import pytest
from pathlib import Path

from eval.providers.base import AgentProvider, ProviderResult
from eval.providers.metrics import Metrics
from eval.runner import EvalRunner, EvalRun, TaskResult
from eval.scorer.base import ScoreResult
from eval.task import Task


class _MockProvider(AgentProvider):
    name = "mock"

    def __init__(self, config=None, response="mock response"):
        super().__init__(config)
        self._response = response

    async def execute(self, prompt, workspace, config):
        return ProviderResult(
            response=self._response,
            workspace=workspace,
            metrics=Metrics(),
            raw_output={},
            agent_name=self.name,
        )

    def get_version(self):
        return "0.0.1-test"


class TestEvalRunnerRunTask:
    async def test_run_single_task(self, tmp_path):
        task = Task.from_dict({
            "id": "test-001",
            "name": "Test",
            "category": "code",
            "input": {"prompt": "say hello"},
            "scoring": {
                "method": "exact",
                "expected": "hello",
                "match_mode": "contains",
            },
        })
        provider = _MockProvider(response="hello world")
        runner = EvalRunner(provider)
        result = await runner.run_task(task)

        assert result.score.passed is True
        assert result.score.score == 1.0
        assert result.task.id == "test-001"


class TestEvalRunnerRunAll:
    async def test_run_multiple_tasks(self):
        tasks = [
            Task.from_dict({
                "id": f"test-{i:03d}",
                "name": f"Task {i}",
                "category": "code",
                "input": {"prompt": "prompt"},
                "scoring": {"method": "exact", "expected": "hello", "match_mode": "contains"},
            })
            for i in range(3)
        ]
        provider = _MockProvider(response="hello")
        runner = EvalRunner(provider)
        run = await runner.run_all(tasks)

        assert run.total_tasks == 3
        assert run.pass_count == 3
        assert run.average_score == 1.0
        assert run.provider_name == "mock"


class TestEvalRun:
    def test_by_category(self):
        tasks = [
            Task.from_dict({"id": "a1", "name": "A", "category": "code"}),
            Task.from_dict({"id": "a2", "name": "B", "category": "code"}),
            Task.from_dict({"id": "a3", "name": "C", "category": "general"}),
        ]
        results = [
            TaskResult(
                task=t,
                score=ScoreResult(passed=True, score=1.0),
                provider_result=ProviderResult(
                    response="", workspace=Path("."), metrics=Metrics(), raw_output={}
                ),
            )
            for t in tasks
        ]
        run = EvalRun(provider_name="test", provider_version="0.1", results=results)
        cats = run.by_category
        assert len(cats["code"]) == 2
        assert len(cats["general"]) == 1

    def test_serialization_roundtrip(self):
        tasks = [
            Task.from_dict({
                "id": "test-001",
                "name": "Test",
                "category": "code",
                "difficulty": "easy",
            }),
        ]
        results = [
            TaskResult(
                task=tasks[0],
                score=ScoreResult(
                    task_id="test-001",
                    passed=True,
                    score=0.85,
                    method="exact",
                    detail="contains match",
                ),
                provider_result=ProviderResult(
                    response="hello",
                    workspace=Path("."),
                    metrics=Metrics(total_tokens=100),
                    raw_output={},
                ),
            )
        ]
        run = EvalRun(
            provider_name="test",
            provider_version="0.1",
            results=results,
        )

        data = run.to_dict()
        assert data["summary"]["total"] == 1
        assert data["summary"]["passed"] == 1

        restored = EvalRun.from_dict(data)
        assert restored.provider_name == "test"
        assert restored.total_tasks == 1
        assert restored.results[0].score.score == 0.85
