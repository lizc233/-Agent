from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .generation import AnswerGenerator, OfflineAnswerGenerator
from .case_tools import CaseResult, CaseTools
from .evidence import EvidenceReviewer
from .planning import TaskPlanner
from .rules import RuleMatch, RuleRetriever
from .skill_registry import SkillRegistry
from .supervisor import AgentRun, Supervisor
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
    selected_skill: str | None
    agent_runs: list[dict[str, Any]]
    memory_hits: list[Any]
    evidence_review: dict[str, Any]
    case_result: CaseResult | None
    user_confirmed_actual_state: bool
    session_context: dict[str, Any]


def classify_question(question: str) -> dict[str, Any]:
    text = question.strip().lower()
    order_match = ORDER_PATTERN.search(question)
    has_issue_detail = any(keyword in text for keyword in ("异物", "头发", "虫子", "塑料", "金属碎屑", "玻璃", "弄洒", "洒了", "破损", "退款", "少餐", "错餐", "超时"))
    if any(phrase in text for phrase in ("确认实际已收到餐品", "确认实际情况", "按实际情况处理")) and not has_issue_detail:
        return {
            "intent": "issue_type_clarify",
            "risk": "none",
            "needs_order": False,
            "order_code": order_match.group(0).upper() if order_match else None,
            "user_confirmed_actual_state": True,
        }
    if any(phrase in text for phrase in ("别人订单", "他人订单", "绕过验证", "不用验证", "不验证身份")):
        return {"intent": "bypass_identity", "risk": "unauthorized", "needs_order": False, "order_code": order_match.group(0).upper() if order_match else None}
    if any(keyword in text for keyword in ("食品安全", "吃坏", "食物中毒", "严重投诉")):
        return {"intent": "high_risk_complaint", "risk": "high", "needs_order": False, "order_code": order_match.group(0).upper() if order_match else None}
    if any(keyword in text for keyword in ("异物", "头发", "虫子", "塑料", "金属碎屑", "玻璃")):
        intent = "food_foreign_object"
    elif any(keyword in text for keyword in ("偷吃", "被吃", "吃了", "当晚餐", "当午餐", "私自食用")):
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
    needs_order = intent in {"refund", "cancel_order", "delivery_timeout", "order_lookup", "delivery_incident_theft", "delivery_incident_damage", "food_foreign_object", "food_quality", "food_safety"}
    confirmed = any(phrase in text for phrase in ("我确认", "确认实际", "确实已经收到", "以我的实际情况", "按实际情况处理", "已收到餐品"))
    return {
        "intent": intent,
        "risk": "none",
        "needs_order": needs_order,
        "use_latest_order": needs_order and not order_match and any(keyword in text for keyword in ("最新订单", "最近订单", "刚下的订单")),
        "order_code": order_match.group(0).upper() if order_match else None,
        "user_confirmed_actual_state": confirmed,
    }


