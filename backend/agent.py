from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .generation import AnswerGenerator, OfflineAnswerGenerator
from .planning import TaskPlanner
from .rules import RuleMatch, RuleRetriever
from .tools import OrderTools, ToolResult


ORDER_PATTERN = re.compile(r"(?<![A-Z0-9])OD[A-Z0-9-]{6,}(?![A-Z0-9])", re.IGNORECASE)


class AgentState(TypedDict, total=False):
    question: str
    intent: str
    order_code: str | None
    needs_order: bool
    use_latest_order: bool
    risk: str
    order_result: ToolResult | None
    order_status: str | None
    rule_match: RuleMatch | None
    decision: str
    answer: str
    sources: list[dict[str, str]]
    trace: list[str]
    provider: str
    fallback_reason: str | None
    retrieval: dict[str, Any]
    choices: list[dict[str, str]]
    order_date: str | None
    planner_provider: str
    planner_fallback_reason: str | None


def classify_question(question: str) -> dict[str, Any]:
    text = question.strip().lower()
    order_match = ORDER_PATTERN.search(question)
    if any(phrase in text for phrase in ("别人订单", "他人订单", "绕过验证", "不用验证", "不验证身份")):
        return {"intent": "bypass_identity", "risk": "unauthorized", "needs_order": False, "order_code": order_match.group(0).upper() if order_match else None}
    if any(keyword in text for keyword in ("食品安全", "吃坏", "食物中毒", "严重投诉")):
        return {"intent": "high_risk_complaint", "risk": "high", "needs_order": False, "order_code": order_match.group(0).upper() if order_match else None}
    if any(keyword in text for keyword in ("偷吃", "被吃", "吃了", "当晚餐", "当午餐", "私自食用")):
        intent = "delivery_incident_theft"
    elif any(keyword in text for keyword in ("弄洒", "洒了", "撒了", "漏了", "汤漏", "破损")):
        intent = "delivery_incident_damage"
    elif any(keyword in text for keyword in ("退款", "退钱", "售后", "没收到")):
        intent = "refund"
    elif any(keyword in text for keyword in ("取消", "不要了", "撤销订单")):
        intent = "cancel_order"
    elif any(keyword in text for keyword in ("超时", "没送到", "配送", "多久")):
        intent = "delivery_timeout"
    elif order_match:
        intent = "order_lookup"
    else:
        intent = "unknown"
    needs_order = intent in {"refund", "cancel_order", "delivery_timeout", "order_lookup", "delivery_incident_theft", "delivery_incident_damage"}
    return {
        "intent": intent,
        "risk": "none",
        "needs_order": needs_order,
        "use_latest_order": needs_order and not order_match and any(keyword in text for keyword in ("最新订单", "最近订单", "刚下的订单")),
        "order_code": order_match.group(0).upper() if order_match else None,
    }


