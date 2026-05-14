"""AgentProvider — Agent 适配器基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from typing import Any

from eval.providers.metrics import Metrics


@dataclass
class ProviderResult:
    """Provider 统一返回结构"""

    response: str
    workspace: Path
    metrics: Metrics
    raw_output: dict[str, Any]
    session_id: str = ""
    agent_name: str = ""
    agent_version: str = ""


class AgentProvider(ABC):
    """Agent 适配器基类"""

    name: str = "unknown"

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._workspaces: list[Path] = []

    def prepare_workspace(
        self, task_files: dict[str, str], task_id: str
    ) -> Path:
        workspace = Path(mkdtemp(prefix=f"eval_{task_id}_"))
        self._workspaces.append(workspace)
        for filename, content in task_files.items():
            file_path = workspace / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        return workspace

    @abstractmethod
    async def execute(
        self, prompt: str, workspace: Path, config: dict
    ) -> ProviderResult:
        ...

    def cleanup(self):
        for ws in self._workspaces:
            if ws.exists():
                rmtree(ws, ignore_errors=True)
        self._workspaces.clear()

    @abstractmethod
    def get_version(self) -> str:
        ...

    