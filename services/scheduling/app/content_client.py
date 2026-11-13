"""The only code in this service that talks to the content service.

One HTTP call, always with a timeout. Any way the call can fail becomes one of two exceptions,
so the routes never see the requests library."""

import requests
from flask import current_app


class ContentUnavailable(Exception):
    """Content did not answer in time, could not be reached, or answered with something unexpected."""


class DeckNotFound(Exception):
    """Content answered: there is no such deck."""


def list_cards(deck_id: int) -> list[dict]:
    """GET {CONTENT_URL}/decks/{deck_id}/cards: the deck's cards as dicts with id, front and back."""
    url = f"{current_app.config['CONTENT_URL'].rstrip('/')}/decks/{deck_id}/cards"
    try:
        response = requests.get(url, timeout=current_app.config["CONTENT_TIMEOUT_S"])
    except requests.RequestException as e:  # timeout, connection refused, DNS failure
        raise ContentUnavailable(str(e)) from e
    if response.status_code == 404:
        raise DeckNotFound(deck_id)
    if response.status_code != 200:
        raise ContentUnavailable(f"content returned {response.status_code}")
    try:
        return response.json()
    except ValueError as e:  # a 200 whose body is not JSON
        raise ContentUnavailable("content returned a body that is not JSON") from e
