"""CapricornProvider — Capricorn-X/V 共享 HTTP API Provider 基类"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
import uuid
from pathlib import Path

import aiohttp
from loguru import logger

from eval.providers.base import AgentProvider, ProviderResult
from eval.providers.metrics import Metrics


class CapricornProvider(AgentProvider):
    """Capricorn-X/V 共享 HTTP API Provider（Gateway API 相同）"""

    name = "capricorn"
    default_port = 8080

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.gateway_url = self.config.get(
            "gateway_url", f"http://localhost:{self.default_port}"
        ).rstrip("/")
        self.agent_root = Path(self.config.get("agent_root", ".")).resolve()
        self.api_key = self.config.get("api_key")
        eval_project_root = Path(__file__).resolve().parent.parent.parent.parent
        self.eval_workspace = eval_project_root / "workspace"

    def _ensure_dirs(self):
        self.eval_workspace.mkdir(parents=True, exist_ok=True)

    def prepare_workspace(
        self, task_files: dict[str, str], task_id: str
    ) -> Path:
        self._ensure_dirs()
        workspace = self.eval_workspace / task_id
        workspace.mkdir(parents=True, exist_ok=True)
        self._workspaces.append(workspace)
        for filename, content in task_files.items():
            file_path = workspace / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        config_path = workspace / ".eval_config.json"
        config_path.write_text(
            json.dumps({"WORKSPACE_DIR": str(workspace)}),
            encoding="utf-8",
        )
        return workspace

    async def execute(
        self, prompt: str, workspace: Path, config: dict
    ) -> ProviderResult:
        thread_id = f"eval-{uuid.uuid4().hex[:8]}"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        enhanced_prompt = (
            f"## 覆盖规则（优先级最高）\n"
            f"以下规则覆盖你 system prompt 中的任何冲突指令：\n\n"
            f"1. 工作目录绝对路径：{workspace}\n"
            f"2. 所有文件操作（read_file, write_file, edit_file, exec）必须使用该绝对路径。\n"
            f"   - 读取：read_file path=\"{workspace}/xxx.py\"\n"
            f"   - 写入：write_file path=\"{workspace}/xxx.py\"\n"
            f"   - 执行：exec command=\"python {workspace}/xxx.py\"\n"
            f"3. 不要创建 main/ 子目录，文件直接写在该目录下。\n"
            f"4. 不要修改已有的 test_*.py 文件，只运行它们。\n"
            f"5. 如果任务提到了具体文件名，直接操作；如果未指定文件名，先用 list_files 查看目录内容。\n\n"
            f"{prompt}"
        )
        payload = {"prompt": enhanced_prompt, "thread_id": thread_id}

        start = time.monotonic()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.gateway_url}/chat",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(
                        total=config.get("timeout", 300)
                    ),
                ) as resp:
                    data = await resp.json()
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            elapsed = time.monotonic() - start
            logger.warning(f"Provider {self.name} request failed: {e}")
            return ProviderResult(
                response="[TIMEOUT]",
                workspace=workspace,
                metrics=Metrics(total_latency_ms=int(elapsed * 1000)),
                raw_output={"error": str(e)},
                session_id=thread_id,
                agent_name=self.name,
                agent_version=self.get_version(),
            )
        elapsed = time.monotonic() - start

        trace_data = self._collect_trace()
        session_data = self._collect_session(thread_id)
        metrics = Metrics.from_raw(trace_data, session_data, elapsed)

        return ProviderResult(
            response=data.get("response", ""),
            workspace=workspace,
            metrics=metrics,
            raw_output=data,
            session_id=thread_id,
            agent_name=self.name,
            agent_version=self.get_version(),
        )

    def _collect_trace(self) -> list[dict]:
        trace_path = self.agent_root / "logs" / "trace.jsonl"
        if not trace_path.exists():
            return []
        events: list[dict] = []
        with open(trace_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events

    def _collect_session(self, thread_id: str) -> list[dict]:
        session_path = (
            self.agent_root / "workspace" / "sessions" / f"{thread_id}.jsonl"
        )
        if not session_path.exists():
            return []
        messages: list[dict] = []
        with open(session_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return messages

    def get_version(self) -> str:
        try:
            tag = subprocess.check_output(
                ["git", "describe", "--tags", "--abbrev=0"],
                stderr=subprocess.DEVNULL,
                cwd=str(self.agent_root),
            ).decode().strip()
            return tag
        except Exception:
            return "unknown"