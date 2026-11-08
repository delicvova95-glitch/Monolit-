import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
INSTANCE_DIR = BASE_DIR / "instance"
UPLOAD_DIR = INSTANCE_DIR / "uploads"


def _secret_key():
    configured = os.environ.get("SECRET_KEY")
    if configured:
        return configured
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    key_file = INSTANCE_DIR / ".secret_key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    key = secrets.token_urlsafe(48)
    key_file.write_text(key, encoding="utf-8")
    return key


class Config:
    SECRET_KEY = _secret_key()
    DATABASE = os.environ.get("DATABASE_PATH", str(INSTANCE_DIR / "monolit.sqlite3"))
    UPLOAD_FOLDER = os.environ.get("UPLOAD_PATH", str(UPLOAD_DIR))
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
    TRUST_PROXY = os.environ.get("TRUST_PROXY", "0") == "1"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "")
    NOTIFY_EMAIL_TO = os.environ.get("NOTIFY_EMAIL_TO", "")
    SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "0") == "1"
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "1") == "1"
