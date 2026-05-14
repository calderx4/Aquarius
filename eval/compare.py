"""Compare — 纵向(版本)和横向(Agent)对比"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from eval.runner import EvalRun


@dataclass
class ComparisonReport:
    runs: list[EvalRun]
    task_ids: list[str] = field(default_factory=list)
    deltas: dict[str, list[float]] = field(default_factory=dict)
    regressions: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)

    @property
    def comparison_type(self) -> str:
        if len(self.runs) < 2:
            return "single"
        names = {r.provider_name for r in self.runs}
        if len(names) == 1:
            return "version"
        return "cross-agent"


def compare_runs(runs: list[EvalRun]) -> ComparisonReport:
    if not runs:
        return ComparisonReport(runs=[])

    all_task_ids: list[str] = []
    seen: set[str] = set()
    for run in runs:
        for r in run.results:
            if r.task.id not in seen:
                all_task_ids.append(r.task.id)
                seen.add(r.task.id)

    deltas: dict[str, list[float]] = {}
    regressions: list[str] = []
    improvements: list[str] = []

    if len(runs) >= 2:
        scores_a = {r.task.id: r.score.score for r in runs[0].results}
        scores_b = {r.task.id: r.score.score for r in runs[1].results}

        for tid in all_task_ids:
            sa = scores_a.get(tid)
            sb = scores_b.get(tid)
            if sa is not None and sb is not None:
                delta = sb - sa
                deltas[tid] = [sa, sb, delta]
                if delta < -0.01:
                    regressions.append(tid)
                elif delta > 0.01:
                    improvements.append(tid)

    return ComparisonReport(
        runs=runs,
        task_ids=all_task_ids,
        deltas=deltas,
        regressions=regressions,
        improvements=improvements,
    )


def generate_comparison_markdown(report: ComparisonReport) -> str:
    lines = [
        "# Comparison Report",
        f"**Type:** {report.comparison_type}",
        f"**Runs:** {len(report.runs)}",
        "",
    ]

    for i, run in enumerate(report.runs):
        lines.append(
            f"- Run {i + 1}: **{run.provider_name}** "
            f"(v{run.provider_version}) — "
            f"avg {run.average_score:.1%}, "
            f"{run.pass_count}/{run.total_tasks} passed"
        )

    if len(report.runs) >= 2:
        lines.extend(["", "## Score Table", ""])
        header = "| Task |"
        sep = "|------|"
        for run in report.runs:
            label = run.provider_name
            header += f" {label} |"
            sep += "--------|"
        header += " Delta |"
        sep += "-------|"
        lines.extend([header, sep])

        for tid in report.task_ids:
            row = f"| {tid} |"
            for run in report.runs:
                score = next(
                    (r.score.score for r in run.results if r.task.id == tid),
                    None,
                )
                row += f" {score:.1%} |" if score is not None else " — |"
            if tid in report.deltas:
                delta = report.deltas[tid][-1]
                sign = "+" if delta >= 0 else ""
                row += f" {sign}{delta:.1%} |"
            else:
                row += " — |"
            lines.append(row)

        lines.extend([
            "",
            f"**Improvements:** {len(report.improvements)}",
            f"**Regressions:** {len(report.regressions)}",
        ])

        if report.regressions:
            lines.append(f"- Regressed tasks: {', '.join(report.regressions)}")
        if report.improvements:
            lines.append(f"- Improved tasks: {', '.join(report.improvements)}")

    return "\n".join(lines)


def load_run(path: Path) -> EvalRun:
    data = json.loads(path.read_text(encoding="utf-8"))
    return EvalRun.from_dict(data)
