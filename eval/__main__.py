"""CLI: python -m eval run --provider X [--save-baseline] [--markdown]"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="eval",
        description="Agent-agnostic evaluation framework",
    )
    sub = parser.add_subparsers(dest="command")

    # run
    run_parser = sub.add_parser("run", help="Run evaluation against an agent")
    run_parser.add_argument(
        "--provider", required=True, help="Agent provider name"
    )
    run_parser.add_argument(
        "--task-dir",
        default=None,
        help="Task YAML directory (default: built-in tasks)",
    )
    run_parser.add_argument(
        "--config", default=None, help="Provider config JSON file"
    )
    run_parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Save result to baselines/{provider}/",
    )
    run_parser.add_argument(
        "--output", default=None, help="Output JSON file path"
    )
    run_parser.add_argument(
        "--markdown", action="store_true", help="Print Markdown report"
    )
    run_parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Override per-task timeout (seconds). Default: from task YAML (120s)",
    )
    run_parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="Override max agent iterations. Default: from task YAML (15)",
    )

    # compare
    cmp_parser = sub.add_parser("compare", help="Compare eval results")
    cmp_parser.add_argument(
        "files", nargs="+", help="JSON result files to compare"
    )
    cmp_parser.add_argument(
        "--markdown", action="store_true", help="Print Markdown comparison"
    )

    # list
    sub.add_parser("list-providers", help="List available providers")
    sub.add_parser("list-scorers", help="List available scorers")

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(_run(args))
    elif args.command == "compare":
        _compare(args)
    elif args.command == "list-providers":
        _list_providers()
    elif args.command == "list-scorers":
        _list_scorers()
    else:
        parser.print_help()


async def _run(args):
    from eval.providers import get_provider, list_providers
    from eval.report import generate_json, generate_markdown
    from eval.runner import EvalRunner
    from eval.task import Task

    provider_config = {}
    # 优先使用命令行指定配置，其次查找 configs.json
    if args.config:
        config_path = Path(args.config)
        provider_config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        configs_file = Path(__file__).parent.parent / "configs.json"
        if configs_file.exists():
            all_configs = json.loads(configs_file.read_text(encoding="utf-8"))
            if args.provider in all_configs:
                provider_config = all_configs[args.provider]
                print(f"Using config from configs.json for: {args.provider}")

    try:
        provider = get_provider(args.provider, provider_config)
    except ValueError as e:
        print(f"Error: {e}")
        print(f"Available providers: {', '.join(list_providers())}")
        sys.exit(1)

    task_dir = (
        Path(args.task_dir)
        if args.task_dir
        else Path(__file__).parent / "tasks"
    )
    if not task_dir.exists():
        print(f"Error: task directory not found: {task_dir}")
        sys.exit(1)

    tasks = Task.load_directory(task_dir)
    if not tasks:
        print(f"Error: no tasks found in {task_dir}")
        sys.exit(1)

    print(f"Loaded {len(tasks)} tasks from {task_dir}")
    print(f"Provider: {args.provider}")
    if args.timeout:
        print(f"Timeout override: {args.timeout}s")
        for t in tasks:
            t.constraints.timeout_seconds = args.timeout
    if args.max_turns:
        print(f"Max turns override: {args.max_turns}")
        for t in tasks:
            t.constraints.max_iterations = args.max_turns
    print()

    runner = EvalRunner(provider, provider_config)
    if args.save_baseline:
        project_root = Path(__file__).resolve().parent.parent
        baseline_dir = project_root / "baselines" / args.provider
        baseline_dir.mkdir(parents=True, exist_ok=True)
        latest_path = baseline_dir / "latest.json"

        def on_task_complete(run):
            latest_path.write_text(generate_json(run), encoding="utf-8")
            print(
                f"  [进度保存] {run.pass_count}/{run.total_tasks} 通过 "
                f"(avg {run.average_score:.1%})"
            )

        runner = EvalRunner(provider, provider_config, on_task_complete=on_task_complete)

    result = await runner.run_all(tasks)

    json_output = generate_json(result)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_output, encoding="utf-8")
        print(f"\nJSON saved to: {out_path}")

    if args.save_baseline:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        baseline_path = baseline_dir / f"{ts}.json"
        baseline_path.write_text(json_output, encoding="utf-8")
        latest_path.write_text(json_output, encoding="utf-8")
        md_path = baseline_dir / f"{ts}.md"
        md_path.write_text(generate_markdown(result), encoding="utf-8")
        print(f"Baseline saved to: {baseline_path}")
        print(f"Markdown saved to: {md_path}")

    if args.markdown:
        print("\n" + generate_markdown(result))

    print(f"\nSummary: {result.pass_count}/{result.total_tasks} passed, "
          f"avg score {result.average_score:.1%}")

    provider.cleanup()


def _compare(args):
    from eval.compare import (
        compare_runs,
        generate_comparison_markdown,
        load_run,
    )

    runs = []
    for f in args.files:
        path = Path(f)
        if not path.exists():
            print(f"Error: file not found: {f}")
            sys.exit(1)
        runs.append(load_run(path))

    report = compare_runs(runs)

    if args.markdown:
        print(generate_comparison_markdown(report))


def _list_providers():
    from eval.providers import list_providers

    print("Available providers:")
    for name in list_providers():
        print(f"  - {name}")


def _list_scorers():
    from eval.scorer import list_scorers

    print("Available scorers:")
    for name in list_scorers():
        print(f"  - {name}")


if __name__ == "__main__":
    main()
