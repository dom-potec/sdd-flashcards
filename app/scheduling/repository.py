"""Scheduling persistence: card_schedule state and the reviews log.

Knows only card ids, never card content. Every function takes an open
sqlite3 connection first.
"""

import sqlite3
from datetime import date

from .sm2 import ScheduleState, due_date, next_state


def get_state(conn: sqlite3.Connection, card_id: int) -> ScheduleState:
    row = conn.execute(
        "SELECT ease_factor, repetitions, interval_days FROM card_schedule WHERE card_id = ?",
        (card_id,),
    ).fetchone()
    if row is None:
        return ScheduleState()
    return ScheduleState(
        ease_factor=row["ease_factor"],
        repetitions=row["repetitions"],
        interval_days=row["interval_days"],
    )


def record_review(conn: sqlite3.Connection, card_id: int, grade: int, today: date) -> ScheduleState:
    before = get_state(conn, card_id)
    after = next_state(before, grade)
    due = due_date(today, after.interval_days).isoformat()
    with conn:  # one transaction: both writes or neither
        conn.execute(
            """
            INSERT INTO card_schedule (card_id, ease_factor, repetitions, interval_days, due_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(card_id) DO UPDATE SET
                ease_factor = excluded.ease_factor,
                repetitions = excluded.repetitions,
                interval_days = excluded.interval_days,
                due_at = excluded.due_at
            """,
            (card_id, after.ease_factor, after.repetitions, after.interval_days, due),
        )
        conn.execute(
            "INSERT INTO reviews (card_id, grade, interval_before, interval_after) VALUES (?, ?, ?, ?)",
            (card_id, grade, before.interval_days, after.interval_days),
        )
    return after


def due_card_ids(conn: sqlite3.Connection, card_ids: list[int], today: date) -> list[int]:
    """New cards (no schedule row) first, then due cards oldest first, then by id."""
    if not card_ids:
        return []
    placeholders = ",".join("?" * len(card_ids))
    rows = conn.execute(
        f"SELECT card_id, due_at FROM card_schedule WHERE card_id IN ({placeholders})",
        card_ids,
    ).fetchall()
    scheduled = {row["card_id"]: row["due_at"] for row in rows}
    new = sorted(cid for cid in card_ids if cid not in scheduled)
    due = sorted((due_at, cid) for cid, due_at in scheduled.items() if due_at <= today.isoformat())
    return new + [cid for _, cid in due]


def count_due(conn: sqlite3.Connection, card_ids: list[int], today: date) -> int:
    return len(due_card_ids(conn, card_ids, today))
