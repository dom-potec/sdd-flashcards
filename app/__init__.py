from flask import Flask, g, jsonify, redirect, url_for

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

    from .content.routes import bp as content_bp
    from .scheduling.routes import bp as study_bp
    app.register_blueprint(content_bp)
    app.register_blueprint(study_bp)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/")
    def index():
        return redirect(url_for("content.list_decks"))

    @app.teardown_appcontext
    def close_conn(exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    return app
