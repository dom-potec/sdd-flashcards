"""SM-2 spaced-repetition maths. Pure functions, no database and no Flask."""

from dataclasses import dataclass
from datetime import date, timedelta

MIN_EASE = 1.3
DEFAULT_EASE = 2.5


@dataclass(frozen=True)
class ScheduleState:
    ease_factor: float = DEFAULT_EASE
    repetitions: int = 0
    interval_days: int = 0


def next_state(state: ScheduleState, grade: int) -> ScheduleState:
    """SM-2. grade 0-5. <3 = lapse: repetitions reset, interval 1, ease unchanged."""
    if not 0 <= grade <= 5:
        raise ValueError("grade must be 0-5")
    if grade < 3:
        return ScheduleState(ease_factor=state.ease_factor, repetitions=0, interval_days=1)
    if state.repetitions == 0:
        interval = 1
    elif state.repetitions == 1:
        interval = 6
    else:
        interval = round(state.interval_days * state.ease_factor)
    ease = state.ease_factor + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    ease = max(MIN_EASE, ease)
    return ScheduleState(ease_factor=ease, repetitions=state.repetitions + 1, interval_days=interval)


def due_date(today: date, interval_days: int) -> date:
    return today + timedelta(days=interval_days)
