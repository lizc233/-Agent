from __future__ import annotations

import sys

from backend.config import load_settings
from backend.database import check_connection
from backend.rules import load_rules


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        settings = load_settings()
        rules = load_rules(settings)
    except Exception as error:
        print(f"Configuration or rules check failed: {error}")
        return 1

    connected, message = check_connection(settings)
    print(message)
    print(f"Rules loaded: {len(rules)}")
    print(f"Rules path: {settings.rules_path}")
    return 0 if connected else 1


if __name__ == "__main__":
    sys.exit(main())
