from __future__ import annotations

from pathlib import Path
import unittest

from backend.skill_registry import SkillRegistry


class SkillRegistryTest(unittest.TestCase):
    def test_loads_declared_skills_and_tool_boundaries(self) -> None:
        root = Path(__file__).resolve().parents[1] / "skills"
        registry = SkillRegistry(root)
        self.assertEqual(5, len(registry.skills))
        delivery = registry.get("delivery-incident")
        self.assertIn("create_after_sales_case", delivery.allowed_tools)
        self.assertNotIn("execute_sql", delivery.allowed_tools)

    def test_planner_catalog_does_not_include_full_instructions(self) -> None:
        root = Path(__file__).resolve().parents[1] / "skills"
        catalog = SkillRegistry(root).planner_catalog()
        self.assertIn("intents", catalog[0])
        self.assertNotIn("prohibited_promises", catalog[0])


if __name__ == "__main__":
    unittest.main()
