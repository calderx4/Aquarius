"""FunctionalScorer — 执行命令验证结果"""

from __future__ import annotations

import asyncio
from pathlib import Path

from eval.scorer.base import BaseScorer, ScoreResult
from eval.task import ScoringConfig


class FunctionalScorer(BaseScorer):
    async def score(
        self,
        response: str,
        workspace: Path,
        scoring_config: ScoringConfig,
    ) -> ScoreResult:
        if not scoring_config.command:
            return ScoreResult(
                passed=False,
                score=0.0,
                method="functional",
                detail="no command configured",
            )

        command = scoring_config.command.replace("{{workspace}}", str(workspace))
        timeout = getattr(scoring_config, 'command_timeout', 30)

        try:
            proc = await asyncio.create_subprocess_exec(
                "sh",
                "-c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            return ScoreResult(
                passed=False,
                score=0.0,
                method="functional",
                detail=f"TIMEOUT after {timeout}s",
            )

        combined = stdout.decode(errors="replace") + stderr.decode(errors="replace")

        if proc.returncode != 0:
            return ScoreResult(
                passed=False,
                score=0.0,
                method="functional",
                detail=f"exit code {proc.returncode}",
                raw_output=combined[:2000],
            )

        if scoring_config.pass_pattern:
            pattern = scoring_config.pass_pattern
            text = combined
            if not scoring_config.case_sensitive:
                pattern = pattern.lower()
                text = text.lower()
            passed = pattern in text
            detail = (
                "pass_pattern found"
                if passed
                else f"pass_pattern '{scoring_config.pass_pattern}' not found"
            )
        else:
            passed = proc.returncode == 0
            detail = "command succeeded (exit 0)"

        return ScoreResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            method="functional",
            detail=detail,
            raw_output=combined[:2000],
        )
