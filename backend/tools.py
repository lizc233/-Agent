from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .config import Settings
from .database import get_current_user_order, list_current_user_orders, list_current_user_orders_by_date, list_current_user_today_orders, write_audit_log


@dataclass(frozen=True)
class AgentSession:
    current_user_id: int


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    code: str
    message: str
    data: Any = None


class OrderTools:
    def __init__(
        self,
        settings: Settings,
        session: AgentSession,
        list_orders: Callable[[Settings, int], list[dict[str, Any]]] = list_current_user_orders,
        list_today_orders: Callable[[Settings, int], list[dict[str, Any]]] = list_current_user_today_orders,
        list_orders_by_date: Callable[[Settings, int, str], list[dict[str, Any]]] = list_current_user_orders_by_date,
        get_order: Callable[[Settings, int, str], dict[str, Any] | None] = get_current_user_order,
        audit: Callable[[Settings, int, str, str, str | None], None] = write_audit_log,
    ) -> None:
        if session.current_user_id <= 0:
            raise ValueError("current_user_id must be a positive database primary key")
        self.settings = settings
        self.session = session
        self._list_orders = list_orders
        self._list_today_orders = list_today_orders
        self._list_orders_by_date = list_orders_by_date
        self._get_order = get_order
        self._audit = audit

    def list_my_orders(self, question: str) -> ToolResult:
        orders = self._list_orders(self.settings, self.session.current_user_id)
        self._audit(
            self.settings,
            self.session.current_user_id,
            question,
            "LIST_MY_ORDERS",
            None,
        )
        if not orders:
            return ToolResult(True, "NO_ORDERS", "当前账户没有可查询的订单。", [])
        return ToolResult(True, "ORDERS_FOUND", "已查询当前账户的订单。", orders)

    def get_my_order(self, order_code: str, question: str) -> ToolResult:
        normalized_order_code = order_code.strip().upper()
        if not normalized_order_code:
            return ToolResult(False, "INVALID_ORDER_CODE", "请提供订单号。")
        order = self._get_order(
            self.settings,
            self.session.current_user_id,
            normalized_order_code,
        )
        action = "GET_MY_ORDER_FOUND" if order else "GET_MY_ORDER_NOT_AVAILABLE"
        self._audit(
            self.settings,
            self.session.current_user_id,
            question,
            action,
            None,
        )
        if order is None:
            return ToolResult(
                False,
                "ORDER_NOT_AVAILABLE",
                "当前账户下未找到该订单，无法提供订单状态。",
            )
        return ToolResult(True, "ORDER_FOUND", "已查询到当前账户的订单状态。", order)

    def list_my_today_orders(self, question: str) -> ToolResult:
        orders = self._list_today_orders(self.settings, self.session.current_user_id)
        self._audit(self.settings, self.session.current_user_id, question, "LIST_MY_TODAY_ORDERS", None)
        if not orders:
            return ToolResult(True, "NO_TODAY_ORDERS", "当前账户今天没有可查询的订单。", [])
        return ToolResult(True, "TODAY_ORDERS_FOUND", "已查询当前账户今天的订单。", orders)

    def list_my_orders_by_date(self, order_date: str, question: str) -> ToolResult:
        orders = self._list_orders_by_date(self.settings, self.session.current_user_id, order_date)
        self._audit(self.settings, self.session.current_user_id, question, "LIST_MY_ORDERS_BY_DATE", None)
        code = "DATED_ORDERS_FOUND" if orders else "NO_DATED_ORDERS"
        return ToolResult(True, code, f"已查询当前账户 {order_date} 的订单。", orders)

    def record_event(self, question: str, action: str, source_rule_id: str | None = None) -> None:
        self._audit(
            self.settings,
            self.session.current_user_id,
            question,
            action,
            source_rule_id,
        )
