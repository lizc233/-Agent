from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


KNOWN_TOOLS = {
    "get_my_order",
    "list_my_today_orders",
    "search_policy",
    "recall_memory",
    "create_after_sales_case",
    "transition_after_sales_case",
    "handoff_human",
}


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    intents: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    required_evidence: tuple[str, ...]
    escalation_conditions: tuple[str, ...]
    prohibited_promises: tuple[str, ...]
    directory: Path


class SkillRegistry:
    def __init__(self, skills_root: Path) -> None:
        self.skills_root = skills_root
        self.skills = self._load()

    def _load(self) -> dict[str, SkillDefinition]:
        loaded: dict[str, SkillDefinition] = {}
        for workflow_path in sorted(self.skills_root.glob("*/workflow.json")):
            data: dict[str, Any] = json.loads(workflow_path.read_text(encoding="utf-8"))
            name = str(data["name"])
            skill_markdown = workflow_path.parent / "SKILL.md"
            if not skill_markdown.exists():
                raise ValueError(f"Skill {name} is missing SKILL.md")
            tools = tuple(str(tool) for tool in data["allowed_tools"])
            unknown_tools = set(tools) - KNOWN_TOOLS
            if unknown_tools:
                raise ValueError(f"Skill {name} contains unknown tools: {sorted(unknown_tools)}")
            if name in loaded:
                raise ValueError(f"Duplicate skill name: {name}")
            loaded[name] = SkillDefinition(
                name=name,
                description=str(data["description"]),
                intents=tuple(str(item) for item in data["intents"]),
                allowed_tools=tools,
                required_evidence=tuple(str(item) for item in data["required_evidence"]),
                escalation_conditions=tuple(str(item) for item in data["escalation_conditions"]),
                prohibited_promises=tuple(str(item) for item in data["prohibited_promises"]),
                directory=workflow_path.parent,
            )
        return loaded

    def get(self, name: str) -> SkillDefinition:
        if name not in self.skills:
            raise KeyError(f"Unknown skill: {name}")
        return self.skills[name]

    def planner_catalog(self) -> list[dict[str, Any]]:
        return [{"name": skill.name, "description": skill.description, "intents": list(skill.intents)} for skill in self.skills.values()]
