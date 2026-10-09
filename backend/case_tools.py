from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import secrets
from typing import Any, Callable

from .config import Settings
from .database import connection
from .tools import AgentSession

CASE_STATUSES = {"WAITING_EVIDENCE", "PENDING_REVIEW", "SOLUTION_PROPOSED", "CLOSED", "HUMAN_HANDOFF"}
ALLOWED_TRANSITIONS = {
    "WAITING_EVIDENCE": {"PENDING_REVIEW", "HUMAN_HANDOFF", "CLOSED"},
    "PENDING_REVIEW": {"WAITING_EVIDENCE", "SOLUTION_PROPOSED", "HUMAN_HANDOFF"},
    "SOLUTION_PROPOSED": {"CLOSED", "HUMAN_HANDOFF"},
    "HUMAN_HANDOFF": {"CLOSED"},
    "CLOSED": set(),
}


@dataclass(frozen=True)
class CaseResult:
    ok: bool
    code: str
    message: str
    data: dict[str, Any] | None = None


def _create_case(settings: Settings, user_id: int, order_code: str, issue_type: str, summary: str, required_evidence: str | None) -> dict[str, Any] | None:
    case_code = f"AS{datetime.now():%Y%m%d%H%M%S}{secrets.token_hex(3).upper()}"
    with connection(settings) as database_connection:
        cursor = database_connection.cursor(dictionary=True)
        cursor.execute("SELECT order_code FROM customer_order WHERE user_id = %s AND order_code = %s FOR UPDATE", (user_id, order_code))
        if cursor.fetchone() is None:
            cursor.close()
            return None
        cursor.execute(
            "SELECT id, case_code, order_code, issue_type, case_status, summary, required_evidence FROM after_sales_case WHERE user_id = %s AND order_code = %s AND issue_type = %s AND case_status <> 'CLOSED' ORDER BY id DESC LIMIT 1",
            (user_id, order_code, issue_type),
        )
        existing = cursor.fetchone()
        if existing:
            database_connection.commit()
            cursor.close()
            existing["created"] = False
            return existing
        cursor.execute("INSERT INTO after_sales_case (case_code, user_id, order_code, issue_type, case_status, summary, required_evidence) VALUES (%s, %s, %s, %s, 'WAITING_EVIDENCE', %s, %s)", (case_code, user_id, order_code, issue_type, summary, required_evidence))
        case_id = cursor.lastrowid
        cursor.execute("INSERT INTO case_event (case_id, event_type, event_content) VALUES (%s, %s, %s)", (case_id, "CASE_CREATED", summary))
        database_connection.commit()
        cursor.close()
    return {"id": case_id, "case_code": case_code, "order_code": order_code, "issue_type": issue_type, "case_status": "WAITING_EVIDENCE", "summary": summary, "required_evidence": required_evidence, "created": True}


def _get_case(settings: Settings, user_id: int, case_code: str) -> dict[str, Any] | None:
    with connection(settings) as database_connection:
        cursor = database_connection.cursor(dictionary=True)
        cursor.execute("SELECT id, case_code, order_code, issue_type, case_status, summary, required_evidence, created_at, updated_at FROM after_sales_case WHERE user_id = %s AND case_code = %s", (user_id, case_code))
        row = cursor.fetchone()
        cursor.close()
    return row


def _transition_case(settings: Settings, user_id: int, case_code: str, expected_status: str, target_status: str, event_content: str) -> dict[str, Any] | None:
    with connection(settings) as database_connection:
        cursor = database_connection.cursor(dictionary=True)
        cursor.execute("SELECT id FROM after_sales_case WHERE user_id = %s AND case_code = %s AND case_status = %s FOR UPDATE", (user_id, case_code, expected_status))
        row = cursor.fetchone()
        if row is None:
            database_connection.rollback()
            cursor.close()
            return None
        cursor.execute("UPDATE after_sales_case SET case_status = %s WHERE id = %s", (target_status, row["id"]))
        cursor.execute("INSERT INTO case_event (case_id, event_type, event_content) VALUES (%s, %s, %s)", (row["id"], f"STATUS_{target_status}", event_content))
        database_connection.commit()
        cursor.close()
    return {"case_code": case_code, "case_status": target_status}


class CaseTools:
    def __init__(self, settings: Settings, session: AgentSession, create_case_record: Callable[..., dict[str, Any] | None] = _create_case, get_case_record: Callable[..., dict[str, Any] | None] = _get_case, transition_case_record: Callable[..., dict[str, Any] | None] = _transition_case) -> None:
        if session.current_user_id <= 0:
            raise ValueError("current_user_id must be a positive database primary key")
        self.settings, self.session = settings, session
        self._create_case_record, self._get_case_record = create_case_record, get_case_record
        self._transition_case_record = transition_case_record

    def create_case(self, order_code: str, issue_type: str, summary: str, required_evidence: str | None = None) -> CaseResult:
        order_code = order_code.strip().upper()
        if not order_code or not issue_type.strip() or not summary.strip():
            return CaseResult(False, "INVALID_CASE_INPUT", "订单号、问题类型和问题摘要不能为空。")
        row = self._create_case_record(self.settings, self.session.current_user_id, order_code, issue_type.strip(), summary.strip(), required_evidence.strip() if required_evidence else None)
        return CaseResult(True, "CASE_CREATED", "售后工单已创建。", row) if row else CaseResult(False, "ORDER_NOT_AVAILABLE", "当前账户下未找到该订单，不能创建售后工单。")

    def get_case(self, case_code: str) -> CaseResult:
        row = self._get_case_record(self.settings, self.session.current_user_id, case_code.strip().upper())
        return CaseResult(True, "CASE_FOUND", "已查询到售后工单。", row) if row else CaseResult(False, "CASE_NOT_AVAILABLE", "当前账户下未找到该售后工单。")

    def transition_case(self, case_code: str, target_status: str, event_content: str) -> CaseResult:
        target_status = target_status.strip().upper()
        if target_status not in CASE_STATUSES:
            return CaseResult(False, "INVALID_CASE_STATUS", "不支持该工单状态。")
        current = self.get_case(case_code)
        if not current.ok or current.data is None:
            return current
        current_status = str(current.data["case_status"])
        if target_status not in ALLOWED_TRANSITIONS[current_status]:
            return CaseResult(False, "INVALID_CASE_TRANSITION", f"工单不能从 {current_status} 变更为 {target_status}。", current.data)
        row = self._transition_case_record(self.settings, self.session.current_user_id, case_code.strip().upper(), current_status, target_status, event_content.strip() or "Agent 推进工单状态")
        return CaseResult(True, "CASE_TRANSITIONED", "工单状态已更新。", row) if row else CaseResult(False, "CASE_CONFLICT", "工单状态已变化，请重新查询后再操作。")
