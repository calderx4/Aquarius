"""EvalRunner — 编排器：加载 task → provider 执行 → scorer 评分 → 汇总"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from loguru import logger

from eval.providers.base import AgentProvider, ProviderResult
from eval.providers.metrics import Metrics
from eval.scorer import get_scorer
from eval.scorer.base import ScoreResult
from eval.task import Task


@dataclass
class TaskResult:
    task: Task
    score: ScoreResult
    provider_result: ProviderResult

    def to_dict(self) -> dict:
        return {
            "task_id": self.task.id,
            "task_name": self.task.name,
            "category": self.task.category,
            "difficulty": self.task.difficulty,
            "score": self.score.to_dict(),
            "metrics": self.provider_result.metrics.to_dict(),
        }


@dataclass
class EvalRun:
    provider_name: str
    provider_version: str
    results: list[TaskResult] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    @property
    def average_score(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.score.score for r in self.results) / len(self.results)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.score.passed)

    @property
    def total_tasks(self) -> int:
        return len(self.results)

    @property
    def by_category(self) -> dict[str, list[TaskResult]]:
        cats: dict[str, list[TaskResult]] = {}
        for r in self.results:
            cats.setdefault(r.task.category, []).append(r)
        return cats

    def to_dict(self) -> dict:
        return {
            "provider": {
                "name": self.provider_name,
                "version": self.provider_version,
            },
            "timestamp": self.timestamp,
            "summary": {
                "total": self.total_tasks,
                "passed": self.pass_count,
                "average_score": round(self.average_score, 4),
            },
            "results": [r.to_dict() for r in self.results],
        }

    @classmethod
    def from_dict(cls, data: dict) -> EvalRun:
        results = []
        for r in data.get("results", []):
            task_data = {
                "id": r["task_id"],
                "name": r["task_name"],
                "category": r["category"],
                "difficulty": r["difficulty"],
            }
            task = Task.from_dict(task_data)
            score_data = r.get("score", {})
            score = ScoreResult(
                task_id=score_data.get("task_id", ""),
                passed=score_data.get("passed", False),
                score=score_data.get("score", 0.0),
                method=score_data.get("method", ""),
                detail=score_data.get("detail", ""),
                raw_output=score_data.get("raw_output", ""),
            )
            metrics_data = r.get("metrics", {})
            metrics = Metrics(**{
                k: v for k, v in metrics_data.items()
                if k in {f.name for f in dataclasses.fields(Metrics)}
            })
            provider_result = ProviderResult(
                response="",
                workspace=Path("."),
                metrics=metrics,
                raw_output={},
            )
            results.append(TaskResult(task=task, score=score, provider_result=provider_result))

        provider = data.get("provider", {})
        return cls(
            provider_name=provider.get("name", "unknown"),
            provider_version=provider.get("version", "unknown"),
            results=results,
            timestamp=data.get("timestamp", ""),
        )


class EvalRunner:
    def __init__(
        self,
        provider: AgentProvider,
        config: dict | None = None,
        on_task_complete: Callable[[EvalRun], None] | None = None,
    ):
        self.provider = provider
        self.config = config or {}
        self.on_task_complete = on_task_complete

    async def run_task(self, task: Task) -> TaskResult:
        workspace = self.provider.prepare_workspace(
            task.workspace_files, task.id
        )

        logger.info(f"Running task: {task.id} ({task.name})")

        provider_result = await self.provider.execute(
            prompt=task.prompt,
            workspace=workspace,
            config={
                "timeout": task.constraints.timeout_seconds,
                "max_turns": task.constraints.max_iterations,
            },
        )

        scorer = get_scorer(task.scoring.method)
        score_result = await scorer.score(
            response=provider_result.response,
            workspace=provider_result.workspace,
            scoring_config=task.scoring,
        )
        score_result.task_id = task.id

        status = "PASS" if score_result.passed else "FAIL"
        logger.info(
            f"  {task.id}: {status} score={score_result.score:.2f} "
            f"({score_result.detail})"
        )

        return TaskResult(
            task=task,
            score=score_result,
            provider_result=provider_result,
        )

    async def run_all(self, tasks: list[Task]) -> EvalRun:
        run = EvalRun(
            provider_name=self.provider.name,
            provider_version=self.provider.get_version(),
        )

        for task in tasks:
            try:
                result = await self.run_task(task)
                run.results.append(result)
            except Exception as e:
                logger.error(f"  {task.id}: ERROR — {e}")
                run.results.append(
                    TaskResult(
                        task=task,
                        score=ScoreResult(
                            task_id=task.id,
                            passed=False,
                            score=0.0,
                            method=task.scoring.method,
                            detail=f"ERROR: {e}",
                        ),
                        provider_result=ProviderResult(
                            response="",
                            workspace=Path("."),
                            metrics=Metrics(),
                            raw_output={},
                        ),
                    )
                )

            if self.on_task_complete:
                self.on_task_complete(run)

        return run
