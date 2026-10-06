from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from app.scheduling.sm2 import MIN_EASE, ScheduleState, due_date, next_state


def test_first_review_grade5():
    new = next_state(ScheduleState(), 5)
    assert new == ScheduleState(ease_factor=2.6, repetitions=1, interval_days=1)


def test_second_review_interval_six():
    new = next_state(ScheduleState(ease_factor=2.5, repetitions=1, interval_days=1), 4)
    assert new == ScheduleState(ease_factor=2.5, repetitions=2, interval_days=6)


def test_third_review_multiplies_by_ease():
    new = next_state(ScheduleState(ease_factor=2.5, repetitions=2, interval_days=6), 3)
    assert new.interval_days == 15  # round(6 * 2.5)
    assert new.repetitions == 3
    assert new.ease_factor == pytest.approx(2.36)


def test_lapse_resets_reps_keeps_ease():
    new = next_state(ScheduleState(ease_factor=2.2, repetitions=5, interval_days=30), 1)
    assert new == ScheduleState(ease_factor=2.2, repetitions=0, interval_days=1)


def test_ease_never_below_floor():
    new = next_state(ScheduleState(ease_factor=1.3, repetitions=3, interval_days=10), 3)
    assert new.ease_factor == MIN_EASE
    assert new.interval_days == 13  # round(10 * 1.3)


@pytest.mark.parametrize("grade", [-1, 6])
def test_invalid_grade_raises(grade):
    with pytest.raises(ValueError):
        next_state(ScheduleState(), grade)


def test_due_date_adds_interval():
    assert due_date(date(2026, 10, 6), 6) == date(2026, 10, 12)


def test_state_is_immutable():
    state = ScheduleState()
    with pytest.raises(FrozenInstanceError):
        state.ease_factor = 1.0
