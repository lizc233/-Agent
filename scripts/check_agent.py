from __future__ import annotations

import argparse
import json
import sys

from backend.agent import CustomerServiceAgent
from backend.config import load_settings
from backend.generation import build_answer_generator
from backend.rules import RuleRetriever, load_rules
from backend.tools import AgentSession, OrderTools


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run one LangGraph customer-service Agent turn.")
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--question", required=True)
    arguments = parser.parse_args()
    settings = load_settings()
    agent = CustomerServiceAgent(
        OrderTools(settings, AgentSession(arguments.user_id)),
        RuleRetriever(load_rules(settings)),
        build_answer_generator(settings),
    )
    result = agent.invoke(arguments.question)
    output = {key: value for key, value in result.items() if key not in {"order_result", "rule_match"}}
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
