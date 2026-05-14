"""Provider registry — name → provider class"""

from __future__ import annotations

from eval.providers.base import AgentProvider
from eval.providers.external.claude_code import ClaudeCodeProvider
from eval.providers.external.hermes import HermesProvider
from eval.providers.self_hosted.capricorn_v import CapricornVProvider
from eval.providers.self_hosted.capricorn_x import CapricornXProvider

PROVIDERS: dict[str, type[AgentProvider]] = {
    "capricorn-x": CapricornXProvider,
    "capricorn-v": CapricornVProvider,
    "claude-code": ClaudeCodeProvider,
    "hermes": HermesProvider,
}


def get_provider(name: str, config: dict | None = None) -> AgentProvider:
    cls = PROVIDERS.get(name)
    if not cls:
        raise ValueError(
            f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}"
        )
    return cls(config)


def list_providers() -> list[str]:
    return list(PROVIDERS.keys())
