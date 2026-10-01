from flask import Flask, jsonify

from . import config


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY,
        DB_PATH=config.DB_PATH,
    )
    if test_config:
        app.config.update(test_config)

    # TODO(block 4): init_db(app.config["DB_PATH"]) and teardown that closes g.conn
    # TODO(block 10/11): register the content and study blueprints and the "/" redirect

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app
