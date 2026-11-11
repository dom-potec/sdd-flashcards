FROM python:3.12-slim

ENV PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Unprivileged user: the process never runs as root.
RUN useradd --create-home --uid 10001 appuser

# Dependencies first, source second: editing a .py file does not reinstall every package (layer cache).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Only what the service needs to run. No tests, no dev requirements, no .env, never `COPY . .`.
COPY app.py gunicorn.conf.py ./
COPY app/ ./app/
COPY migrations/ ./migrations/

USER appuser

EXPOSE 8000

# `docker compose up --wait` and CI wait on this. Python stdlib only: the slim image has no curl.
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=6 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health', timeout=3)" || exit 1

CMD ["gunicorn", "app:create_app()"]
