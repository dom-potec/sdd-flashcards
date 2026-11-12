"""Fixtures for the content tests. They need a real SQL Server:
locally `docker compose up -d sqlserver db-init`, in CI a service container."""

import os

import pytest

from app import create_app, db, migrate

# Local-only development credential, the same one as in docker-compose.yml. CI passes its own URL.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "mssql://sa:LocalDev_Passw0rd@localhost:1433/content_test"
)
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "migrations")


def url_for_database(name: str) -> str:
    """TEST_DATABASE_URL pointing at another database on the same server."""
    return TEST_DATABASE_URL.rsplit("/", 1)[0] + "/" + name


def recreate_database(name: str) -> None:
    """Drop and create an empty database. CREATE DATABASE cannot run in a transaction, hence autocommit."""
    master = db.connect(url_for_database("master"))
    master.autocommit(True)
    cur = master.cursor()
    cur.execute(f"IF DB_ID('{name}') IS NOT NULL DROP DATABASE [{name}]")
    cur.execute(f"CREATE DATABASE [{name}]")
    master.close()


@pytest.fixture(scope="session")
def schema():
    """Once per test run: an empty test database with the real migrations applied."""
    recreate_database(db.parse_url(TEST_DATABASE_URL)["database"])
    conn = db.connect(TEST_DATABASE_URL)
    migrate.apply_pending(conn, MIGRATIONS_DIR)
    conn.close()


@pytest.fixture
def conn(schema):
    """A connection to the test database with no decks and no cards."""
    c = db.connect(TEST_DATABASE_URL)
    cur = c.cursor()
    cur.execute("DELETE FROM cards")
    cur.execute("DELETE FROM decks")
    c.commit()
    yield c
    c.close()


@pytest.fixture
def app(conn):
    return create_app({"DATABASE_URL": TEST_DATABASE_URL})


@pytest.fixture
def client(app):
    return app.test_client()
