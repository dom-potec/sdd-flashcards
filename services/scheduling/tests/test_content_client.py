import pytest
import requests
from flask import Flask

from app import content_client


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self.body = body

    def json(self):
        if self.body is None:
            raise ValueError("no JSON")
        return self.body


@pytest.fixture
def calls(monkeypatch):
    """Runs the test inside an app context with a CONTENT_URL, and records every requests.get call.
    Set calls.result to the response to return or the exception to raise."""
    app = Flask(__name__)
    app.config.update(CONTENT_URL="http://content.test:8000/", CONTENT_TIMEOUT_S=2.0)

    class Calls(list):
        result = None

    recorded = Calls()

    def fake_get(url, **kwargs):
        recorded.append((url, kwargs))
        if isinstance(recorded.result, Exception):
            raise recorded.result
        return recorded.result

    monkeypatch.setattr(requests, "get", fake_get)
    with app.app_context():
        yield recorded


def test_200_returns_the_cards(calls):
    cards = [{"id": 1, "deck_id": 7, "front": "hola", "back": "hello"}]
    calls.result = FakeResponse(200, cards)
    assert content_client.list_cards(7) == cards


def test_calls_the_cards_endpoint_with_the_configured_timeout(calls):
    calls.result = FakeResponse(200, [])
    content_client.list_cards(7)
    assert calls == [("http://content.test:8000/decks/7/cards", {"timeout": 2.0})]


def test_404_means_deck_not_found(calls):
    calls.result = FakeResponse(404, {"error": "not found"})
    with pytest.raises(content_client.DeckNotFound):
        content_client.list_cards(7)


@pytest.mark.parametrize("status", [500, 503, 302])
def test_any_other_status_means_content_unavailable(calls, status):
    calls.result = FakeResponse(status, {"error": "x"})
    with pytest.raises(content_client.ContentUnavailable):
        content_client.list_cards(7)


@pytest.mark.parametrize("error", [requests.Timeout("slow"), requests.ConnectionError("refused")])
def test_timeout_or_connection_error_means_content_unavailable(calls, error):
    calls.result = error
    with pytest.raises(content_client.ContentUnavailable):
        content_client.list_cards(7)


def test_200_that_is_not_json_means_content_unavailable(calls):
    calls.result = FakeResponse(200, None)
    with pytest.raises(content_client.ContentUnavailable):
        content_client.list_cards(7)
