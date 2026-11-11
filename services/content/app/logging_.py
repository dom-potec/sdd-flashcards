"""One log line per request on stdout: method, path, status, duration."""

import logging
import sys
import time

from flask import Flask, g, request

log = logging.getLogger("request")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


def init_request_logging(app: Flask) -> None:
    @app.before_request
    def start_timer():
        g.started = time.perf_counter()

    @app.after_request
    def log_request(response):
        ms = (time.perf_counter() - g.get("started", time.perf_counter())) * 1000
        log.info("%s %s %s %.1fms", request.method, request.path, response.status_code, ms)
        return response
