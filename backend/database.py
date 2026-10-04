from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import mysql.connector
from mysql.connector import MySQLConnection

from .config import Settings


@contextmanager
def connection(settings: Settings) -> Iterator[MySQLConnection]:
    database_connection = mysql.connector.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        database=settings.mysql_database,
        user=settings.mysql_user,
        password=settings.mysql_password,
        connection_timeout=5,
    )
    try:
        yield database_connection
    finally:
        database_connection.close()


def check_connection(settings: Settings) -> tuple[bool, str]:
    try:
        with connection(settings) as database_connection:
            cursor = database_connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
        return True, "MySQL connection is healthy"
    except Exception as error:
        return False, f"MySQL connection failed: {error}"


def list_current_user_orders(settings: Settings, user_id: int) -> list[dict[str, Any]]:
    query = """
        SELECT order_code, order_status, created_at
        FROM customer_order
        WHERE user_id = %s
        ORDER BY created_at DESC, id DESC
    """
    with connection(settings) as database_connection:
        cursor = database_connection.cursor(dictionary=True)
        cursor.execute(query, (user_id,))
        rows = list(cursor.fetchall())
        cursor.close()
    return rows


def list_current_user_today_orders(settings: Settings, user_id: int) -> list[dict[str, Any]]:
    query = """
        SELECT order_code, order_status, created_at
        FROM customer_order
        WHERE user_id = %s
          AND created_at >= CURRENT_DATE()
          AND created_at < CURRENT_DATE() + INTERVAL 1 DAY
        ORDER BY created_at DESC, id DESC
    """
    with connection(settings) as database_connection:
        cursor = database_connection.cursor(dictionary=True)
        cursor.execute(query, (user_id,))
        rows = list(cursor.fetchall())
        cursor.close()
    return rows


def list_current_user_orders_by_date(settings: Settings, user_id: int, order_date: str) -> list[dict[str, Any]]:
    query = """
        SELECT order_code, order_status, created_at
        FROM customer_order
        WHERE user_id = %s AND DATE(created_at) = %s
        ORDER BY created_at DESC, id DESC
    """
    with connection(settings) as database_connection:
        cursor = database_connection.cursor(dictionary=True)
        cursor.execute(query, (user_id, order_date))
        rows = list(cursor.fetchall())
        cursor.close()
    return rows


def get_current_user_order(settings: Settings, user_id: int, order_code: str) -> dict[str, Any] | None:
    query = """
        SELECT order_code, order_status, created_at
        FROM customer_order
        WHERE user_id = %s AND order_code = %s
    """
    with connection(settings) as database_connection:
        cursor = database_connection.cursor(dictionary=True)
        cursor.execute(query, (user_id, order_code))
        row = cursor.fetchone()
        cursor.close()
    return row


def write_audit_log(
    settings: Settings,
    user_id: int,
    question: str,
    action: str,
    source_rule_id: str | None = None,
) -> None:
    query = """
        INSERT INTO agent_audit_log (user_id, question, action, source_rule_id)
        VALUES (%s, %s, %s, %s)
    """
    with connection(settings) as database_connection:
        cursor = database_connection.cursor()
        cursor.execute(query, (user_id, question, action, source_rule_id))
        database_connection.commit()
        cursor.close()
