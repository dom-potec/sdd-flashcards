def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_index_redirects_to_decks(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/decks")


def test_create_deck_shows_in_list(client):
    client.post("/decks", data={"name": "Spanish", "description": "verbs"})
    response = client.get("/decks")
    assert response.status_code == 200
    assert b"Spanish" in response.data


def test_study_empty_deck_shows_done(client):
    client.post("/decks", data={"name": "Empty"})
    response = client.get("/study/1")
    assert response.status_code == 200
    assert b"All caught up" in response.data
