from __future__ import annotations

import json
import asyncio
import socket
import unittest

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from backend.case_tools import CaseResult
from backend.mcp_server import build_mcp_server, start_mcp_server
from backend.rules import RuleMatch, RuleSource
from backend.tools import ToolResult


class FakeOrderTools:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get_my_order(self, order_code: str, question: str) -> ToolResult:
        self.calls.append((order_code, question))
        return ToolResult(True, "ORDER_FOUND", "found", {"order_code": order_code})

    def list_my_orders_by_date(self, order_date: str, question: str) -> ToolResult:
        return ToolResult(True, "ORDERS_FOUND", "found", [])


class FakeCaseTools:
    def create_case(self, order_code: str, issue_type: str, summary: str, required_evidence: str | None = None) -> CaseResult:
        return CaseResult(True, "CASE_CREATED", "created", {"case_code": "AS1"})

    def get_case(self, case_code: str) -> CaseResult:
        return CaseResult(True, "CASE_FOUND", "found", {"case_code": case_code})

    def transition_case(self, case_code: str, target_status: str, event_content: str) -> CaseResult:
        return CaseResult(True, "CASE_TRANSITIONED", "updated", {"case_code": case_code, "case_status": target_status})


class FakeMemory:
    def recall(self, query: str, limit: int = 3) -> list[object]:
        return []


class FakeRuleRetriever:
    def retrieve(self, question: str, intent: str, order_status: str | None) -> RuleMatch:
        return RuleMatch(True, "RULE_FOUND", "found", {"rule_id": "R1"}, RuleSource("R1", "规则", "http://localhost/r1", "content"), 0.9)


class McpServerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.orders = FakeOrderTools()
        self.server = build_mcp_server(self.orders, FakeCaseTools(), FakeMemory(), FakeRuleRetriever())

    async def test_exposes_expected_standard_mcp_tools(self) -> None:
        tools = self.server._tool_manager.list_tools()
        names = {tool.name for tool in tools}
        self.assertEqual({"get_my_order", "list_my_orders_by_date", "search_policy", "recall_memory", "create_after_sales_case", "get_after_sales_case", "transition_after_sales_case"}, names)

    async def test_tool_schemas_never_accept_user_id(self) -> None:
        for tool in self.server._tool_manager.list_tools():
            schema = json.dumps(tool.parameters, ensure_ascii=False)
            self.assertNotIn("user_id", schema)
            self.assertNotIn("current_user_id", schema)

    async def test_order_tool_delegates_to_session_bound_service(self) -> None:
        await self.server._tool_manager.call_tool("get_my_order", {"order_code": "OD100000", "question": "查询订单"})
        self.assertEqual([("OD100000", "查询订单")], self.orders.calls)

    async def test_streamable_http_transport_works_with_mcp_client(self) -> None:
        with socket.socket() as free_socket:
            free_socket.bind(("127.0.0.1", 0))
            port = free_socket.getsockname()[1]
        http_server, thread = start_mcp_server(self.server, port=port)
        try:
            for _ in range(50):
                if http_server.started:
                    break
                await asyncio.sleep(0.02)
            async with streamable_http_client(f"http://127.0.0.1:{port}/mcp") as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    self.assertIn("get_my_order", {tool.name for tool in tools.tools})
        finally:
            http_server.should_exit = True
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
