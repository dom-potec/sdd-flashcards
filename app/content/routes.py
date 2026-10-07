from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from ..db import get_conn
from . import repository

bp = Blueprint("content", __name__)


def conn():
    if "conn" not in g:
        g.conn = get_conn(current_app.config["DB_PATH"])
    return g.conn


@bp.get("/decks")
def list_decks():
    decks = repository.list_decks(conn())
    return render_template("decks.html", decks=decks)


@bp.post("/decks")
def create_deck():
    try:
        repository.create_deck(conn(), request.form.get("name", ""), request.form.get("description", ""))
    except ValueError as e:
        flash(str(e))
    return redirect(url_for("content.list_decks"))


@bp.get("/decks/<int:deck_id>")
def show_deck(deck_id):
    deck = repository.get_deck(conn(), deck_id)
    if deck is None:
        abort(404)
    cards = repository.list_cards(conn(), deck_id)
    return render_template("deck.html", deck=deck, cards=cards)


@bp.post("/decks/<int:deck_id>/cards")
def create_card(deck_id):
    try:
        repository.create_card(conn(), deck_id, request.form.get("front", ""), request.form.get("back", ""))
    except ValueError as e:
        flash(str(e))
    except LookupError:
        abort(404)
    return redirect(url_for("content.show_deck", deck_id=deck_id))


@bp.post("/decks/<int:deck_id>/delete")
def delete_deck(deck_id):
    repository.delete_deck(conn(), deck_id)
    return redirect(url_for("content.list_decks"))


@bp.post("/cards/<int:card_id>/delete")
def delete_card(card_id):
    card = repository.get_card(conn(), card_id)
    if card is None:
        abort(404)
    repository.delete_card(conn(), card_id)
    return redirect(url_for("content.show_deck", deck_id=card["deck_id"]))
