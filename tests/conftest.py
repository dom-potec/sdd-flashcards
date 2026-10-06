import pytest

from app.db import get_conn, init_db


@pytest.fixture
def conn(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    c = get_conn(db)
    yield c
    c.close()


@pytest.fixture
def client(tmp_path):
    from app import create_app

    app = create_app({"DB_PATH": str(tmp_path / "app.db"), "TESTING": True})
    return app.test_client()
