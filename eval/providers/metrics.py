"""Metrics — 执行指标数据类，所有字段可选"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Metrics:
    """执行指标 — 所有字段可选，不同 Provider 填充不同"""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    iterations: int = 0
    max_iterations_hit: bool = False
    tool_call_count: int = 0
    tool_calls_per_iteration: list[int] = field(default_factory=list)
    tool_names_used: list[str] = field(default_factory=list)
    tool_success_count: int = 0
    tool_timeout_count: int = 0
    tool_error_count: int = 0
    total_latency_ms: int = 0
    round_latencies_ms: list[int] = field(default_factory=list)
    message_count: int = 0
    final_response_length: int = 0
    source: str = ""

    @property
    def tool_success_rate(self) -> float:
        if self.tool_call_count == 0:
            return 1.0
        return self.tool_success_count / self.tool_call_count

    @property
    def available_metrics(self) -> list[str]:
        filled: list[str] = []
        if self.total_tokens > 0:
            filled.append("tokens")
        if self.iterations > 0:
            filled.append("iterations")
        if self.tool_call_count > 0:
            filled.append("tool_calls")
        if self.total_latency_ms > 0:
            filled.append("latency")
        if self.cost_usd > 0:
            filled.append("cost")
        return filled

    @classmethod
    def from_raw(
        cls,
        trace: list[dict],
        session: list[dict],
        elapsed_seconds: float = 0,
    ) -> Metrics:
        m = cls()
        m.total_latency_ms = int(elapsed_seconds * 1000)
        m.message_count = len(session)

        # Parse per-thread session data (accurate, not global)
        if session:
            m.source = "session"
            for msg in session:
                role = msg.get("role")
                if role == "assistant":
                    m.iterations += 1
                    calls = msg.get("tool_calls") or []
                    call_count = len(calls)
                    if call_count > 0:
                        m.tool_calls_per_iteration.append(call_count)
                    m.tool_call_count += call_count
                    for tc in calls:
                        name = tc.get("name", "")
                        if name:
                            m.tool_names_used.append(name)
                        m.tool_success_count += 1
                elif role == "tool":
                    content = msg.get("content", "")
                    if content.startswith("[ERROR]") or "error" in content[:20].lower():
                        m.tool_error_count += 1

            for msg in reversed(session):
                if msg.get("role") == "assistant" and msg.get("content"):
                    m.final_response_length = len(msg["content"])
                    break
        elif trace:
            # Fallback: global trace (may include other sessions)
            m.source = "trace"
            for event in trace:
                etype = event.get("type")
                if etype == "round_start":
                    m.iterations = max(m.iterations, event.get("round", 0))
                elif etype == "round_end":
                    m.round_latencies_ms.append(event.get("latency_ms", 0))
                    tc = event.get("tool_calls", 0)
                    if tc > 0:
                        m.tool_calls_per_iteration.append(tc)
                elif etype == "tool_call":
                    m.tool_call_count += 1
                    m.tool_names_used.append(event.get("tool", ""))
                    status = event.get("status", "ok")
                    if status == "ok":
                        m.tool_success_count += 1
                    elif status == "timeout":
                        m.tool_timeout_count += 1
                    elif status == "error":
                        m.tool_error_count += 1

        return m

    def to_dict(self) -> dict:
        return asdict(self)
