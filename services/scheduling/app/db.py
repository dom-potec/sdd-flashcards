"""SQL Server connections via pymssql. One connection per request, no pool."""

import logging
import time
from urllib.parse import unquote, urlsplit

import pymssql
from flask import current_app, g

log = logging.getLogger(__name__)


def parse_url(url: str) -> dict:
    """mssql://user:password@host:1433/database -> keyword arguments for pymssql.connect."""
    u = urlsplit(url)
    if u.scheme != "mssql" or not u.hostname or not u.path.strip("/"):
        raise ValueError("DATABASE_URL must look like mssql://user:password@host:1433/database")
    return {
        "server": u.hostname,
        "port": u.port or 1433,
        "user": unquote(u.username or ""),
        "password": unquote(u.password or ""),
        "database": u.path.strip("/"),
    }


def connect(url: str) -> pymssql.Connection:
    """A single connection attempt. Rows come back as dicts."""
    return pymssql.connect(**parse_url(url), as_dict=True, login_timeout=10, tds_version="7.4")


def connect_with_retry(url: str, attempts: int) -> pymssql.Connection:
    """Azure SQL serverless answers error 40613 while it resumes from pause (up to about a minute).
    Retry with exponential backoff: 1, 2, 4, 8, 16, 30, 30, 30 seconds."""
    delay = 1
    for attempt in range(1, attempts + 1):
        try:
            return connect(url)
        except pymssql.Error as e:
            if attempt == attempts:
                raise
            log.warning("db connect attempt %d/%d failed: %s; retrying in %ds", attempt, attempts, e, delay)
            time.sleep(delay)
            delay = min(delay * 2, 30)


def request_conn() -> pymssql.Connection:
    """The connection for the current request, opened on first use and closed by create_app's teardown."""
    if "conn" not in g:
        cfg = current_app.config
        g.conn = connect_with_retry(cfg["DATABASE_URL"], cfg["DB_CONNECT_ATTEMPTS"])
    return g.conn
