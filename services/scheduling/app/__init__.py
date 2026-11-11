"""Scheduling service: SM-2 state, the reviews log and what is due. create_app() configures the app,
applies pending migrations, restricts CORS to the UI origin and exposes /health."""

from flask import Flask, g, jsonify
from flask_cors import CORS

from . import config, db, migrate
from .logging_ import configure_logging, init_request_logging


def create_app(test_config: dict | None = None) -> Flask:
    configure_logging()
    app = Flask(__name__)
    app.config.update(config.from_env())
    if test_config:
        app.config.update(test_config)
    if not app.config["DATABASE_URL"]:
        raise RuntimeError("DATABASE_URL is not set")

    conn = db.connect_with_retry(app.config["DATABASE_URL"], app.config["DB_CONNECT_ATTEMPTS"])
    try:
        migrate.apply_pending(conn, app.config["MIGRATIONS_DIR"])
    finally:
        conn.close()

    CORS(app, origins=[app.config["UI_ORIGIN"]], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    init_request_logging(app)

    @app.get("/health")
    def health():
        """200 only if this service can read and write its own database. Never looks at other services."""
        version = app.config["GIT_SHA"]
        try:
            conn = db.connect(app.config["DATABASE_URL"])  # single attempt: health must answer fast
            try:
                cur = conn.cursor()
                cur.execute("UPDATE health_probe SET checked_at = SYSUTCDATETIME() WHERE id = 1")
                conn.commit()
                cur.execute("SELECT checked_at FROM health_probe WHERE id = 1")
                if cur.fetchone() is None:
                    raise RuntimeError("health_probe row missing")
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001 - any failure means unhealthy
            app.logger.warning("health check failed: %s", e)
            return jsonify(status="error", db="error", version=version), 503
        return jsonify(status="ok", db="ok", version=version), 200

    @app.teardown_appcontext
    def close_conn(exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    return app
