"""Every setting comes from an environment variable. Secrets have no default."""

import os


def from_env() -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    return {
        "PORT": int(os.environ.get("PORT", "8000")),
        "DATABASE_URL": os.environ.get("DATABASE_URL"),  # required; mssql://user:password@host:1433/database
        "UI_ORIGIN": os.environ.get("UI_ORIGIN", "http://localhost:8080"),
        "GIT_SHA": os.environ.get("GIT_SHA", "dev"),
        "DB_CONNECT_ATTEMPTS": int(os.environ.get("DB_CONNECT_ATTEMPTS", "8")),  # ~2 min of backoff
        "MIGRATIONS_DIR": os.environ.get("MIGRATIONS_DIR", os.path.join(here, "..", "migrations")),
        "CONTENT_URL": os.environ.get("CONTENT_URL", "http://content:8000"),  # the content service
        "CONTENT_TIMEOUT_S": float(os.environ.get("CONTENT_TIMEOUT_S", "2")),  # seconds per call
    }
