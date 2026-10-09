from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from threading import Thread
from typing import Any

from mcp.server.fastmcp import FastMCP
import uvicorn

from .case_tools import CaseTools
from .memory import ConversationMemory
from .rules import RuleRetriever
from .tools import OrderTools


def _json_value(value: Any) -> Any:
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def build_mcp_server(order_tools: OrderTools, case_tools: CaseTools, memory: ConversationMemory, rule_retriever: RuleRetriever) -> FastMCP:
    server = FastMCP(
        "kangaroo-customer-service",
        instructions="外卖客服本地工具。所有订单、工单和记忆操作都绑定桌面端当前登录用户。",
        stateless_http=True,
        json_response=True,
    )

    @server.tool(description="查询当前登录用户的一张订单；不能指定用户。")
    def get_my_order(order_code: str, question: str) -> dict[str, Any]:
        return _json_value(order_tools.get_my_order(order_code, question))

    @server.tool(description="查询当前登录用户在指定日期的订单；不能指定用户。")
    def list_my_orders_by_date(order_date: str, question: str) -> dict[str, Any]:
        return _json_value(order_tools.list_my_orders_by_date(order_date, question))

    @server.tool(description="使用本地 bge-m3 语义检索客服规则，并返回可访问来源。")
    def search_policy(question: str, intent: str, order_status: str | None = None) -> dict[str, Any]:
        return _json_value(rule_retriever.retrieve(question, intent, order_status))

    @server.tool(description="仅召回当前登录用户的相关长期会话记忆。")
    def recall_memory(query: str, limit: int = 3) -> list[dict[str, Any]]:
        return _json_value(memory.recall(query, limit=limit))

    @server.tool(description="为当前登录用户本人订单创建或复用售后工单。")
    def create_after_sales_case(order_code: str, issue_type: str, summary: str, required_evidence: str | None = None) -> dict[str, Any]:
        return _json_value(case_tools.create_case(order_code, issue_type, summary, required_evidence))

    @server.tool(description="查询当前登录用户的一张售后工单。")
    def get_after_sales_case(case_code: str) -> dict[str, Any]:
        return _json_value(case_tools.get_case(case_code))

    @server.tool(description="按状态机推进当前登录用户的售后工单。")
    def transition_after_sales_case(case_code: str, target_status: str, event_content: str) -> dict[str, Any]:
        return _json_value(case_tools.transition_case(case_code, target_status, event_content))

    return server


def start_mcp_server(server: FastMCP, host: str = "127.0.0.1", port: int = 8765) -> tuple[uvicorn.Server, Thread]:
    config = uvicorn.Config(
        server.streamable_http_app(),
        host=host,
        port=port,
        log_level="warning",
        log_config=None,
    )
    http_server = uvicorn.Server(config)
    thread = Thread(target=http_server.run, name="kangaroo-mcp-server", daemon=True)
    thread.start()
    return http_server, thread
