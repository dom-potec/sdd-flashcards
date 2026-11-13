"""JSON API for studying. The /study routes need the content service (through content_client);
/reviews and /cards/<id>/schedule use only this service's own database and keep working without it."""

from datetime import date

from flask import Blueprint, jsonify, request

from . import content_client, repository
from .db import request_conn

bp = Blueprint("scheduling", __name__)


def body_int(key: str) -> int | None:
    """The integer under `key` in the JSON body, or None when it is missing or not an integer."""
    data = request.get_json(silent=True)
    value = data.get(key) if isinstance(data, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def schedule_json(schedule: dict) -> dict:
    """A schedule row with due_at as an ISO date string (or null for a card never reviewed)."""
    due_at = schedule["due_at"]
    return {**schedule, "due_at": due_at.isoformat() if due_at else None}


@bp.get("/study/<int:deck_id>/next")
def next_card(deck_id: int):
    """The next card to study in a deck, with its text. The cards come from content over HTTP."""
    cards = content_client.list_cards(deck_id)
    due = repository.due_card_ids(request_conn(), [card["id"] for card in cards], date.today())
    if not due:
        return jsonify(done=True, remaining=0)
    card = next(card for card in cards if card["id"] == due[0])
    return jsonify(
        done=False,
        remaining=len(due),
        card={"id": card["id"], "front": card["front"], "back": card["back"]},
    )


@bp.get("/study/<int:deck_id>/due-count")
def due_count(deck_id: int):
    cards = content_client.list_cards(deck_id)
    due = repository.count_due(request_conn(), [card["id"] for card in cards], date.today())
    return jsonify(deck_id=deck_id, due=due)


@bp.post("/reviews")
def create_review():
    """Record a grade. Deliberately does not ask content whether the card exists (see ADR-7):
    this write has to keep working while content is down."""
    card_id = body_int("card_id")
    grade = body_int("grade")
    if card_id is None or grade is None:
        return jsonify(error="card_id and grade must be integers"), 400
    conn = request_conn()
    try:
        repository.record_review(conn, card_id, grade, date.today())
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(schedule_json(repository.get_schedule(conn, card_id))), 201


@bp.get("/cards/<int:card_id>/schedule")
def get_schedule(card_id: int):
    return jsonify(schedule_json(repository.get_schedule(request_conn(), card_id)))