class CustomerServiceAgent:
    def __init__(self, order_tools: OrderTools, rule_retriever: RuleRetriever, answer_generator: AnswerGenerator | None = None, task_planner: TaskPlanner | None = None) -> None:
        self.order_tools = order_tools
        self.rule_retriever = rule_retriever
        self.answer_generator = answer_generator or OfflineAnswerGenerator()
        self.task_planner = task_planner
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("classify", self._classify)
        workflow.add_node("query_order", self._query_order)
        workflow.add_node("retrieve_rule", self._retrieve_rule)
        workflow.add_node("validate_evidence", self._validate_evidence)
        workflow.add_node("answer", self._answer)
        workflow.add_node("clarify", self._clarify)
        workflow.add_node("reject", self._reject)
        workflow.add_node("abstain", self._abstain)
        workflow.add_node("handoff", self._handoff)
        workflow.add_edge(START, "classify")
        workflow.add_conditional_edges("classify", self._route_after_classify, {"query_order": "query_order", "retrieve_rule": "retrieve_rule", "clarify": "clarify", "reject": "reject", "handoff": "handoff"})
        workflow.add_conditional_edges("query_order", self._route_after_order, {"retrieve_rule": "retrieve_rule", "clarify": "clarify", "reject": "reject"})
        workflow.add_edge("retrieve_rule", "validate_evidence")
        workflow.add_conditional_edges("validate_evidence", self._route_after_evidence, {"answer": "answer", "abstain": "abstain"})
        for node in ("answer", "clarify", "reject", "abstain", "handoff"):
            workflow.add_edge(node, END)
        return workflow.compile()

    def invoke(self, question: str) -> AgentState:
        initial: AgentState = {"question": question, "trace": [], "sources": []}
        return self.graph.invoke(initial)

    def _classify(self, state: AgentState) -> dict[str, Any]:
        if self.task_planner:
            plan = self.task_planner.plan(state["question"])
            result = {
                "intent": plan.intent,
                "needs_order": plan.needs_order,
                "order_code": plan.order_code,
                "order_date": plan.order_date,
                "risk": plan.risk,
                "planner_provider": plan.provider,
                "planner_fallback_reason": plan.fallback_reason,
            }
        else:
            result = classify_question(state["question"])
        if result["intent"] == "unknown":
            semantic_match = self.rule_retriever.retrieve(state["question"], "unknown", None, enforce_status=False)
            if semantic_match.found and semantic_match.rule and semantic_match.rule.get("order_statuses"):
                result["intent"] = semantic_match.rule["intents"][0]
                result["needs_order"] = True
                result["use_latest_order"] = not result.get("order_code") and any(
                    phrase in state["question"] for phrase in ("最新", "最近", "刚下", "这单", "我的餐")
                )
        return {**result, "trace": state["trace"] + ["classify"]}

    def _route_after_classify(self, state: AgentState) -> str:
        if state["risk"] == "unauthorized":
            return "reject"
        if state["risk"] == "high":
            return "handoff"
        if state["needs_order"]:
            return "query_order"
        return "retrieve_rule"

    def _query_order(self, state: AgentState) -> dict[str, Any]:
        if not state.get("order_code"):
            if state.get("order_date"):
                list_result = self.order_tools.list_my_orders_by_date(state["order_date"], state["question"])
            else:
                list_result = self.order_tools.list_my_today_orders(state["question"])
            if not list_result.ok or not list_result.data:
                result = ToolResult(False, "NO_DATED_ORDERS", "当前账户在指定日期没有可查询的订单。")
            elif len(list_result.data) > 1:
                result = ToolResult(True, "MULTIPLE_DATED_ORDERS", "指定日期有多个订单，需要用户选择。", list_result.data)
            else:
                result = ToolResult(True, "ORDER_FOUND", "已自动定位当前账户今天的订单。", list_result.data[0])
        else:
            result = self.order_tools.get_my_order(state["order_code"] or "", state["question"])
        single_order = result.data if isinstance(result.data, dict) else None
        order_status = single_order.get("order_status") if single_order else None
        order_code = single_order.get("order_code") if single_order else state.get("order_code")
        return {"order_result": result, "order_status": order_status, "order_code": order_code, "trace": state["trace"] + ["query_order"]}

    def _route_after_order(self, state: AgentState) -> str:
        if state["order_result"].code in {"MULTIPLE_DATED_ORDERS", "NO_DATED_ORDERS"}:
            return "clarify"
        return "retrieve_rule" if state["order_result"].ok else "reject"

    def _retrieve_rule(self, state: AgentState) -> dict[str, Any]:
        match = self.rule_retriever.retrieve(state["question"], state["intent"], state.get("order_status"))
        retrieval = {"method": match.retrieval_method, "model": match.model_name, "score": round(match.score, 4)}
        return {"rule_match": match, "retrieval": retrieval, "trace": state["trace"] + ["retrieve_rule"]}

    def _validate_evidence(self, state: AgentState) -> dict[str, Any]:
        match = state["rule_match"]
        decision = "answer" if match and match.found and match.source else "abstain"
        return {"decision": decision, "trace": state["trace"] + ["validate_evidence"]}

    def _route_after_evidence(self, state: AgentState) -> str:
        return state["decision"]

    def _answer(self, state: AgentState) -> dict[str, Any]:
        match = state["rule_match"]
        generated = self.answer_generator.generate(state["question"], state.get("order_status"), match.rule)
        source = {"rule_id": match.source.rule_id, "title": match.source.title, "url": match.source.url, "score": round(match.score, 4)}
        return {"answer": generated.answer, "provider": generated.provider, "fallback_reason": generated.fallback_reason, "sources": [source], "decision": "answer", "trace": state["trace"] + ["answer"]}

    def _clarify(self, state: AgentState) -> dict[str, Any]:
        order_result = state.get("order_result")
        if order_result and order_result.code == "MULTIPLE_DATED_ORDERS":
            choices = [
                {
                    "label": f"{order['order_code']} · {order['order_status']}",
                    "value": order["order_code"],
                    "question": state["question"],
                }
                for order in order_result.data
            ]
            answer = "我查到该日期有多个外卖订单，请选择出现问题的订单："
        else:
            choices = []
            answer = "我没有查到当前账户在该日期的订单，请提供订单号，我会核验后继续处理。"
        return {"answer": answer, "provider": "local-policy", "choices": choices, "decision": "clarify", "trace": state["trace"] + ["clarify"]}

    def _reject(self, state: AgentState) -> dict[str, Any]:
        if state.get("risk") == "unauthorized":
            answer = "我不能绕过身份校验查询或处理其他账户的订单。"
            match = self.rule_retriever.retrieve(state["question"], "bypass_identity", None)
            sources = []
            source_rule_id = None
            if match.found and match.source:
                source_rule_id = match.source.rule_id
                sources = [{"rule_id": match.source.rule_id, "title": match.source.title, "url": match.source.url}]
            self.order_tools.record_event(state["question"], "REJECT_UNAUTHORIZED", source_rule_id)
        else:
            answer = "当前账户下未找到可核验的订单，因此不能提供订单状态或执行售后操作。"
            sources = []
        return {"answer": answer, "provider": "local-policy", "sources": sources, "decision": "reject", "trace": state["trace"] + ["reject"]}

    def _abstain(self, state: AgentState) -> dict[str, Any]:
        return {"answer": "当前客服知识库没有找到足够依据，我不能直接给出结论。", "provider": "local-policy", "decision": "abstain", "trace": state["trace"] + ["abstain"]}

    def _handoff(self, state: AgentState) -> dict[str, Any]:
        self.order_tools.record_event(state["question"], "HANDOFF_HIGH_RISK", None)
        return {"answer": "该问题涉及高风险投诉，需要人工客服进一步核验，我将建议转人工处理。", "provider": "local-policy", "decision": "handoff", "trace": state["trace"] + ["handoff"]}
