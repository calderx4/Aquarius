"""Claude Code CLI Provider"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

from loguru import logger

from eval.providers.base import AgentProvider, ProviderResult
from eval.providers.metrics import Metrics


class ClaudeCodeProvider(AgentProvider):
    name = "claude-code"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.cli_path = self.config.get("cli_path", "claude")
        self.model = self.config.get("model")
        self.max_turns = self.config.get("max_turns", 30)
        self.permission_mode = self.config.get(
            "permission_mode", "bypassPermissions"
        )
        self.system_prompt = self.config.get("system_prompt")

    async def execute(
        self, prompt: str, workspace: Path, config: dict
    ) -> ProviderResult:
        cmd = [
            self.cli_path,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--max-turns",
            str(config.get("max_turns", self.max_turns)),
            "--permission-mode",
            self.permission_mode,
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        if self.system_prompt:
            cmd.extend(["--system-prompt", self.system_prompt])
        cmd.extend(["--allowedTools", "Read,Write,Edit,Bash"])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace),
        )

        timeout = config.get("timeout", 120)
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            return ProviderResult(
                response="[TIMEOUT]",
                workspace=workspace,
                metrics=Metrics(),
                raw_output={"stderr": stderr.decode() if stderr else ""},
                agent_name=self.name,
                agent_version=self.get_version(),
            )

        raw: dict = {}
        response_text = ""
        try:
            raw = json.loads(stdout.decode())
            response_text = raw.get("result", "")
        except json.JSONDecodeError:
            response_text = stdout.decode()

        metrics = self._parse_metrics(raw)
        return ProviderResult(
            response=response_text,
            workspace=workspace,
            metrics=metrics,
            raw_output=raw,
            session_id=raw.get("session_id", ""),
            agent_name=self.name,
            agent_version=self.get_version(),
        )

    def _parse_metrics(self, raw: dict) -> Metrics:
        m = Metrics()
        usage = raw.get("usage", {})
        m.total_input_tokens = usage.get("input_tokens", 0)
        m.total_output_tokens = usage.get("output_tokens", 0)
        m.cache_read_tokens = usage.get("cache_read_input_tokens", 0)
        m.cache_creation_tokens = usage.get("cache_creation_input_tokens", 0)
        m.total_tokens = m.total_input_tokens + m.total_output_tokens
        m.cost_usd = raw.get("total_cost_usd", 0)
        m.total_latency_ms = raw.get("duration_ms", 0)
        m.iterations = raw.get("num_turns", 0)
        m.source = "cli_json"
        return m

    def get_version(self) -> str:
        try:
            r = subprocess.run(
                [self.cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return r.stdout.strip()
        except Exception:
            return "unknown"
