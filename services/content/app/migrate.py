"""Forward-only SQL migrations: numbered files applied in order, each recorded once in schema_migrations."""

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def split_batches(sql: str) -> list[str]:
    """Split on lines that are exactly GO, like sqlcmd does. T-SQL compiles a whole batch before running it,
    so an ALTER TABLE that adds a column and an UPDATE that uses it must be separate batches."""
    batches, current = [], []
    for line in sql.splitlines():
        if line.strip().upper() == "GO":
            batches.append("\n".join(current))
            current = []
        else:
            current.append(line)
    batches.append("\n".join(current))
    return [b for b in batches if b.strip()]


def apply_pending(conn, migrations_dir: str) -> list[str]:
    """Apply every *.sql in migrations_dir, in name order, that is not yet in schema_migrations.
    One transaction per migration: all of its batches run, or none. Returns the versions applied."""
    cur = conn.cursor()
    cur.execute(
        """
        IF OBJECT_ID('schema_migrations') IS NULL
            CREATE TABLE schema_migrations (
                version    NVARCHAR(100) PRIMARY KEY,
                applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            )
        """
    )
    conn.commit()
    cur.execute("SELECT version FROM schema_migrations")
    applied = {row["version"] for row in cur.fetchall()}

    done = []
    for path in sorted(Path(migrations_dir).glob("*.sql")):
        version = path.stem  # "001_init"
        if version in applied:
            continue
        try:
            for batch in split_batches(path.read_text()):
                cur.execute(batch)
            cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            conn.commit()
        except Exception:
            conn.rollback()
            log.error("migration %s failed and was rolled back", version)
            raise
        log.info("applied migration %s", version)
        done.append(version)
    if not done:
        log.info("no pending migrations")
    return done
