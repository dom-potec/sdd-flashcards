"""Gunicorn settings for the container. `gunicorn app:create_app()` reads this file."""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = 1          # migrations run inside create_app; one worker means they run once per boot
threads = 4
timeout = 180        # a cold start (container + Azure SQL resuming from pause) can take over a minute
accesslog = None     # the app writes its own one-line-per-request log
