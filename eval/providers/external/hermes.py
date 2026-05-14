"""Hermes CLI Provider — hermes chat -q (non-interactive)"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path

from eval.providers.base import AgentProvider, ProviderResult
from eval.providers.metrics import Metrics

_SESSION_ID_RE = re.compile(r"^session_id:\s*(\S+)", re.MULTILINE)


class HermesProvider(AgentProvider):
    name = "hermes"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.cli_path = self.config.get("cli_path", "hermes")
        self.model = self.config.get("model")
        self.max_turns = self.config.get("max_turns", 50)

    async def execute(
        self, prompt: str, workspace: Path, config: dict
    ) -> ProviderResult:
        cmd = [
            self.cli_path,
            "chat",
            "-q", prompt,
            "-Q",
            "--yolo",
            "--accept-hooks",
            "--max-turns", str(config.get("max_turns", self.max_turns)),
        ]
        if self.model:
            cmd.extend(["-m", self.model])

        start = asyncio.get_event_loop().time()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace),
        )

        timeout = config.get("timeout", 300)
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
                raw_output={"stderr": stderr.decode(errors="replace") if stderr else ""},
                agent_name=self.name,
                agent_version=self.get_version(),
            )
        elapsed = asyncio.get_event_loop().time() - start

        combined = stdout.decode(errors="replace")

        session_id = ""
        match = _SESSION_ID_RE.search(combined)
        if match:
            session_id = match.group(1)

        response_text = _SESSION_ID_RE.sub("", combined).strip()

        raw = {"stdout": combined, "stderr": stderr.decode(errors="replace")}

        session_data = self._export_session(session_id)
        if session_data:
            raw["session"] = session_data

        metrics = self._parse_metrics(session_data, elapsed)
        return ProviderResult(
            response=response_text,
            workspace=workspace,
            metrics=metrics,
            raw_output=raw,
            session_id=session_id,
            agent_name=self.name,
            agent_version=self.get_version(),
        )

    def _export_session(self, session_id: str) -> dict | None:
        if not session_id:
            return None
        try:
            r = subprocess.run(
                [self.cli_path, "sessions", "export", "--session-id", session_id, "-"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0 and r.stdout.strip():
                return json.loads(r.stdout)
        except Exception:
            pass
        return None

    def _parse_metrics(self, session_data: dict | None, elapsed: float) -> Metrics:
        m = Metrics()
        m.total_latency_ms = int(elapsed * 1000)
        m.source = "cli_text"
        if not session_data:
            return m

        m.total_input_tokens = session_data.get("input_tokens", 0)
        m.total_output_tokens = session_data.get("output_tokens", 0)
        m.cache_read_tokens = session_data.get("cache_read_tokens", 0)
        m.cache_creation_tokens = session_data.get("cache_write_tokens", 0)
        m.total_tokens = m.total_input_tokens + m.total_output_tokens
        m.tool_call_count = session_data.get("tool_call_count", 0)
        m.message_count = session_data.get("message_count", 0)
        m.cost_usd = session_data.get("estimated_cost_usd", 0) or 0
        m.source = "session_export"

        messages = session_data.get("messages", [])
        for msg in messages:
            if msg.get("role") == "assistant":
                m.iterations += 1
                tc = msg.get("tool_calls") or []
                if tc:
                    m.tool_calls_per_iteration.append(len(tc))
                for t in tc:
                    name = t.get("name", "")
                    if name:
                        m.tool_names_used.append(name)
                    m.tool_success_count += 1
            elif msg.get("role") == "tool":
                content = str(msg.get("content", ""))
                if "error" in content[:30].lower():
                    m.tool_error_count += 1

        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                m.final_response_length = len(str(msg["content"]))
                break

        return m

    def get_version(self) -> str:
        try:
            r = subprocess.run(
                [self.cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            first_line = r.stdout.strip().split("\n")[0]
            return first_line
        except Exception:
            return "unknown"
