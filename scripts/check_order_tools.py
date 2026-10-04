from __future__ import annotations

import argparse
import json
import sys

from backend.config import load_settings
from backend.tools import AgentSession, OrderTools


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Check controlled order tools for one current user.")
    parser.add_argument("--user-id", type=int, required=True, help="Current authenticated user's database primary key.")
    parser.add_argument("--order-code", help="Optional order code owned by the current user.")
    arguments = parser.parse_args()

    tools = OrderTools(load_settings(), AgentSession(arguments.user_id))
    if arguments.order_code:
        result = tools.get_my_order(arguments.order_code, "阶段二工具检查")
    else:
        result = tools.list_my_orders("阶段二工具检查")
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2, default=str))
    return 0 if result.ok else 2


if __name__ == "__main__":
    sys.exit(main())
