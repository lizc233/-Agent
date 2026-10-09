from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import current_thread
from time import perf_counter
from typing import Any, Callable


@dataclass(frozen=True)
class AgentRun:
    agent: str
    ok: bool
    duration_ms: float
    thread_name: str
    data: Any = None
    error: str | None = None


class Supervisor:
    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers

    @staticmethod
    def _execute(agent: str, task: Callable[[], Any]) -> AgentRun:
        started = perf_counter()
        try:
            data = task()
            return AgentRun(agent, True, round((perf_counter() - started) * 1000, 2), current_thread().name, data)
        except Exception as error:
            return AgentRun(agent, False, round((perf_counter() - started) * 1000, 2), current_thread().name, error=str(error))

    def dispatch(self, tasks: dict[str, Callable[[], Any]]) -> dict[str, AgentRun]:
        if not tasks:
            return {}
        runs: dict[str, AgentRun] = {}
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(tasks)), thread_name_prefix="kangaroo-agent") as executor:
            futures = {executor.submit(self._execute, name, task): name for name, task in tasks.items()}
            for future in as_completed(futures):
                run = future.result()
                runs[run.agent] = run
        return runs
