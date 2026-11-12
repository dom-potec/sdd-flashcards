import pytest

from app import db, migrate
from tests.conftest import MIGRATIONS_DIR, recreate_database, url_for_database

SCRATCH = "content_migrate_test"


@pytest.fixture
def fresh_conn():
    """A connection to a database that has no tables at all."""
    recreate_database(SCRATCH)
    c = db.connect(url_for_database(SCRATCH))
    yield c
    c.close()


def table_exists(conn, name: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT OBJECT_ID(%s) AS id", (name,))
    return cur.fetchone()["id"] is not None


def test_fresh_database_gets_001_init(fresh_conn):
    assert migrate.apply_pending(fresh_conn, MIGRATIONS_DIR) == ["001_init"]
    assert table_exists(fresh_conn, "decks")
    assert table_exists(fresh_conn, "cards")
    assert table_exists(fresh_conn, "health_probe")


def test_second_run_applies_nothing(fresh_conn):
    migrate.apply_pending(fresh_conn, MIGRATIONS_DIR)
    assert migrate.apply_pending(fresh_conn, MIGRATIONS_DIR) == []
    cur = fresh_conn.cursor()
    cur.execute("SELECT version FROM schema_migrations")
    assert [row["version"] for row in cur.fetchall()] == ["001_init"]


def test_migrations_run_in_name_order_and_only_new_ones(fresh_conn, tmp_path):
    (tmp_path / "002_second.sql").write_text("ALTER TABLE things ADD note NVARCHAR(50) NULL;")
    (tmp_path / "001_first.sql").write_text("CREATE TABLE things (id INT PRIMARY KEY);")
    assert migrate.apply_pending(fresh_conn, str(tmp_path)) == ["001_first", "002_second"]
    (tmp_path / "003_third.sql").write_text("CREATE TABLE more_things (id INT PRIMARY KEY);")
    assert migrate.apply_pending(fresh_conn, str(tmp_path)) == ["003_third"]


def test_go_lets_a_migration_use_the_column_it_just_added(fresh_conn, tmp_path):
    (tmp_path / "001_first.sql").write_text(
        "CREATE TABLE things (id INT PRIMARY KEY);\nINSERT INTO things (id) VALUES (1);"
    )
    (tmp_path / "002_add.sql").write_text(
        "ALTER TABLE things ADD score INT NOT NULL DEFAULT 0;\nGO\nUPDATE things SET score = 7;"
    )
    migrate.apply_pending(fresh_conn, str(tmp_path))
    cur = fresh_conn.cursor()
    cur.execute("SELECT id, score FROM things")
    assert cur.fetchall() == [{"id": 1, "score": 7}]


def test_failing_migration_is_rolled_back_and_not_recorded(fresh_conn, tmp_path):
    (tmp_path / "001_bad.sql").write_text(
        "CREATE TABLE half_done (id INT PRIMARY KEY);\nGO\nINSERT INTO no_such_table (id) VALUES (1);"
    )
    with pytest.raises(Exception):
        migrate.apply_pending(fresh_conn, str(tmp_path))
    assert not table_exists(fresh_conn, "half_done")
    cur = fresh_conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM schema_migrations")
    assert cur.fetchone()["n"] == 0


def test_split_batches_splits_on_go_lines():
    sql = "CREATE TABLE a (id INT);\nGO\nINSERT INTO a VALUES (1);\n  go  \nSELECT 1;"
    assert migrate.split_batches(sql) == [
        "CREATE TABLE a (id INT);",
        "INSERT INTO a VALUES (1);",
        "SELECT 1;",
    ]


def test_split_batches_ignores_blank_batches():
    assert migrate.split_batches("GO\n\nGO\nSELECT 1;\nGO\n   \n") == ["SELECT 1;"]
    assert migrate.split_batches("SELECT 'GOAL';") == ["SELECT 'GOAL';"]
