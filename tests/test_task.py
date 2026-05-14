"""Task system tests"""

import pytest
import yaml
from pathlib import Path

from eval.task import Task, ScoringConfig, TaskConstraints


class TestScoringConfigDefaults:
    def setup_method(self):
        self.config = ScoringConfig()

    def test_method_default(self):
        assert self.config.method == "exact"

    def test_match_mode_default(self):
        assert self.config.match_mode == "contains"

    def test_tolerance_default(self):
        assert self.config.tolerance == 0.05

    def test_optional_fields_none(self):
        assert self.config.expected is None
        assert self.config.command is None
        assert self.config.pass_pattern is None
        assert self.config.expected_numbers is None
        assert self.config.required_keywords is None
        assert self.config.rubric is None
        assert self.config.weights is None
        assert self.config.sub_scorers is None


class TestTaskConstraintsDefaults:
    def setup_method(self):
        self.constraints = TaskConstraints()

    def test_max_iterations(self):
        assert self.constraints.max_iterations == 15

    def test_timeout(self):
        assert self.constraints.timeout_seconds == 120

    def test_max_tokens(self):
        assert self.constraints.max_tokens == 10000


class TestTaskFromDict:
    def test_minimal(self):
        data = {
            "id": "test-001",
            "name": "Test",
            "category": "code",
        }
        task = Task.from_dict(data)
        assert task.id == "test-001"
        assert task.name == "Test"
        assert task.category == "code"
        assert task.difficulty == "medium"
        assert task.prompt == ""
        assert task.workspace_files == {}

    def test_full(self):
        data = {
            "id": "test-002",
            "name": "Full Test",
            "category": "code",
            "difficulty": "hard",
            "tags": ["python", "debug"],
            "input": {
                "prompt": "Fix the bug",
                "workspace_files": {"bug.py": "code here"},
            },
            "scoring": {
                "method": "functional",
                "command": "python test.py",
                "pass_pattern": "PASS",
            },
            "constraints": {
                "max_iterations": 20,
                "timeout_seconds": 300,
            },
        }
        task = Task.from_dict(data)
        assert task.difficulty == "hard"
        assert task.tags == ["python", "debug"]
        assert task.prompt == "Fix the bug"
        assert task.workspace_files == {"bug.py": "code here"}
        assert task.scoring.method == "functional"
        assert task.scoring.command == "python test.py"
        assert task.constraints.max_iterations == 20
        assert task.constraints.timeout_seconds == 300


class TestTaskFromYaml:
    def test_load_yaml(self, tmp_path):
        yaml_content = {
            "id": "yaml-001",
            "name": "YAML Test",
            "category": "code",
            "difficulty": "easy",
            "input": {
                "prompt": "Write a hello world",
                "workspace_files": {},
            },
            "scoring": {
                "method": "exact",
                "expected": "hello world",
                "match_mode": "contains",
            },
        }
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml.dump(yaml_content), encoding="utf-8")

        task = Task.from_yaml(yaml_path)
        assert task.id == "yaml-001"
        assert task.scoring.method == "exact"
        assert task.scoring.expected == "hello world"


class TestTaskLoadDirectory:
    def test_load_multiple(self, tmp_path):
        code_dir = tmp_path / "code"
        code_dir.mkdir()
        for i in range(3):
            content = {
                "id": f"task-{i:03d}",
                "name": f"Task {i}",
                "category": "code",
            }
            (code_dir / f"task_{i:03d}.yaml").write_text(
                yaml.dump(content), encoding="utf-8"
            )

        tasks = Task.load_directory(tmp_path)
        assert len(tasks) == 3
        assert tasks[0].id == "task-000"
        assert tasks[2].id == "task-002"
