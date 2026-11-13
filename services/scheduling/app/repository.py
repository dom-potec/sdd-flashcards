"""Scheduling persistence in SQL Server: card_schedule state and the reviews log.

Knows only card ids, never card content. Every function takes an open pymssql connection first.
Rows come back as dicts; due_at is a DATE column, so it arrives as a datetime.date."""

from datetime import date

import pymssql

from .sm2 import ScheduleState, due_date, next_state


def get_state(conn: pymssql.Connection, card_id: int) -> ScheduleState:
    """The SM-2 state of a card, or the default state for a card that was never reviewed."""
    cur = conn.cursor()
    cur.execute(
        "SELECT ease_factor, repetitions, interval_days FROM card_schedule WHERE card_id = %s", (card_id,)
    )
    row = cur.fetchone()
    if row is None:
        return ScheduleState()
    return ScheduleState(
        ease_factor=row["ease_factor"],
        repetitions=row["repetitions"],
        interval_days=row["interval_days"],
    )


def get_schedule(conn: pymssql.Connection, card_id: int) -> dict:
    """The schedule row of a card as a dict. A card that was never reviewed has due_at None."""
    cur = conn.cursor()
    cur.execute(
        "SELECT card_id, ease_factor, repetitions, interval_days, due_at "
        "FROM card_schedule WHERE card_id = %s",
        (card_id,),
    )
    row = cur.fetchone()
    if row is None:
        new = ScheduleState()
        return {
            "card_id": card_id,
            "ease_factor": new.ease_factor,
            "repetitions": new.repetitions,
            "interval_days": new.interval_days,
            "due_at": None,
        }
    return row


def record_review(conn: pymssql.Connection, card_id: int, grade: int, today: date) -> ScheduleState:
    """Apply one grade: update (or create) the schedule row and append to the reviews log.
    One transaction: both writes are committed together, or neither is."""
    before = get_state(conn, card_id)
    after = next_state(before, grade)  # raises ValueError for a grade outside 0-5, before any write
    due = due_date(today, after.interval_days)
    cur = conn.cursor()
    try:
        # Upsert: try the UPDATE; @@ROWCOUNT is 0 when the card has no row yet, so INSERT it.
        cur.execute(
            """
            UPDATE card_schedule
            SET ease_factor = %s, repetitions = %s, interval_days = %s, due_at = %s
            WHERE card_id = %s;
            IF @@ROWCOUNT = 0
                INSERT INTO card_schedule (card_id, ease_factor, repetitions, interval_days, due_at)
                VALUES (%s, %s, %s, %s, %s);
            """,
            (
                after.ease_factor, after.repetitions, after.interval_days, due, card_id,
                card_id, after.ease_factor, after.repetitions, after.interval_days, due,
            ),
        )
        cur.execute(
            "INSERT INTO reviews (card_id, grade, interval_before, interval_after) VALUES (%s, %s, %s, %s)",
            (card_id, grade, before.interval_days, after.interval_days),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return after


def due_card_ids(conn: pymssql.Connection, card_ids: list[int], today: date) -> list[int]:
    """Of the given cards, the ones to study now: new cards (no schedule row) first by id,
    then due cards, the longest overdue first, then by id."""
    if not card_ids:
        return []
    placeholders = ",".join(["%s"] * len(card_ids))
    cur = conn.cursor()
    cur.execute(
        f"SELECT card_id, due_at FROM card_schedule WHERE card_id IN ({placeholders})", tuple(card_ids)
    )
    scheduled = {row["card_id"]: row["due_at"] for row in cur.fetchall()}
    new = sorted(cid for cid in card_ids if cid not in scheduled)
    due = sorted((due_at, cid) for cid, due_at in scheduled.items() if due_at <= today)
    return new + [cid for _, cid in due]


def count_due(conn: pymssql.Connection, card_ids: list[int], today: date) -> int:
    return len(due_card_ids(conn, card_ids, today))
