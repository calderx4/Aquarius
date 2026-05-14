# Aquarius

Agent 不可知的评估框架。测量任务完成度、工具效率和 Token 成本，适用于任何 AI 编码 Agent。

## 快速开始

```bash
# 安装
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 验证
python -m pytest tests/ -v

# 运行评估
python -m eval run --provider capricorn-x --save-baseline
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `run --provider <name>` | 运行评估 |
| `compare <file1> <file2>` | 对比结果 |
| `list-providers` | 列出可用 Agent |
| `list-scorers` | 列出可用评分器 |

选项：`--save-baseline` `--markdown` `--timeout <秒>` `--max-turns <次数>`

## 支持的 Agent

| Provider | 类型 |
|----------|------|
| `capricorn-x` | 自托管 HTTP API |
| `capricorn-v` | 自托管 HTTP API |
| `claude-code` | 外部 CLI（`claude -p`） |
| `hermes` | 外部 CLI（`hermes chat -q`） |

## 评分器

| Scorer | 说明 |
|--------|------|
| `functional` | 执行命令验证 |
| `exact` | 字符串匹配 |
| `keyword_check` | 关键词存在性 |
| `composite` | 多评分器组合 |

## 目录结构

```
eval/
├── eval/                  # Python 包
│   ├── __main__.py       # CLI 入口
│   ├── task.py            # 任务定义
│   ├── runner.py          # 编排器
│   ├── report.py          # 报告
│   ├── compare.py         # 对比
│   ├── providers/         # Agent 适配
│   │   ├── base.py
│   │   ├── metrics.py
│   │   ├── self_hosted/   # Capricorn-X/V
│   │   └── external/      # Claude Code, Hermes
│   ├── scorer/            # 评分器
│   │   ├── base.py
│   │   ├── functional.py
│   │   ├── exact.py
│   │   ├── keyword_check.py
│   │   └── composite.py
│   └── tasks/             # 任务定义
│       ├── code/          # 8 个代码任务
│       └── general/       # 2 个通用任务
├── baselines/             # 测评结果（gitignore）
├── tests/                 # 测试
└── configs.json.example   # 配置模板
```

## 添加新 Provider

```python
# eval/providers/external/my_agent.py
from eval.providers.base import AgentProvider, ProviderResult

class MyAgentProvider(AgentProvider):
    name = "my-agent"

    async def execute(self, prompt, workspace, config):
        # 调用你的 Agent
        ...
```

在 `eval/providers/__init__.py` 注册。