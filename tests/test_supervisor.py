from __future__ import annotations

from time import perf_counter, sleep
import unittest

from backend.supervisor import Supervisor


class SupervisorTest(unittest.TestCase):
    def test_independent_agents_run_in_parallel(self) -> None:
        def delayed(value: str) -> str:
            sleep(0.08)
            return value

        started = perf_counter()
        runs = Supervisor(max_workers=3).dispatch({
            "OrderAgent": lambda: delayed("order"),
            "PolicyAgent": lambda: delayed("policy"),
            "RiskAgent": lambda: delayed("risk"),
        })
        elapsed = perf_counter() - started

        self.assertLess(elapsed, 0.18)
        self.assertEqual({"OrderAgent", "PolicyAgent", "RiskAgent"}, set(runs))
        self.assertTrue(all(run.ok for run in runs.values()))
        self.assertTrue(all(run.thread_name.startswith("kangaroo-agent") for run in runs.values()))

    def test_one_agent_failure_does_not_cancel_other_agents(self) -> None:
        def fail() -> None:
            raise RuntimeError("tool unavailable")

        runs = Supervisor().dispatch({"OrderAgent": lambda: "ok", "MemoryAgent": fail})

        self.assertTrue(runs["OrderAgent"].ok)
        self.assertFalse(runs["MemoryAgent"].ok)
        self.assertIn("tool unavailable", runs["MemoryAgent"].error or "")


if __name__ == "__main__":
    unittest.main()
