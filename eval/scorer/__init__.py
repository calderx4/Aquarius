"""Scorer registry — method name → scorer class"""

from __future__ import annotations

from eval.scorer.base import BaseScorer
from eval.scorer.composite import CompositeScorer
from eval.scorer.exact import ExactMatchScorer
from eval.scorer.functional import FunctionalScorer
from eval.scorer.keyword_check import KeywordCheckScorer

SCORERS: dict[str, type[BaseScorer]] = {
    "exact": ExactMatchScorer,
    "functional": FunctionalScorer,
    "keyword_check": KeywordCheckScorer,
    "composite": CompositeScorer,
}


def get_scorer(method: str) -> BaseScorer:
    cls = SCORERS.get(method)
    if not cls:
        raise ValueError(
            f"Unknown scorer: {method}. Available: {list(SCORERS.keys())}"
        )
    return cls()


def list_scorers() -> list[str]:
    return list(SCORERS.keys())
