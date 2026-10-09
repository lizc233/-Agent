from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import secrets
from typing import Any, Callable

import numpy as np

from .config import Settings
from .database import connection
from .semantic_retrieval import resolve_model_path
from .tools import AgentSession


@dataclass(frozen=True)
class MemoryHit:
    memory_id: int
    summary: str
    score: float
    order_code: str | None = None
    issue_type: str | None = None
    pending_information: str | None = None


def _start_session(settings: Settings, user_id: int, session_code: str) -> int:
    with connection(settings) as database_connection:
        cursor = database_connection.cursor()
        cursor.execute("INSERT INTO conversation_session (session_code, user_id) VALUES (%s, %s)", (session_code, user_id))
        session_id = cursor.lastrowid
        database_connection.commit()
        cursor.close()
    return int(session_id)


def _insert_memory(settings: Settings, user_id: int, session_id: int, order_code: str | None, issue_type: str | None, summary: str, pending_information: str | None) -> int:
    with connection(settings) as database_connection:
        cursor = database_connection.cursor()
        cursor.execute("INSERT INTO conversation_memory (session_id, user_id, order_code, issue_type, summary, pending_information) SELECT id, %s, %s, %s, %s, %s FROM conversation_session WHERE id = %s AND user_id = %s", (user_id, order_code, issue_type, summary, pending_information, session_id, user_id))
        if cursor.rowcount != 1:
            database_connection.rollback()
            cursor.close()
            raise ValueError("session does not belong to current user")
        memory_id = cursor.lastrowid
        database_connection.commit()
        cursor.close()
    return int(memory_id)


def _list_memories(settings: Settings, user_id: int, limit: int) -> list[dict[str, Any]]:
    with connection(settings) as database_connection:
        cursor = database_connection.cursor(dictionary=True)
        cursor.execute("SELECT id, order_code, issue_type, summary, pending_information, created_at FROM conversation_memory WHERE user_id = %s ORDER BY created_at DESC, id DESC LIMIT %s", (user_id, limit))
        rows = list(cursor.fetchall())
        cursor.close()
    return rows

def _get_session_context(settings: Settings, user_id: int, session_id: int) -> dict[str, Any]:
    with connection(settings) as database_connection:
        cursor = database_connection.cursor(dictionary=True)
        cursor.execute("SELECT current_order_code, current_order_status, current_issue_type, waiting_for, last_confirmed_fact, pending_question FROM conversation_session WHERE id = %s AND user_id = %s", (session_id, user_id))
        row = cursor.fetchone()
        cursor.close()
    return dict(row) if row else {}

def _update_session_context(settings: Settings, user_id: int, session_id: int, values: dict[str, Any]) -> None:
    allowed = {"current_order_code", "current_order_status", "current_issue_type", "waiting_for", "last_confirmed_fact", "pending_question"}

def _list_recent_turns(settings: Settings, user_id: int, session_id: int, limit: int) -> list[dict[str, Any]]:
    with connection(settings) as database_connection:
        cursor = database_connection.cursor(dictionary=True)
        cursor.execute("SELECT summary, order_code, issue_type, pending_information, created_at FROM conversation_memory WHERE session_id = %s AND user_id = %s ORDER BY created_at DESC, id DESC LIMIT %s", (session_id, user_id, limit))
        rows = list(cursor.fetchall())
        cursor.close()
    rows.reverse()
    return rows
    updates = {key: value for key, value in values.items() if key in allowed}
    if not updates:
        return
    assignments = ", ".join(f"{key} = %s" for key in updates)
    parameters = [updates[key] for key in updates] + [session_id, user_id]
    with connection(settings) as database_connection:
        cursor = database_connection.cursor()
        cursor.execute(f"UPDATE conversation_session SET {assignments} WHERE id = %s AND user_id = %s", parameters)
        database_connection.commit()
        cursor.close()


class ConversationMemory:
    def __init__(self, settings: Settings, session: AgentSession, start_session_record: Callable[[Settings, int, str], int] = _start_session, insert_memory_record: Callable[..., int] = _insert_memory, list_memory_records: Callable[[Settings, int, int], list[dict[str, Any]]] = _list_memories, encoder: Any | None = None) -> None:
        if session.current_user_id <= 0:
            raise ValueError("current_user_id must be a positive database primary key")
        self.settings, self.session = settings, session
        self._start_session_record, self._insert_memory_record = start_session_record, insert_memory_record
        self._list_memory_records, self._encoder = list_memory_records, encoder

    @property
    def encoder(self) -> Any:
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(str(resolve_model_path()), local_files_only=True)
        return self._encoder

    def start_session(self) -> tuple[int, str]:
        session_code = f"CS{datetime.now():%Y%m%d%H%M%S}{secrets.token_hex(3).upper()}"
        return self._start_session_record(self.settings, self.session.current_user_id, session_code), session_code

    def get_context(self, session_id: int) -> dict[str, Any]:
        return _get_session_context(self.settings, self.session.current_user_id, session_id)

    def update_context(self, session_id: int, **values: Any) -> None:
        _update_session_context(self.settings, self.session.current_user_id, session_id, values)

    def recent_turns(self, session_id: int, limit: int = 6) -> list[dict[str, Any]]:
        return _list_recent_turns(self.settings, self.session.current_user_id, session_id, limit)

    def remember(self, session_id: int, summary: str, order_code: str | None = None, issue_type: str | None = None, pending_information: str | None = None) -> int:
        if not summary.strip():
            raise ValueError("memory summary cannot be empty")
        return self._insert_memory_record(self.settings, self.session.current_user_id, session_id, order_code.strip().upper() if order_code else None, issue_type.strip() if issue_type else None, summary.strip(), pending_information.strip() if pending_information else None)

    def recall(self, query: str, limit: int = 3, threshold: float = 0.45) -> list[MemoryHit]:
        if not query.strip() or limit <= 0:
            return []
        rows = self._list_memory_records(self.settings, self.session.current_user_id, 50)
        if not rows:
            return []
        texts = [str(row["summary"]) for row in rows]
        embeddings = np.asarray(self.encoder.encode([query, *texts], normalize_embeddings=True, show_progress_bar=False), dtype=np.float32)
        ranked = sorted(zip(embeddings[1:] @ embeddings[0], rows), key=lambda item: float(item[0]), reverse=True)
        return [MemoryHit(int(row["id"]), str(row["summary"]), float(score), row.get("order_code"), row.get("issue_type"), row.get("pending_information")) for score, row in ranked[:limit] if float(score) >= threshold]