class CustomerServiceAgent:
    def __init__(self, order_tools: OrderTools, rule_retriever: RuleRetriever, answer_generator: AnswerGenerator | None = None, task_planner: TaskPlanner | None = None, memory: Any | None = None, memory_session_id: int | None = None, skill_registry: SkillRegistry | None = None, supervisor: Supervisor | None = None, evidence_reviewer: EvidenceReviewer | None = None, case_tools: CaseTools | None = None) -> None:
        self.order_tools = order_tools
        self.rule_retriever = rule_retriever
        self.answer_generator = answer_generator or OfflineAnswerGenerator()
        self.task_planner = task_planner
        self.memory = memory
        self.memory_session_id = memory_session_id
        self.skill_registry = skill_registry
        self.supervisor = supervisor or Supervisor()
        self.evidence_reviewer = evidence_reviewer or EvidenceReviewer()
        self.case_tools = case_tools
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("classify", self._classify)
        workflow.add_node("supervise", self._supervise)
        workflow.add_node("validate_evidence", self._validate_evidence)
        workflow.add_node("act_case", self._act_case)
        workflow.add_node("answer", self._answer)
        workflow.add_node("clarify", self._clarify)
        workflow.add_node("reject", self._reject)
        workflow.add_node("abstain", self._abstain)
        workflow.add_node("handoff", self._handoff)
        workflow.add_edge(START, "classify")
        workflow.add_conditional_edges("classify", self._route_after_classify, {"supervise": "supervise", "clarify": "clarify", "reject": "reject", "handoff": "handoff"})
        workflow.add_conditional_edges("supervise", self._route_after_supervise, {"validate_evidence": "validate_evidence", "clarify": "clarify", "reject": "reject", "handoff": "handoff"})
        workflow.add_conditional_edges("validate_evidence", self._route_after_evidence, {"answer": "answer", "act_case": "act_case", "clarify": "clarify", "abstain": "abstain", "reject": "reject", "handoff": "handoff"})
        workflow.add_edge("act_case", "answer")
        for node in ("answer", "clarify", "reject", "abstain", "handoff"):
            workflow.add_edge(node, END)
        return workflow.compile()

    def invoke(self, question: str) -> AgentState:
        context = {}
        if self.memory is not None and self.memory_session_id is not None and hasattr(self.memory, "get_context"):
            context = self.memory.get_context(self.memory_session_id)
            if hasattr(self.memory, "recent_turns"):
                context["recent_turns"] = self.memory.recent_turns(self.memory_session_id, 5)
        model_context = {
            "current_order_code": context.get("current_order_code"),
            "current_order_status": context.get("current_order_status"),
            "reference_issue_type": context.get("current_issue_type"),
            "waiting_for": context.get("waiting_for"),
            "pending_question": context.get("pending_question"),
            "last_confirmed_fact": context.get("last_confirmed_fact"),
            "recent_turns": [
                {key: str(value) if value is not None else None for key, value in turn.items()}
                for turn in context.get("recent_turns", [])
            ],
        }
        if self.task_planner and hasattr(self.task_planner, "set_context"):
            self.task_planner.set_context(model_context)
        if hasattr(self.answer_generator, "set_context"):
            self.answer_generator.set_context(model_context)
        initial: AgentState = {"question": question, "trace": [], "sources": [], "session_context": context}
        result = self.graph.invoke(initial)
        self._remember_result(result)
        return result

    def _remember_result(self, result: AgentState) -> None:
        if self.memory is None or self.memory_session_id is None:
            return
        question = str(result.get("question", "")).strip()
        answer = str(result.get("answer", "")).strip()
        summary = f"用户问题：{question}\n正式回复：{answer}"[:980]
        pending_information = "需要用户选择或补充订单信息" if result.get("decision") == "clarify" else None
        try:
            self.memory.remember(
                self.memory_session_id,
                summary,
                order_code=result.get("order_code"),
                issue_type=result.get("intent"),
                pending_information=pending_information,
            )
        except Exception as error:
            result.setdefault("agent_runs", []).append({
                "agent": "MemoryWriter",
                "ok": False,
                "duration_ms": 0.0,
                "thread_name": "main-agent",
                "error": str(error),
            })

    def _classify(self, state: AgentState) -> dict[str, Any]:
        local_classification = classify_question(state["question"])
        if local_classification["intent"] == "issue_type_clarify":
            result = local_classification
            result["planner_provider"] = "local-confirmation-router"
            result["planner_fallback_reason"] = None
        elif self.task_planner:
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
            result["user_confirmed_actual_state"] = classify_question(state["question"])["user_confirmed_actual_state"]
        else:
            result = classify_question(state["question"])
        if not result.get("order_code") and result.get("needs_order"):
            current_order = state.get("session_context", {}).get("current_order_code")
            if current_order:
                result["order_code"] = current_order
                result["context_order_reused"] = True
        waiting_for = state.get("session_context", {}).get("waiting_for")
        pending_question = state.get("session_context", {}).get("pending_question")
        if waiting_for == "order_selection" and result.get("order_code") and pending_question:
            pending_plan = classify_question(str(pending_question))
            if pending_plan.get("intent") != "unknown":
                result["intent"] = pending_plan["intent"]
                result["needs_order"] = pending_plan["needs_order"]
                result["resumed_pending_question"] = True
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
        if state["intent"] == "issue_type_clarify":
            return "clarify"
        return "supervise"

    @staticmethod
    def _skill_for_intent(intent: str) -> str | None:
        mapping = {
            "refund": "refund", "refund_status": "refund", "after_sales": "refund",
            "delivery_timeout": "delivery-incident", "delivery_incident_theft": "delivery-incident", "delivery_incident_damage": "delivery-incident",
            "food_foreign_object": "food-safety", "food_safety": "food-safety", "food_quality": "food-safety",
            "payment_issue": "payment", "cancel_order": "order-cancellation",
        }
        return mapping.get(intent)

    def _order_agent(self, state: AgentState) -> ToolResult | None:
        if not state.get("needs_order"):
            return None
        if state.get("order_code"):
            return self.order_tools.get_my_order(state["order_code"] or "", state["question"])
        list_result = self.order_tools.list_my_orders_by_date(state["order_date"], state["question"]) if state.get("order_date") else self.order_tools.list_my_today_orders(state["question"])
        if not list_result.ok or not list_result.data:
            return ToolResult(False, "NO_DATED_ORDERS", "当前账户在指定日期没有可查询的订单。")
        if len(list_result.data) > 1:
            return ToolResult(True, "MULTIPLE_DATED_ORDERS", "指定日期有多个订单，需要用户选择。", list_result.data)
        return ToolResult(True, "ORDER_FOUND", "已自动定位当前账户今天的订单。", list_result.data[0])

    @staticmethod
    def _risk_agent(state: AgentState) -> dict[str, str]:
        question = state["question"]
        if any(value in question for value in ("威胁", "自杀", "报警", "中毒", "住院")):
            return {"level": "high", "action": "handoff"}
        return {"level": state.get("risk", "none"), "action": "continue"}

    def _supervise(self, state: AgentState) -> dict[str, Any]:
        tasks = {
            "OrderAgent": lambda: self._order_agent(state),
            "PolicyAgent": lambda: self.rule_retriever.retrieve(state["question"], state["intent"], None, enforce_status=False),
            "RiskAgent": lambda: self._risk_agent(state),
        }
        if self.memory is not None:
            tasks["MemoryAgent"] = lambda: self.memory.recall(state["question"])
        runs = self.supervisor.dispatch(tasks)
        order_result = runs["OrderAgent"].data if runs["OrderAgent"].ok else ToolResult(False, "ORDER_TOOL_ERROR", "订单查询暂时不可用。")
        policy_match = runs["PolicyAgent"].data if runs["PolicyAgent"].ok else RuleMatch(False, "POLICY_TOOL_ERROR", "规则检索暂时不可用。")
        risk_result = runs["RiskAgent"].data if runs["RiskAgent"].ok else {"level": "high", "action": "handoff"}
        single_order = order_result.data if order_result and isinstance(order_result.data, dict) else None
        trace_steps = (["query_order"] if state.get("needs_order") else []) + ["retrieve_rule"]
        selected_skill = self._skill_for_intent(state["intent"])
        if single_order and self.memory is not None and self.memory_session_id is not None and hasattr(self.memory, "update_context"):
            self.memory.update_context(self.memory_session_id, current_order_code=single_order.get("order_code"), current_order_status=single_order.get("order_status"), current_issue_type=state.get("intent"), waiting_for=None)
        if selected_skill and self.skill_registry:
            self.skill_registry.get(selected_skill)
        return {
            "order_result": order_result,
            "order_status": single_order.get("order_status") if single_order else None,
            "order_code": single_order.get("order_code") if single_order else state.get("order_code"),
            "rule_match": policy_match,
            "risk": risk_result["level"],
            "selected_skill": selected_skill,
            "memory_hits": runs.get("MemoryAgent").data if runs.get("MemoryAgent") and runs["MemoryAgent"].ok else [],
            "user_confirmed_actual_state": state.get("user_confirmed_actual_state", False),
            "agent_runs": [self._serialize_run(run) for run in runs.values()],
            "trace": state["trace"] + trace_steps,
        }

    @staticmethod
    def _serialize_run(run: AgentRun) -> dict[str, Any]:
        return {"agent": run.agent, "ok": run.ok, "duration_ms": run.duration_ms, "thread_name": run.thread_name, "error": run.error}

    def _route_after_supervise(self, state: AgentState) -> str:
        if state.get("risk") == "high":
            return "handoff"
        order_result = state.get("order_result")
        if order_result and order_result.code in {"MULTIPLE_DATED_ORDERS", "NO_DATED_ORDERS"}:
            return "clarify"
        if state.get("needs_order") and (not order_result or not order_result.ok):
            return "reject"
        return "validate_evidence"

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
        match = self.rule_retriever.retrieve(state["question"], state["intent"], None, enforce_status=False)
        review = self.evidence_reviewer.review(
            intent=state["intent"], risk=state.get("risk", "none"), needs_order=state.get("needs_order", False),
            order_result=state.get("order_result"), order_status=state.get("order_status"),
            rule_match=match, memory_hits=state.get("memory_hits", []),
            user_confirmed_actual_state=state.get("user_confirmed_actual_state", False),
        )
        retrieval = {"method": match.retrieval_method, "model": match.model_name, "score": round(match.score, 4)}
        evidence_review = {"approved": review.approved, "decision": review.decision, "reasons": list(review.reasons), "case_action": review.case_action, "required_evidence": review.required_evidence}
        return {"rule_match": match, "retrieval": retrieval, "decision": review.decision, "evidence_review": evidence_review, "trace": state["trace"] + ["validate_evidence"]}

    def _route_after_evidence(self, state: AgentState) -> str:
        if state["decision"] == "answer" and state.get("evidence_review", {}).get("case_action") and self.case_tools:
            return "act_case"
        return state["decision"]

    def _act_case(self, state: AgentState) -> dict[str, Any]:
        review = state["evidence_review"]
        result = self.case_tools.create_case(
            state.get("order_code") or "",
            state["intent"],
            f"用户咨询 {state['intent']}，Evidence Reviewer 已核验订单与规则。",
            review.get("required_evidence"),
        )
        return {"case_result": result}

    def _answer(self, state: AgentState) -> dict[str, Any]:
        match = state["rule_match"]
        generated = self.answer_generator.generate(state["question"], state.get("order_status"), match.rule)
        answer = generated.answer
        case_result = state.get("case_result")
        if case_result and case_result.ok and case_result.data:
            case_code = case_result.data.get("case_code")
            action = "已创建" if case_result.data.get("created", True) else "已关联现有"
            answer += f" {action}售后工单 {case_code}，后续处理会记录在该工单中。"
        source = {"rule_id": match.source.rule_id, "title": match.source.title, "url": match.source.url, "score": round(match.score, 4)}
        if self.memory is not None and self.memory_session_id is not None and hasattr(self.memory, "update_context"):
            self.memory.update_context(self.memory_session_id, current_issue_type=state.get("intent"), waiting_for=None, pending_question=None)
        return {"answer": answer, "provider": generated.provider, "fallback_reason": generated.fallback_reason, "sources": [source], "decision": "answer", "trace": state["trace"] + ["answer"]}

    def _clarify(self, state: AgentState) -> dict[str, Any]:
        order_result = state.get("order_result")
        if order_result and order_result.code == "MULTIPLE_DATED_ORDERS":
            if self.memory is not None and self.memory_session_id is not None and hasattr(self.memory, "update_context"):
                self.memory.update_context(self.memory_session_id, current_issue_type=state.get("intent"), waiting_for="order_selection", pending_question=state.get("question"))
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
            review = state.get("evidence_review", {})
            if review.get("decision") == "clarify":
                if self.memory is not None and self.memory_session_id is not None and hasattr(self.memory, "update_context"):
                    self.memory.update_context(self.memory_session_id, current_issue_type=state.get("intent"), waiting_for="actual_state_confirmation", pending_question=state.get("question"))
                answer = "数据库订单状态与您描述的实际情况不一致。请先确认是否已经收到餐品；确认后我会继续询问具体问题，不会修改数据库中的订单状态。"
                choices = [
                    {"label": "确认已收到餐品", "value": "confirm_actual_state", "question": f"我确认实际已收到餐品，请按实际情况处理，不修改订单状态。订单号 {state.get('order_code') or ''}"},
                    {"label": "不确认，按订单状态处理", "value": "use_database_status", "question": "我不确认实际收货情况，请按数据库订单状态处理。"},
                ]
            elif state.get("intent") == "issue_type_clarify":
                if self.memory is not None and self.memory_session_id is not None and hasattr(self.memory, "update_context"):
                    self.memory.update_context(self.memory_session_id, waiting_for="issue_description", last_confirmed_fact="用户确认实际已收到餐品")
                answer = "好的，请直接描述这笔订单遇到的具体问题。我会重新进行开放式语义判断并检索知识库，不会把问题限制在固定选项中。"
                choices = []
            else:
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
        review = state.get("evidence_review", {})
        reasons = review.get("reasons") or [state.get("rule_match").message if state.get("rule_match") else "当前证据不足"]
        generated = self.answer_generator.explain_refusal(state["question"], "；".join(str(reason) for reason in reasons))
        return {
            "answer": generated.answer,
            "provider": generated.provider,
            "fallback_reason": generated.fallback_reason,
            "decision": "abstain",
            "trace": state["trace"] + ["abstain"],
        }

    def _handoff(self, state: AgentState) -> dict[str, Any]:
        self.order_tools.record_event(state["question"], "HANDOFF_HIGH_RISK", None)
        return {"answer": "该问题涉及高风险投诉，需要人工客服进一步核验，我将建议转人工处理。", "provider": "local-policy", "decision": "handoff", "trace": state["trace"] + ["handoff"]}
