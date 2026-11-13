from datetime import date, timedelta

import pytest

from app import repository as s
from app.sm2 import ScheduleState

TODAY = date(2026, 10, 8)
TOMORROW = TODAY + timedelta(days=1)

# Card ids are plain numbers here: the cards themselves live in the content service.
IDS = [101, 102, 103]


def count(conn, table: str) -> int:
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) AS n FROM {table}")
    return cur.fetchone()["n"]


def one(conn, sql: str, params: tuple) -> dict:
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchone()


def test_get_state_default_when_never_reviewed(conn):
    assert s.get_state(conn, IDS[0]) == ScheduleState()


def test_record_review_inserts_schedule_and_review_row(conn):
    state = s.record_review(conn, IDS[0], 5, TODAY)
    assert state == ScheduleState(ease_factor=2.6, repetitions=1, interval_days=1)
    row = one(conn, "SELECT * FROM card_schedule WHERE card_id = %s", (IDS[0],))
    assert row["repetitions"] == 1
    assert row["interval_days"] == 1
    assert row["due_at"] == TOMORROW
    review = one(conn, "SELECT * FROM reviews WHERE card_id = %s", (IDS[0],))
    assert review["grade"] == 5
    assert review["interval_before"] == 0
    assert review["interval_after"] == 1


def test_second_review_uses_stored_state(conn):
    s.record_review(conn, IDS[0], 5, TODAY)
    state = s.record_review(conn, IDS[0], 4, TOMORROW)
    assert state.repetitions == 2
    assert state.interval_days == 6
    assert s.get_state(conn, IDS[0]) == state
    assert count(conn, "card_schedule") == 1
    assert count(conn, "reviews") == 2


def test_lapse_resets_repetitions(conn):
    s.record_review(conn, IDS[0], 5, TODAY)
    s.record_review(conn, IDS[0], 4, TOMORROW)
    state = s.record_review(conn, IDS[0], 1, TOMORROW)
    assert state.repetitions == 0
    assert state.interval_days == 1
    assert state.ease_factor == pytest.approx(2.6)


def test_invalid_grade_writes_nothing(conn):
    with pytest.raises(ValueError):
        s.record_review(conn, IDS[0], 6, TODAY)
    assert count(conn, "reviews") == 0
    assert s.get_state(conn, IDS[0]) == ScheduleState()


def test_failed_review_insert_rolls_back_the_schedule_update(conn):
    """Both writes or neither: grade 9 passes a fake SM-2 but breaks the CHECK on reviews.grade."""
    s.record_review(conn, IDS[0], 5, TODAY)
    original = s.next_state
    s.next_state = lambda state, grade: ScheduleState(ease_factor=9.9, repetitions=9, interval_days=9)
    try:
        with pytest.raises(Exception):
            s.record_review(conn, IDS[0], 9, TOMORROW)
    finally:
        s.next_state = original
    assert s.get_state(conn, IDS[0]) == ScheduleState(ease_factor=2.6, repetitions=1, interval_days=1)
    assert count(conn, "reviews") == 1


def test_new_card_is_due(conn):
    assert s.due_card_ids(conn, IDS, TODAY) == IDS


def test_future_card_not_due(conn):
    s.record_review(conn, IDS[0], 5, TODAY)  # due tomorrow
    assert s.due_card_ids(conn, IDS, TODAY) == IDS[1:]


def test_past_card_is_due(conn):
    s.record_review(conn, IDS[0], 5, TODAY - timedelta(days=3))  # was due two days ago
    assert IDS[0] in s.due_card_ids(conn, IDS, TODAY)


def test_due_ordering_new_then_oldest(conn):
    s.record_review(conn, IDS[0], 3, TODAY - timedelta(days=2))  # due yesterday
    s.record_review(conn, IDS[1], 3, TODAY - timedelta(days=5))  # due four days ago
    # IDS[2] never reviewed -> first; then IDS[1] (older due date); then IDS[0]
    assert s.due_card_ids(conn, IDS, TODAY) == [IDS[2], IDS[1], IDS[0]]


def test_due_card_ids_empty_input(conn):
    assert s.due_card_ids(conn, [], TODAY) == []


def test_count_due(conn):
    assert s.count_due(conn, IDS, TODAY) == 3
    s.record_review(conn, IDS[0], 5, TODAY)
    assert s.count_due(conn, IDS, TODAY) == 2


def test_ids_not_asked_about_are_ignored(conn):
    other_card = 999
    s.record_review(conn, other_card, 5, TODAY - timedelta(days=3))
    assert other_card not in s.due_card_ids(conn, IDS, TODAY)
    assert s.due_card_ids(conn, [other_card], TODAY) == [other_card]


def test_no_foreign_key_so_rows_for_a_deleted_card_stay(conn):
    """ADR-7: the card may be gone in content; its rows stay here and are never served,
    because due_card_ids only looks at the ids it is given."""
    s.record_review(conn, IDS[0], 5, TODAY - timedelta(days=3))
    still_existing = IDS[1:]
    assert s.due_card_ids(conn, still_existing, TODAY) == still_existing
    assert count(conn, "card_schedule") == 1
    assert count(conn, "reviews") == 1


def test_get_schedule(conn):
    assert s.get_schedule(conn, IDS[0]) == {
        "card_id": IDS[0], "ease_factor": 2.5, "repetitions": 0, "interval_days": 0, "due_at": None,
    }
    s.record_review(conn, IDS[0], 5, TODAY)
    assert s.get_schedule(conn, IDS[0]) == {
        "card_id": IDS[0], "ease_factor": 2.6, "repetitions": 1, "interval_days": 1, "due_at": TOMORROW,
    }
