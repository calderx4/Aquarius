"""Report — JSON + Markdown 报告生成"""

from __future__ import annotations

import json

from eval.runner import EvalRun


def generate_json(eval_run: EvalRun) -> str:
    return json.dumps(eval_run.to_dict(), indent=2, ensure_ascii=False)


def generate_markdown(eval_run: EvalRun) -> str:
    lines = [
        f"# Eval Report: {eval_run.provider_name}",
        f"**Version:** {eval_run.provider_version}",
        f"**Date:** {eval_run.timestamp}",
        "",
        "## Summary",
        f"- Tasks: {eval_run.total_tasks}",
        f"- Passed: {eval_run.pass_count}/{eval_run.total_tasks}",
        f"- Average Score: {eval_run.average_score:.1%}",
        "",
    ]

    by_category = eval_run.by_category
    if by_category:
        lines.append("## By Category")
        for cat, results in sorted(by_category.items()):
            avg = sum(r.score.score for r in results) / len(results)
            passed = sum(1 for r in results if r.score.passed)
            lines.append(
                f"- **{cat}**: {passed}/{len(results)} passed, "
                f"avg score {avg:.1%}"
            )
        lines.append("")

    lines.extend([
        "## Results",
        "",
        "| Task | Category | Difficulty | Score | Passed | Detail |",
        "|------|----------|------------|-------|--------|--------|",
    ])
    for r in eval_run.results:
        status = "YES" if r.score.passed else "NO"
        lines.append(
            f"| {r.task.id} | {r.task.category} | {r.task.difficulty} "
            f"| {r.score.score:.1%} | {status} | {r.score.detail} |"
        )

    has_metrics = any(
        r.provider_result.metrics.available_metrics
        for r in eval_run.results
    )
    if has_metrics:
        lines.extend(["", "## Metrics", ""])
        lines.append(
            "| Task | Tokens | Latency (ms) | Tool Calls | Iterations |"
        )
        lines.append(
            "|------|--------|-------------|------------|------------|"
        )
        for r in eval_run.results:
            m = r.provider_result.metrics
            lines.append(
                f"| {r.task.id} | {m.total_tokens} "
                f"| {m.total_latency_ms} | {m.tool_call_count} "
                f"| {m.iterations} |"
            )

    return "\n".join(lines)