from datetime import date, timedelta

import pytest

from app import content_client, create_app, repository

UI = "http://localhost:8080"
DECK = 7
CARDS = [
    {"id": 101, "deck_id": DECK, "front": "hola", "back": "hello", "created_at": "2026-11-12T14:24:03Z"},
    {"id": 102, "deck_id": DECK, "front": "adios", "back": "bye", "created_at": "2026-11-12T14:24:04Z"},
]
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


@pytest.fixture
def content_up(monkeypatch):
    """Content answers: deck 7 has two cards, every other deck does not exist."""
    def list_cards(deck_id):
        if deck_id != DECK:
            raise content_client.DeckNotFound(deck_id)
        return CARDS

    monkeypatch.setattr(content_client, "list_cards", list_cards)


@pytest.fixture
def content_down(monkeypatch):
    def list_cards(deck_id):
        raise content_client.ContentUnavailable("connection refused")

    monkeypatch.setattr(content_client, "list_cards", list_cards)


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok", "db": "ok", "version": "dev"}


def test_health_503_when_the_database_rejects_the_login(app, client):
    app.config["DATABASE_URL"] = "mssql://sa:wrong-password@localhost:1433/scheduling_test"
    res = client.get("/health")
    assert res.status_code == 503
    assert res.get_json() == {"status": "error", "db": "error", "version": "dev"}


def test_health_does_not_depend_on_content(client, content_down):
    assert client.get("/health").status_code == 200


def test_create_app_refuses_to_start_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        create_app()


def test_study_flow_next_review_next_done(client, content_up):
    first = client.get(f"/study/{DECK}/next").get_json()
    assert first == {"done": False, "remaining": 2, "card": {"id": 101, "front": "hola", "back": "hello"}}

    res = client.post("/reviews", json={"card_id": 101, "grade": 5})
    assert res.status_code == 201
    assert res.get_json() == {
        "card_id": 101, "ease_factor": 2.6, "repetitions": 1, "interval_days": 1, "due_at": TOMORROW,
    }

    second = client.get(f"/study/{DECK}/next").get_json()
    assert second == {"done": False, "remaining": 1, "card": {"id": 102, "front": "adios", "back": "bye"}}

    client.post("/reviews", json={"card_id": 102, "grade": 2})
    assert client.get(f"/study/{DECK}/next").get_json() == {"done": True, "remaining": 0}


def test_due_count(client, content_up):
    assert client.get(f"/study/{DECK}/due-count").get_json() == {"deck_id": DECK, "due": 2}
    client.post("/reviews", json={"card_id": 101, "grade": 4})
    assert client.get(f"/study/{DECK}/due-count").get_json() == {"deck_id": DECK, "due": 1}


def test_missing_deck_is_404_json(client, content_up):
    for path in ("/study/999/next", "/study/999/due-count"):
        res = client.get(path)
        assert (res.status_code, res.get_json()) == (404, {"error": "not found"})


def test_study_routes_are_503_json_when_content_is_unavailable(client, content_down):
    for path in (f"/study/{DECK}/next", f"/study/{DECK}/due-count"):
        res = client.get(path)
        assert (res.status_code, res.get_json()) == (503, {"error": "content service unavailable"})


def test_reviews_and_schedule_keep_working_when_content_is_unavailable(client, content_down):
    res = client.post("/reviews", json={"card_id": 101, "grade": 5})
    assert res.status_code == 201
    res = client.get("/cards/101/schedule")
    assert res.status_code == 200
    assert res.get_json()["due_at"] == TOMORROW


def test_schedule_of_a_card_never_reviewed(client):
    assert client.get("/cards/555/schedule").get_json() == {
        "card_id": 555, "ease_factor": 2.5, "repetitions": 0, "interval_days": 0, "due_at": None,
    }


def test_review_with_grade_out_of_range_is_400(client):
    res = client.post("/reviews", json={"card_id": 101, "grade": 7})
    assert (res.status_code, res.get_json()) == (400, {"error": "grade must be 0-5"})
    assert client.get("/cards/101/schedule").get_json()["due_at"] is None


@pytest.mark.parametrize("body", [{"grade": 3}, {"card_id": 101}, {"card_id": "101", "grade": 3},
                                  {"card_id": 101, "grade": True}, ["x"]])
def test_review_with_missing_or_wrong_fields_is_400(client, body):
    res = client.post("/reviews", json=body)
    assert (res.status_code, res.get_json()) == (400, {"error": "card_id and grade must be integers"})


def test_review_without_a_body_is_400_not_415(client):
    assert client.post("/reviews").status_code == 400


def test_unknown_path_and_wrong_method_are_json(client):
    res = client.get("/nope")
    assert (res.status_code, res.get_json()) == (404, {"error": "not found"})
    res = client.get("/reviews")
    assert (res.status_code, res.get_json()) == (405, {"error": "method not allowed"})


def test_unexpected_error_is_500_json(client, monkeypatch):
    def boom(conn, card_id):
        raise RuntimeError("boom")

    monkeypatch.setattr(repository, "get_schedule", boom)
    res = client.get("/cards/101/schedule")
    assert (res.status_code, res.get_json()) == (500, {"error": "internal server error"})


def test_cors_allows_only_the_ui_origin(client):
    allowed = client.get("/cards/101/schedule", headers={"Origin": UI})
    assert allowed.headers.get("Access-Control-Allow-Origin") == UI
    other = client.get("/cards/101/schedule", headers={"Origin": "http://evil.example"})
    assert "Access-Control-Allow-Origin" not in other.headers


def test_each_request_is_logged_once(client, caplog):
    with caplog.at_level("INFO", logger="request"):
        client.get("/cards/101/schedule")
    lines = [r.getMessage() for r in caplog.records if r.name == "request"]
    assert len(lines) == 1
    assert lines[0].startswith("GET /cards/101/schedule 200 ")
