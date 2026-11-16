"""Integration tests across the two services, over real HTTP, against the docker compose stack.

Start the stack first: `docker compose up --build --wait`. Nothing is stubbed here: scheduling really
calls content. The outage test stops the content container, so it only runs with RUN_FAILURE_TEST=1."""

import os
import subprocess
import time

import pytest
import requests

CONTENT = os.environ.get("CONTENT_BASE", "http://localhost:8000")
SCHEDULING = os.environ.get("SCHEDULING_BASE", "http://localhost:8001")
REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
TIMEOUT = 10  # seconds; every call in a test has a timeout too


def create_deck_with_cards(*cards: tuple[str, str]) -> tuple[int, list[int]]:
    """Create a deck in content with the given (front, back) cards. Returns (deck id, card ids)."""
    deck = requests.post(f"{CONTENT}/decks", json={"name": "Integration"}, timeout=TIMEOUT)
    assert deck.status_code == 201
    deck_id = deck.json()["id"]
    card_ids = []
    for front, back in cards:
        card = requests.post(
            f"{CONTENT}/decks/{deck_id}/cards", json={"front": front, "back": back}, timeout=TIMEOUT
        )
        assert card.status_code == 201
        card_ids.append(card.json()["id"])
    return deck_id, card_ids


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], cwd=REPO_ROOT, check=True, capture_output=True)


def wait_until_healthy(base: str, seconds: int = 90) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if requests.get(f"{base}/health", timeout=3).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise AssertionError(f"{base}/health did not return 200 within {seconds}s")


def test_study_flow_across_services():
    deck_id, (first, second) = create_deck_with_cards(("hola", "hello"), ("adios", "bye"))
    try:
        # The card text was written to content only; scheduling can only know it by calling content.
        res = requests.get(f"{SCHEDULING}/study/{deck_id}/next", timeout=TIMEOUT)
        assert res.status_code == 200
        assert res.json() == {
            "done": False, "remaining": 2, "card": {"id": first, "front": "hola", "back": "hello"},
        }
        assert requests.get(f"{SCHEDULING}/study/{deck_id}/due-count", timeout=TIMEOUT).json()["due"] == 2

        res = requests.post(f"{SCHEDULING}/reviews", json={"card_id": first, "grade": 5}, timeout=TIMEOUT)
        assert res.status_code == 201
        assert res.json()["interval_days"] == 1

        res = requests.get(f"{SCHEDULING}/study/{deck_id}/next", timeout=TIMEOUT)
        assert res.json() == {
            "done": False, "remaining": 1, "card": {"id": second, "front": "adios", "back": "bye"},
        }

        res = requests.post(f"{SCHEDULING}/reviews", json={"card_id": second, "grade": 4}, timeout=TIMEOUT)
        assert res.status_code == 201

        res = requests.get(f"{SCHEDULING}/study/{deck_id}/next", timeout=TIMEOUT)
        assert res.json() == {"done": True, "remaining": 0}
        res = requests.get(f"{SCHEDULING}/study/{deck_id}/due-count", timeout=TIMEOUT)
        assert res.json() == {"deck_id": deck_id, "due": 0}
    finally:
        requests.delete(f"{CONTENT}/decks/{deck_id}", timeout=TIMEOUT)


def test_deck_unknown_to_content_is_404_from_scheduling():
    res = requests.get(f"{SCHEDULING}/study/999999999/next", timeout=TIMEOUT)
    assert res.status_code == 404
    assert res.json() == {"error": "not found"}


@pytest.mark.skipif(
    os.environ.get("RUN_FAILURE_TEST") != "1", reason="stops the content container; set RUN_FAILURE_TEST=1"
)
def test_content_down_is_handled():
    deck_id, (card_id,) = create_deck_with_cards(("hola", "hello"))
    compose("stop", "content")
    try:
        started = time.monotonic()
        res = requests.get(f"{SCHEDULING}/study/{deck_id}/next", timeout=TIMEOUT)
        elapsed = time.monotonic() - started
        assert res.status_code == 503
        assert res.json() == {"error": "content service unavailable"}
        assert elapsed < 4  # the 2 s timeout plus margin: scheduling fails fast, it does not hang

        # Scheduling's own data keeps working while content is down.
        res = requests.post(f"{SCHEDULING}/reviews", json={"card_id": card_id, "grade": 5}, timeout=TIMEOUT)
        assert res.status_code == 201
        assert requests.get(f"{SCHEDULING}/cards/{card_id}/schedule", timeout=TIMEOUT).status_code == 200
        # Health is about the service's own database, not about content.
        assert requests.get(f"{SCHEDULING}/health", timeout=TIMEOUT).status_code == 200
    finally:
        compose("start", "content")
        wait_until_healthy(CONTENT)
    # After content is back, the study routes work again without restarting scheduling.
    res = requests.get(f"{SCHEDULING}/study/{deck_id}/next", timeout=TIMEOUT)
    assert res.status_code == 200
    requests.delete(f"{CONTENT}/decks/{deck_id}", timeout=TIMEOUT)
