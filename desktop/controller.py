from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from backend.agent import CustomerServiceAgent


class WorkerSignals(QObject):
    completed = Signal(dict)
    failed = Signal(str)


class AgentWorker(QRunnable):
    def __init__(self, agent: CustomerServiceAgent, question: str) -> None:
        super().__init__()
        self.agent = agent
        self.question = question
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.agent.invoke(self.question)
            output: dict[str, Any] = {
                key: value
                for key, value in result.items()
                if key not in {"order_result", "rule_match"}
            }
            self.signals.completed.emit(output)
        except Exception as error:
            self.signals.failed.emit(str(error))


class AgentController(QObject):
    response_ready = Signal(dict)
    response_failed = Signal(str)

    def __init__(self, agent: CustomerServiceAgent) -> None:
        super().__init__()
        self.agent = agent
        self.thread_pool = QThreadPool.globalInstance()
        self.active_workers: set[AgentWorker] = set()

    @Slot(str)
    def submit(self, question: str) -> None:
        worker = AgentWorker(self.agent, question)
        self.active_workers.add(worker)
        worker.signals.completed.connect(lambda result, current=worker: self._completed(current, result))
        worker.signals.failed.connect(lambda message, current=worker: self._failed(current, message))
        self.thread_pool.start(worker)

    def _completed(self, worker: AgentWorker, result: dict) -> None:
        self.active_workers.discard(worker)
        self.response_ready.emit(result)

    def _failed(self, worker: AgentWorker, message: str) -> None:
        self.active_workers.discard(worker)
        self.response_failed.emit(message)
