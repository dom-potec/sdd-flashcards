from datetime import date, timedelta

import pytest

from app.content import repository as content
from app.scheduling import repository as s
from app.scheduling.sm2 import ScheduleState

TODAY = date(2026, 10, 8)
TOMORROW = TODAY + timedelta(days=1)


@pytest.fixture
def deck(conn):
    """A deck with three cards; returns (deck_id, [card ids])."""
    deck_id = content.create_deck(conn, "Spanish")
    ids = [content.create_card(conn, deck_id, f"front {i}", f"back {i}") for i in range(3)]
    return deck_id, ids


def test_get_state_default_when_never_reviewed(conn, deck):
    _, ids = deck
    assert s.get_state(conn, ids[0]) == ScheduleState()


def test_record_review_inserts_schedule_and_review_row(conn, deck):
    _, ids = deck
    state = s.record_review(conn, ids[0], 5, TODAY)
    assert state == ScheduleState(ease_factor=2.6, repetitions=1, interval_days=1)
    row = conn.execute("SELECT * FROM card_schedule WHERE card_id = ?", (ids[0],)).fetchone()
    assert row["repetitions"] == 1
    assert row["interval_days"] == 1
    assert row["due_at"] == TOMORROW.isoformat()
    review = conn.execute("SELECT * FROM reviews WHERE card_id = ?", (ids[0],)).fetchone()
    assert review["grade"] == 5
    assert review["interval_before"] == 0
    assert review["interval_after"] == 1


def test_second_review_uses_stored_state(conn, deck):
    _, ids = deck
    s.record_review(conn, ids[0], 5, TODAY)
    state = s.record_review(conn, ids[0], 4, TOMORROW)
    assert state.repetitions == 2
    assert state.interval_days == 6
    assert s.get_state(conn, ids[0]) == state
    assert conn.execute("SELECT COUNT(*) FROM card_schedule").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 2


def test_lapse_resets_repetitions(conn, deck):
    _, ids = deck
    s.record_review(conn, ids[0], 5, TODAY)
    s.record_review(conn, ids[0], 4, TOMORROW)
    state = s.record_review(conn, ids[0], 1, TOMORROW)
    assert state.repetitions == 0
    assert state.interval_days == 1
    assert state.ease_factor == pytest.approx(2.6)


def test_invalid_grade_writes_nothing(conn, deck):
    _, ids = deck
    with pytest.raises(ValueError):
        s.record_review(conn, ids[0], 6, TODAY)
    assert conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 0
    assert s.get_state(conn, ids[0]) == ScheduleState()


def test_new_card_is_due(conn, deck):
    _, ids = deck
    assert s.due_card_ids(conn, ids, TODAY) == ids


def test_future_card_not_due(conn, deck):
    _, ids = deck
    s.record_review(conn, ids[0], 5, TODAY)  # due tomorrow
    assert s.due_card_ids(conn, ids, TODAY) == ids[1:]


def test_past_card_is_due(conn, deck):
    _, ids = deck
    s.record_review(conn, ids[0], 5, TODAY - timedelta(days=3))  # was due two days ago
    assert ids[0] in s.due_card_ids(conn, ids, TODAY)


def test_due_ordering_new_then_oldest(conn, deck):
    _, ids = deck
    s.record_review(conn, ids[0], 3, TODAY - timedelta(days=2))  # due yesterday
    s.record_review(conn, ids[1], 3, TODAY - timedelta(days=5))  # due four days ago
    # ids[2] never reviewed -> first; then ids[1] (older due date); then ids[0]
    assert s.due_card_ids(conn, ids, TODAY) == [ids[2], ids[1], ids[0]]


def test_due_card_ids_empty_input(conn):
    assert s.due_card_ids(conn, [], TODAY) == []


def test_count_due(conn, deck):
    _, ids = deck
    assert s.count_due(conn, ids, TODAY) == 3
    s.record_review(conn, ids[0], 5, TODAY)
    assert s.count_due(conn, ids, TODAY) == 2


def test_ids_from_other_decks_ignored(conn, deck):
    _, ids = deck
    other = content.create_deck(conn, "Chem")
    other_card = content.create_card(conn, other, "H2O", "water")
    assert other_card not in s.due_card_ids(conn, ids, TODAY)
    assert s.due_card_ids(conn, [other_card], TODAY) == [other_card]


def test_delete_card_cascades_schedule_and_reviews(conn, deck):
    _, ids = deck
    s.record_review(conn, ids[0], 5, TODAY)
    content.delete_card(conn, ids[0])
    assert conn.execute("SELECT COUNT(*) FROM card_schedule").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 0
