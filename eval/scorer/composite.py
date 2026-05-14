"""CompositeScorer — 多维度加权组合评分"""

from __future__ import annotations

from pathlib import Path

from eval.scorer.base import BaseScorer, ScoreResult
from eval.task import ScoringConfig


class CompositeScorer(BaseScorer):
    async def score(
        self,
        response: str,
        workspace: Path,
        scoring_config: ScoringConfig,
    ) -> ScoreResult:
        from eval.scorer import get_scorer

        sub_scorers = scoring_config.sub_scorers or {}
        weights = scoring_config.weights or {}

        if not sub_scorers:
            return ScoreResult(
                passed=False,
                score=0.0,
                method="composite",
                detail="no sub_scorers configured",
            )

        results: dict[str, ScoreResult] = {}
        for name, sub_config in sub_scorers.items():
            scorer = get_scorer(sub_config.method)
            result = await scorer.score(response, workspace, sub_config)
            result.task_id = ""
            results[name] = result

        total_weight = sum(weights.get(n, 1.0) for n in results)
        if total_weight == 0:
            total_weight = 1.0

        weighted_score = sum(
            results[n].score * weights.get(n, 1.0) for n in results
        ) / total_weight

        all_passed = all(r.passed for r in results.values())
        detail_parts = {
            n: {"score": round(r.score, 3), "passed": r.passed, "detail": r.detail}
            for n, r in results.items()
        }

        import json

        return ScoreResult(
            passed=all_passed,
            score=weighted_score,
            method="composite",
            detail=json.dumps(detail_parts),
        )
