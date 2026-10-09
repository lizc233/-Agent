from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from statistics import mean
from time import perf_counter, sleep
from typing import Any

from backend.agent import CustomerServiceAgent
from backend.config import PROJECT_ROOT, load_settings
from backend.rules import RuleRetriever, load_rules
from backend.supervisor import Supervisor
from backend.tools import ToolResult


class EvaluationOrderTools:
    def __init__(self) -> None:
        self.orders = {"OD202610010001": "DELIVERING", "OD202610010002": "COMPLETED"}
        self.order_calls = 0

    def get_my_order(self, order_code: str, question: str) -> ToolResult:
        self.order_calls += 1
        status = self.orders.get(order_code)
        return ToolResult(True, "ORDER_FOUND", "found", {"order_code": order_code, "order_status": status}) if status else ToolResult(False, "ORDER_NOT_AVAILABLE", "not found")

    def list_my_today_orders(self, question: str) -> ToolResult:
        self.order_calls += 1
        return ToolResult(True, "NO_TODAY_ORDERS", "none", [])

    def list_my_orders_by_date(self, order_date: str, question: str) -> ToolResult:
        self.order_calls += 1
        return ToolResult(True, "NO_DATED_ORDERS", "none", [])

    def record_event(self, question: str, action: str, source_rule_id: str | None = None) -> None:
        return None


@dataclass(frozen=True)
class EvaluationSummary:
    cases: int
    decision_accuracy: float
    source_accuracy: float
    trustworthy_rejection_accuracy: float
    order_tool_routing_accuracy: float
    professional_agent_success_rate: float
    average_latency_ms: float
    sequential_benchmark_ms: float
    parallel_benchmark_ms: float
    parallel_speedup: float


def benchmark_parallelism() -> tuple[float, float]:
    def task() -> str:
        sleep(0.05)
        return "ok"

    started = perf_counter()
    for _ in range(4):
        task()
    sequential_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    Supervisor(max_workers=4).dispatch({f"Agent{index}": task for index in range(4)})
    parallel_ms = (perf_counter() - started) * 1000
    return sequential_ms, parallel_ms


def evaluate() -> tuple[EvaluationSummary, list[dict[str, Any]]]:
    cases = json.loads((PROJECT_ROOT / "data" / "evaluation" / "customer_service_eval.json").read_text(encoding="utf-8"))
    retriever = RuleRetriever(load_rules(load_settings(require_database=False)))
    details = []
    decisions = sources = rejections = routes = successful_runs = total_runs = 0
    latencies = []
    rejection_cases = 0
    for case in cases:
        tools = EvaluationOrderTools()
        agent = CustomerServiceAgent(tools, retriever)
        started = perf_counter()
        result = agent.invoke(case["question"])
        latencies.append((perf_counter() - started) * 1000)
        actual_rule = result.get("sources", [{}])[0].get("rule_id") if result.get("sources") else None
        decision_ok = result.get("decision") == case["expected_decision"]
        source_ok = actual_rule == case["expected_rule"]
        route_ok = bool(tools.order_calls) == case["expected_order_tool"]
        decisions += decision_ok
        sources += source_ok
        routes += route_ok
        if case["expected_decision"] in {"reject", "abstain", "handoff"}:
            rejection_cases += 1
            rejections += decision_ok
        runs = result.get("agent_runs", [])
        successful_runs += sum(bool(run.get("ok")) for run in runs)
        total_runs += len(runs)
        details.append({"question": case["question"], "decision": result.get("decision"), "rule_id": actual_rule, "decision_ok": decision_ok, "source_ok": source_ok, "route_ok": route_ok, "latency_ms": round(latencies[-1], 2)})
    sequential_ms, parallel_ms = benchmark_parallelism()
    summary = EvaluationSummary(
        cases=len(cases),
        decision_accuracy=round(decisions / len(cases), 4),
        source_accuracy=round(sources / len(cases), 4),
        trustworthy_rejection_accuracy=round(rejections / rejection_cases, 4),
        order_tool_routing_accuracy=round(routes / len(cases), 4),
        professional_agent_success_rate=round(successful_runs / total_runs, 4) if total_runs else 1.0,
        average_latency_ms=round(mean(latencies), 2),
        sequential_benchmark_ms=round(sequential_ms, 2),
        parallel_benchmark_ms=round(parallel_ms, 2),
        parallel_speedup=round(sequential_ms / parallel_ms, 2),
    )
    return summary, details


if __name__ == "__main__":
    summary, details = evaluate()
    print(json.dumps({"summary": asdict(summary), "details": details}, ensure_ascii=False, indent=2))
