import pytest

from app import create_app, repository

UI = "http://localhost:8080"


def make_deck(client, name="Spanish"):
    return client.post("/decks", json={"name": name}).get_json()["id"]


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok", "db": "ok", "version": "dev"}


def test_health_503_when_the_database_rejects_the_login(app, client):
    app.config["DATABASE_URL"] = "mssql://sa:wrong-password@localhost:1433/content_test"
    res = client.get("/health")
    assert res.status_code == 503
    assert res.get_json() == {"status": "error", "db": "error", "version": "dev"}


def test_create_app_refuses_to_start_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        create_app()


def test_create_deck_then_list_shows_it(client):
    res = client.post("/decks", json={"name": " Spanish ", "description": "verbs"})
    assert res.status_code == 201
    deck = res.get_json()
    assert deck["name"] == "Spanish"
    assert deck["description"] == "verbs"
    assert deck["card_count"] == 0
    assert deck["created_at"].endswith("Z")
    assert client.get("/decks").get_json() == [deck]
    assert client.get(f"/decks/{deck['id']}").get_json() == deck


def test_blank_deck_name_is_400_json(client):
    res = client.post("/decks", json={"name": "   "})
    assert res.status_code == 400
    assert res.get_json() == {"error": "deck name must not be blank"}
    assert client.get("/decks").get_json() == []


def test_missing_or_non_json_body_is_400_not_415(client):
    assert client.post("/decks").status_code == 400
    assert client.post("/decks", data="name=Spanish").status_code == 400
    assert client.post("/decks", json={"name": 5}).status_code == 400
    assert client.post("/decks", json=["Spanish"]).status_code == 400


def test_missing_deck_is_404_json(client):
    for path in ("/decks/999", "/decks/999/cards"):
        res = client.get(path)
        assert res.status_code == 404
        assert res.get_json() == {"error": "not found"}
    assert client.delete("/decks/999").status_code == 404


def test_create_card_then_list_cards(client):
    deck_id = make_deck(client)
    res = client.post(f"/decks/{deck_id}/cards", json={"front": "hola", "back": "hello"})
    assert res.status_code == 201
    card = res.get_json()
    assert set(card) == {"id", "deck_id", "front", "back", "created_at"}
    assert (card["deck_id"], card["front"], card["back"]) == (deck_id, "hola", "hello")
    second = client.post(f"/decks/{deck_id}/cards", json={"front": "adios", "back": "bye"}).get_json()
    assert client.get(f"/decks/{deck_id}/cards").get_json() == [card, second]
    assert client.get(f"/cards/{card['id']}").get_json() == card
    assert client.get(f"/decks/{deck_id}").get_json()["card_count"] == 2


def test_create_card_errors(client):
    deck_id = make_deck(client)
    res = client.post(f"/decks/{deck_id}/cards", json={"front": "hola"})
    assert res.status_code == 400
    assert res.get_json() == {"error": "card front and back must not be blank"}
    assert client.post("/decks/999/cards", json={"front": "a", "back": "b"}).status_code == 404


def test_update_card(client):
    deck_id = make_deck(client)
    card_id = client.post(f"/decks/{deck_id}/cards", json={"front": "hola", "back": "hello"}).get_json()["id"]
    res = client.put(f"/cards/{card_id}", json={"front": "hola", "back": "hi"})
    assert res.status_code == 200
    assert res.get_json()["back"] == "hi"
    assert client.put(f"/cards/{card_id}", json={"front": "", "back": "hi"}).status_code == 400
    assert client.put("/cards/999", json={"front": "a", "back": "b"}).status_code == 404


def test_delete_card(client):
    deck_id = make_deck(client)
    card_id = client.post(f"/decks/{deck_id}/cards", json={"front": "hola", "back": "hello"}).get_json()["id"]
    res = client.delete(f"/cards/{card_id}")
    assert res.status_code == 204
    assert res.data == b""
    assert client.get(f"/cards/{card_id}").status_code == 404
    assert client.delete(f"/cards/{card_id}").status_code == 404


def test_delete_deck_then_its_cards_are_gone(client):
    deck_id = make_deck(client)
    card_id = client.post(f"/decks/{deck_id}/cards", json={"front": "hola", "back": "hello"}).get_json()["id"]
    assert client.delete(f"/decks/{deck_id}").status_code == 204
    assert client.get(f"/decks/{deck_id}/cards").status_code == 404
    assert client.get(f"/cards/{card_id}").status_code == 404


def test_unknown_path_and_wrong_method_are_json(client):
    res = client.get("/nope")
    assert (res.status_code, res.get_json()) == (404, {"error": "not found"})
    res = client.patch("/decks")
    assert (res.status_code, res.get_json()) == (405, {"error": "method not allowed"})


def test_unexpected_error_is_500_json(client, monkeypatch):
    def boom(conn):
        raise RuntimeError("boom")

    monkeypatch.setattr(repository, "list_decks", boom)
    res = client.get("/decks")
    assert (res.status_code, res.get_json()) == (500, {"error": "internal server error"})


def test_cors_allows_only_the_ui_origin(client):
    allowed = client.get("/decks", headers={"Origin": UI})
    assert allowed.headers.get("Access-Control-Allow-Origin") == UI
    other = client.get("/decks", headers={"Origin": "http://evil.example"})
    assert "Access-Control-Allow-Origin" not in other.headers


def test_cors_preflight_for_the_ui_origin(client):
    res = client.options(
        "/decks", headers={"Origin": UI, "Access-Control-Request-Method": "POST",
                           "Access-Control-Request-Headers": "Content-Type"},
    )
    assert res.headers.get("Access-Control-Allow-Origin") == UI
    assert "POST" in res.headers.get("Access-Control-Allow-Methods", "")


def test_each_request_is_logged_once(client, caplog):
    with caplog.at_level("INFO", logger="request"):
        client.get("/decks")
    lines = [r.getMessage() for r in caplog.records if r.name == "request"]
    assert len(lines) == 1
    assert lines[0].startswith("GET /decks 200 ")
