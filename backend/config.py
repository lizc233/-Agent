from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import sys

from dotenv import load_dotenv


if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(getattr(sys, "_MEIPASS"))
    APP_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    APP_ROOT = PROJECT_ROOT
load_dotenv(APP_ROOT / ".env")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value.startswith("your_"):
        raise ValueError(
            f"缺少本地配置 {name}。请将项目目录中的 .env 复制到 EXE 同目录：{APP_ROOT / '.env'}，"
            f"然后填写 {name}。模板位置：{APP_ROOT / '.env.example'}"
        )
    return value


@dataclass(frozen=True)
class Settings:
    mysql_host: str
    mysql_port: int
    mysql_database: str
    mysql_user: str
    mysql_password: str
    rules_path: Path
    offline_fallback: bool
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    current_user_id: int


def load_settings(require_database: bool = True) -> Settings:
    if require_database:
        mysql_host = _required("MYSQL_HOST")
        mysql_database = _required("MYSQL_DATABASE")
        mysql_user = _required("MYSQL_USER")
        mysql_password = _required("MYSQL_PASSWORD")
    else:
        mysql_host = os.getenv("MYSQL_HOST", "127.0.0.1").strip()
        mysql_database = os.getenv("MYSQL_DATABASE", "kangaroo_agent").strip()
        mysql_user = os.getenv("MYSQL_USER", "").strip()
        mysql_password = os.getenv("MYSQL_PASSWORD", "").strip()
    return Settings(
        mysql_host=mysql_host,
        mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
        mysql_database=mysql_database,
        mysql_user=mysql_user,
        mysql_password=mysql_password,
        rules_path=PROJECT_ROOT / "data" / "knowledge" / "customer_rules.jsonl",
        offline_fallback=os.getenv("OFFLINE_FALLBACK", "true").lower() == "true",
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip().rstrip("/"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip(),
        current_user_id=int(os.getenv("CURRENT_USER_ID", "1")),
    )
