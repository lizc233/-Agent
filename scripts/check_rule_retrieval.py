from __future__ import annotations

import argparse
import json
import sys

from backend.config import load_settings
from backend.rules import RuleRetriever, load_rules


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Check deterministic customer-rule retrieval.")
    parser.add_argument("--question", required=True)
    parser.add_argument("--intent", required=True)
    parser.add_argument("--order-status")
    arguments = parser.parse_args()
    settings = load_settings(require_database=False)
    result = RuleRetriever(load_rules(settings)).retrieve(arguments.question, arguments.intent, arguments.order_status)
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2, default=lambda value: value.__dict__))
    return 0 if result.found else 2


if __name__ == "__main__":
    sys.exit(main())
