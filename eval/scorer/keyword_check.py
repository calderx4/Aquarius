"""KeywordCheckScorer — 关键词出现检查"""

from __future__ import annotations

from pathlib import Path

from eval.scorer.base import BaseScorer, ScoreResult
from eval.task import ScoringConfig


class KeywordCheckScorer(BaseScorer):
    async def score(
        self,
        response: str,
        workspace: Path,
        scoring_config: ScoringConfig,
    ) -> ScoreResult:
        keywords = scoring_config.required_keywords or []
        if not keywords:
            return ScoreResult(
                passed=True,
                score=1.0,
                method="keyword_check",
                detail="no keywords to check",
            )

        found = [kw for kw in keywords if kw in response]
        missing = [kw for kw in keywords if kw not in response]
        score = len(found) / len(keywords)
        passed = len(missing) == 0

        detail = (
            "all keywords found"
            if passed
            else f"missing: {missing}"
        )

        return ScoreResult(
            passed=passed,
            score=score,
            method="keyword_check",
            detail=detail,
        )
