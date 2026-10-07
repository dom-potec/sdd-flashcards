"""Study pages. The one module that calls both repositories: Content for card
text, Scheduling for what is due and for recording grades."""

from datetime import date

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for

from ..content import repository as content
from ..db import get_conn
from . import repository as scheduling

bp = Blueprint("study", __name__)

GRADES = [
    (0, "Blackout"),
    (1, "Wrong"),
    (2, "Almost"),
    (3, "Hard"),
    (4, "Good"),
    (5, "Easy"),
]


def conn():
    if "conn" not in g:
        g.conn = get_conn(current_app.config["DB_PATH"])
    return g.conn


@bp.get("/study/<int:deck_id>")
def study(deck_id):
    deck = content.get_deck(conn(), deck_id)
    if deck is None:
        abort(404)
    ids = content.list_card_ids(conn(), deck_id)
    due = scheduling.due_card_ids(conn(), ids, date.today())
    if not due:
        return render_template("study.html", deck=deck, done=True)
    card = content.get_card(conn(), due[0])
    reveal = request.args.get("reveal") == "1"
    return render_template(
        "study.html", deck=deck, done=False, card=card, reveal=reveal, remaining=len(due), grades=GRADES
    )


@bp.post("/study/<int:deck_id>/review")
def review(deck_id):
    card_id = request.form.get("card_id", type=int)
    grade = request.form.get("grade", type=int)
    card = content.get_card(conn(), card_id) if card_id is not None else None
    if card is None or card["deck_id"] != deck_id or grade is None:
        abort(400)
    try:
        scheduling.record_review(conn(), card_id, grade, date.today())
    except ValueError:
        abort(400)
    return redirect(url_for("study.study", deck_id=deck_id))
