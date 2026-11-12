"""JSON API for decks and cards. Each route parses the request, calls the repository and picks a status."""

from flask import Blueprint, jsonify, request

from . import repository
from .db import request_conn

bp = Blueprint("content", __name__)


def body_text(key: str) -> str:
    """The string under `key` in the JSON body, or "" when the body or the key is missing or not a string."""
    data = request.get_json(silent=True)
    value = data.get(key) if isinstance(data, dict) else None
    return value if isinstance(value, str) else ""


def as_json(row: dict) -> dict:
    """A deck or card row with created_at as an ISO 8601 UTC string instead of a datetime."""
    return {**row, "created_at": row["created_at"].isoformat(timespec="seconds") + "Z"}


def not_found():
    return jsonify(error="not found"), 404


def bad_request(error: ValueError):
    return jsonify(error=str(error)), 400


@bp.get("/decks")
def list_decks():
    return jsonify([as_json(deck) for deck in repository.list_decks(request_conn())])


@bp.post("/decks")
def create_deck():
    conn = request_conn()
    try:
        deck_id = repository.create_deck(conn, body_text("name"), body_text("description"))
    except ValueError as e:
        return bad_request(e)
    return jsonify(as_json(repository.get_deck(conn, deck_id))), 201


@bp.get("/decks/<int:deck_id>")
def get_deck(deck_id: int):
    deck = repository.get_deck(request_conn(), deck_id)
    if deck is None:
        return not_found()
    return jsonify(as_json(deck))


@bp.delete("/decks/<int:deck_id>")
def delete_deck(deck_id: int):
    if not repository.delete_deck(request_conn(), deck_id):
        return not_found()
    return "", 204


@bp.get("/decks/<int:deck_id>/cards")
def list_cards(deck_id: int):
    """The one endpoint the scheduling service calls: all cards of a deck, ordered by id."""
    conn = request_conn()
    if repository.get_deck(conn, deck_id) is None:
        return not_found()
    return jsonify([as_json(card) for card in repository.list_cards(conn, deck_id)])


@bp.post("/decks/<int:deck_id>/cards")
def create_card(deck_id: int):
    conn = request_conn()
    try:
        card_id = repository.create_card(conn, deck_id, body_text("front"), body_text("back"))
    except ValueError as e:
        return bad_request(e)
    except LookupError:
        return not_found()
    return jsonify(as_json(repository.get_card(conn, card_id))), 201


@bp.get("/cards/<int:card_id>")
def get_card(card_id: int):
    card = repository.get_card(request_conn(), card_id)
    if card is None:
        return not_found()
    return jsonify(as_json(card))


@bp.put("/cards/<int:card_id>")
def update_card(card_id: int):
    conn = request_conn()
    try:
        updated = repository.update_card(conn, card_id, body_text("front"), body_text("back"))
    except ValueError as e:
        return bad_request(e)
    if not updated:
        return not_found()
    return jsonify(as_json(repository.get_card(conn, card_id)))


@bp.delete("/cards/<int:card_id>")
def delete_card(card_id: int):
    if not repository.delete_card(request_conn(), card_id):
        return not_found()
    return "", 204
