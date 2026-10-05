from flask import Flask, g, jsonify

from . import config
from .db import init_db


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY,
        DB_PATH=config.DB_PATH,
    )
    if test_config:
        app.config.update(test_config)

    init_db(app.config["DB_PATH"])

    # TODO(block 10/11): register the content and study blueprints and the "/" redirect

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.teardown_appcontext
    def close_conn(exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    return app
