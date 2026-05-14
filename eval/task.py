"""Task — Agent-agnostic 任务定义与 YAML 加载"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ScoringConfig:
    method: str = "exact"
    expected: str | None = None
    match_mode: str = "contains"
    command: str | None = None
    command_timeout: int = 30
    pass_pattern: str | None = None
    case_sensitive: bool = True
    expected_numbers: dict[str, float] | None = None
    tolerance: float = 0.05
    required_keywords: list[str] | None = None
    rubric: str | None = None
    weights: dict[str, float] | None = None
    sub_scorers: dict[str, Any] | None = None


@dataclass
class TaskConstraints:
    max_iterations: int = 15
    timeout_seconds: int = 120
    max_tokens: int = 10000


@dataclass
class Task:
    id: str
    name: str
    category: str
    difficulty: str = "medium"
    tags: list[str] = field(default_factory=list)
    vertical: str | None = None
    prompt: str = ""
    workspace_files: dict[str, str] = field(default_factory=dict)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    constraints: TaskConstraints = field(default_factory=TaskConstraints)

    @classmethod
    def from_yaml(cls, path: Path) -> Task:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        scoring_data = data.get("scoring", {})
        sub_scorers = None
        if scoring_data.get("sub_scorers"):
            sub_scorers = {k: ScoringConfig(**v) for k, v in scoring_data["sub_scorers"].items()}

        scoring = ScoringConfig(
            method=scoring_data.get("method", "exact"),
            expected=scoring_data.get("expected"),
            match_mode=scoring_data.get("match_mode", "contains"),
            command=scoring_data.get("command"),
            command_timeout=scoring_data.get("command_timeout", 30),
            pass_pattern=scoring_data.get("pass_pattern"),
            case_sensitive=scoring_data.get("case_sensitive", True),
            expected_numbers=scoring_data.get("expected_numbers"),
            tolerance=scoring_data.get("tolerance", 0.05),
            required_keywords=scoring_data.get("required_keywords"),
            rubric=scoring_data.get("rubric"),
            weights=scoring_data.get("weights"),
            sub_scorers=sub_scorers,
        )

        constraints_data = data.get("constraints", {})
        constraints = TaskConstraints(
            max_iterations=constraints_data.get("max_iterations", 15),
            timeout_seconds=constraints_data.get("timeout_seconds", 120),
            max_tokens=constraints_data.get("max_tokens", 10000),
        )

        input_data = data.get("input", {})
        return cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            difficulty=data.get("difficulty", "medium"),
            tags=data.get("tags", []),
            vertical=data.get("vertical"),
            prompt=input_data.get("prompt", ""),
            workspace_files=input_data.get("workspace_files", {}),
            scoring=scoring,
            constraints=constraints,
        )

    @classmethod
    def load_directory(cls, path: Path) -> list[Task]:
        return [cls.from_yaml(f) for f in sorted(path.rglob("*.yaml"))]