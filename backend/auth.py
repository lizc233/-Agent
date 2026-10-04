from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import dataclass
from hashlib import pbkdf2_hmac
import hmac
import os

from .config import Settings
from .database import connection


PBKDF2_ITERATIONS = 210_000


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    user_code: str
    display_name: str


def hash_password(password: str) -> str:
    if len(password) < 6:
        raise ValueError("密码至少需要 6 位。")
    salt = os.urandom(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${b64encode(salt).decode()}${b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = pbkdf2_hmac("sha256", password.encode("utf-8"), b64decode(salt_text), int(iterations))
        return hmac.compare_digest(actual, b64decode(digest_text))
    except (ValueError, TypeError):
        return False


def ensure_auth_schema(settings: Settings) -> None:
    query = """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'customer_user' AND COLUMN_NAME = 'password_hash'
    """
    with connection(settings) as database_connection:
        cursor = database_connection.cursor()
        cursor.execute(query, (settings.mysql_database,))
        exists = cursor.fetchone()[0] > 0
        if not exists:
            cursor.execute("ALTER TABLE customer_user ADD COLUMN password_hash VARCHAR(255) NULL AFTER display_name")
            database_connection.commit()
        cursor.close()


def authenticate(settings: Settings, user_code: str, password: str) -> AuthenticatedUser | None:
    query = "SELECT id, user_code, display_name, password_hash FROM customer_user WHERE user_code = %s"
    with connection(settings) as database_connection:
        cursor = database_connection.cursor(dictionary=True)
        cursor.execute(query, (user_code.strip().upper(),))
        row = cursor.fetchone()
        cursor.close()
    if not row or not row["password_hash"] or not verify_password(password, row["password_hash"]):
        return None
    return AuthenticatedUser(int(row["id"]), row["user_code"], row["display_name"])


def register(settings: Settings, user_code: str, display_name: str, password: str) -> AuthenticatedUser:
    normalized_code = user_code.strip().upper()
    normalized_name = display_name.strip()
    if not normalized_code or not normalized_name:
        raise ValueError("用户编号和昵称不能为空。")
    encoded = hash_password(password)
    with connection(settings) as database_connection:
        cursor = database_connection.cursor(dictionary=True)
        cursor.execute("SELECT id, user_code, display_name, password_hash FROM customer_user WHERE user_code = %s FOR UPDATE", (normalized_code,))
        existing = cursor.fetchone()
        if existing and existing["password_hash"]:
            cursor.close()
            raise ValueError("该用户编号已注册。")
        if existing:
            cursor.execute("UPDATE customer_user SET display_name = %s, password_hash = %s WHERE id = %s", (normalized_name, encoded, existing["id"]))
            user_id = int(existing["id"])
        else:
            cursor.execute("INSERT INTO customer_user (user_code, display_name, password_hash) VALUES (%s, %s, %s)", (normalized_code, normalized_name, encoded))
            user_id = int(cursor.lastrowid)
        database_connection.commit()
        cursor.close()
    return AuthenticatedUser(user_id, normalized_code, normalized_name)
