"""Scorer tests"""

import pytest
from pathlib import Path

from eval.scorer.exact import ExactMatchScorer
from eval.scorer.functional import FunctionalScorer
from eval.scorer.keyword_check import KeywordCheckScorer
from eval.scorer.composite import CompositeScorer
from eval.task import ScoringConfig


class TestExactMatchScorer:
    def setup_method(self):
        self.scorer = ExactMatchScorer()
        self.workspace = Path(".")

    async def test_contains_match(self):
        config = ScoringConfig(
            method="exact", expected="hello", match_mode="contains"
        )
        result = await self.scorer.score("say hello world", self.workspace, config)
        assert result.passed is True
        assert result.score == 1.0

    async def test_contains_no_match(self):
        config = ScoringConfig(
            method="exact", expected="goodbye", match_mode="contains"
        )
        result = await self.scorer.score("hello world", self.workspace, config)
        assert result.passed is False
        assert result.score == 0.0

    async def test_exact_match(self):
        config = ScoringConfig(
            method="exact", expected="hello", match_mode="exact"
        )
        result = await self.scorer.score("hello", self.workspace, config)
        assert result.passed is True

    async def test_exact_no_match(self):
        config = ScoringConfig(
            method="exact", expected="hello", match_mode="exact"
        )
        result = await self.scorer.score("hello world", self.workspace, config)
        assert result.passed is False

    async def test_regex_match(self):
        config = ScoringConfig(
            method="exact", expected=r"score: \d+", match_mode="regex"
        )
        result = await self.scorer.score("The score: 42 points", self.workspace, config)
        assert result.passed is True


class TestFunctionalScorer:
    def setup_method(self):
        self.scorer = FunctionalScorer()

    async def test_pass_pattern_found(self, tmp_path):
        config = ScoringConfig(
            method="functional",
            command="echo ALL TESTS PASSED",
            pass_pattern="ALL TESTS PASSED",
        )
        result = await self.scorer.score("", tmp_path, config)
        assert result.passed is True
        assert result.score == 1.0

    async def test_pass_pattern_not_found(self, tmp_path):
        config = ScoringConfig(
            method="functional",
            command="echo something else",
            pass_pattern="ALL TESTS PASSED",
        )
        result = await self.scorer.score("", tmp_path, config)
        assert result.passed is False
        assert result.score == 0.0

    async def test_workspace_substitution(self, tmp_path):
        (tmp_path / "hello.txt").write_text("world")
        config = ScoringConfig(
            method="functional",
            command="cat {{workspace}}/hello.txt",
            pass_pattern="world",
        )
        result = await self.scorer.score("", tmp_path, config)
        assert result.passed is True

    async def test_exit_code_nonzero(self, tmp_path):
        config = ScoringConfig(
            method="functional",
            command="exit 1",
        )
        result = await self.scorer.score("", tmp_path, config)
        assert result.passed is False
        assert "exit code 1" in result.detail

    async def test_no_command(self, tmp_path):
        config = ScoringConfig(method="functional")
        result = await self.scorer.score("", tmp_path, config)
        assert result.passed is False
        assert "no command" in result.detail


class TestKeywordCheckScorer:
    def setup_method(self):
        self.scorer = KeywordCheckScorer()

    async def test_all_keywords_found(self):
        config = ScoringConfig(
            method="keyword_check",
            required_keywords=["准备", "迁移", "验证"],
        )
        result = await self.scorer.score(
            "准备阶段：检查数据。迁移阶段：执行。验证阶段：确认。",
            Path("."),
            config,
        )
        assert result.passed is True
        assert result.score == 1.0

    async def test_partial_keywords(self):
        config = ScoringConfig(
            method="keyword_check",
            required_keywords=["准备", "迁移", "验证", "回滚"],
        )
        result = await self.scorer.score(
            "准备阶段和迁移阶段。", Path("."), config
        )
        assert result.passed is False
        assert result.score == 0.5

    async def test_no_keywords(self):
        config = ScoringConfig(method="keyword_check")
        result = await self.scorer.score("some text", Path("."), config)
        assert result.passed is True


class TestCompositeScorer:
    def setup_method(self):
        self.scorer = CompositeScorer()

    async def test_weighted_combination(self, tmp_path):
        config = ScoringConfig(
            method="composite",
            weights={"check_a": 1.0, "check_b": 1.0},
            sub_scorers={
                "check_a": ScoringConfig(
                    method="keyword_check",
                    required_keywords=["hello"],
                ),
                "check_b": ScoringConfig(
                    method="keyword_check",
                    required_keywords=["world"],
                ),
            },
        )
        result = await self.scorer.score(
            "hello world", tmp_path, config
        )
        assert result.passed is True
        assert result.score == 1.0

    async def test_partial(self, tmp_path):
        config = ScoringConfig(
            method="composite",
            weights={"check_a": 1.0, "check_b": 1.0},
            sub_scorers={
                "check_a": ScoringConfig(
                    method="keyword_check",
                    required_keywords=["hello"],
                ),
                "check_b": ScoringConfig(
                    method="keyword_check",
                    required_keywords=["missing"],
                ),
            },
        )
        result = await self.scorer.score(
            "hello world", tmp_path, config
        )
        assert result.passed is False
        assert result.score == 0.5

    async def test_no_sub_scorers(self, tmp_path):
        config = ScoringConfig(method="composite")
        result = await self.scorer.score("text", tmp_path, config)
        assert result.passed is False
        assert "no sub_scorers" in result.detail
