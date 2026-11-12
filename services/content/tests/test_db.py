import pymssql
import pytest

from app import db


def test_parse_url():
    assert db.parse_url("mssql://bob:s3cret@dbhost:1444/content") == {
        "server": "dbhost", "port": 1444, "user": "bob", "password": "s3cret", "database": "content",
    }


def test_parse_url_defaults_port_and_decodes_password():
    parsed = db.parse_url("mssql://bob:p%40ss%2Fword@dbhost/content")
    assert parsed["port"] == 1433
    assert parsed["password"] == "p@ss/word"


@pytest.mark.parametrize("url", ["sqlite:///x.db", "mssql://bob:pw@/content", "mssql://bob:pw@dbhost"])
def test_parse_url_rejects_other_shapes(url):
    with pytest.raises(ValueError):
        db.parse_url(url)


def test_connect_with_retry_backs_off_then_succeeds(monkeypatch):
    calls, sleeps = [], []

    def fake_connect(url):
        calls.append(url)
        if len(calls) < 4:
            raise pymssql.OperationalError("database is resuming")
        return "connection"

    monkeypatch.setattr(db, "connect", fake_connect)
    monkeypatch.setattr(db.time, "sleep", sleeps.append)
    assert db.connect_with_retry("mssql://u:p@h/d", attempts=8) == "connection"
    assert len(calls) == 4
    assert sleeps == [1, 2, 4]


def test_connect_with_retry_gives_up_after_the_last_attempt(monkeypatch):
    sleeps = []

    def always_fails(url):
        raise pymssql.OperationalError("down")

    monkeypatch.setattr(db, "connect", always_fails)
    monkeypatch.setattr(db.time, "sleep", sleeps.append)
    with pytest.raises(pymssql.OperationalError):
        db.connect_with_retry("mssql://u:p@h/d", attempts=8)
    assert sleeps == [1, 2, 4, 8, 16, 30, 30]
