"""BaseScorer — 评分器基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from eval.task import ScoringConfig


@dataclass
class ScoreResult:
    """单个 task 的评分结果"""

    task_id: str = ""
    passed: bool = False
    score: float = 0.0
    method: str = ""
    detail: str = ""
    raw_output: str = ""

    def to_dict(self) -> dict:
        import dataclasses

        return dataclasses.asdict(self)


class BaseScorer(ABC):
    """评分器基类 — Agent 无关"""

    @abstractmethod
    async def score(
        self,
        response: str,
        workspace: Path,
        scoring_config: ScoringConfig,
    ) -> ScoreResult:
        ...
