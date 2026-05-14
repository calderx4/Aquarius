"""ExactMatchScorer — 字符串精确/包含/正则匹配"""

from __future__ import annotations

import re
from pathlib import Path

from eval.scorer.base import BaseScorer, ScoreResult
from eval.task import ScoringConfig


class ExactMatchScorer(BaseScorer):
    async def score(
        self,
        response: str,
        workspace: Path,
        scoring_config: ScoringConfig,
    ) -> ScoreResult:
        expected = scoring_config.expected or ""
        mode = scoring_config.match_mode

        if mode == "exact":
            passed = expected.strip() == response.strip()
            detail = "exact match" if passed else "no exact match"
        elif mode == "regex":
            passed = bool(re.search(expected, response))
            detail = "regex matched" if passed else "regex not matched"
        else:  # contains
            passed = expected in response
            detail = "contains match" if passed else "expected text not found"

        return ScoreResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            method="exact",
            detail=detail,
            raw_output=response[:500],
        )
