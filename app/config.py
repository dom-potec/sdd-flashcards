import os

PORT = int(os.environ.get("PORT", "8000"))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "flashcards.db"))
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")  # needed for flash()
