"""Deck and card persistence. Every function takes an open sqlite3 connection first."""

import sqlite3


def create_deck(conn: sqlite3.Connection, name: str, description: str = "") -> int:
    name = name.strip()
    if not name:
        raise ValueError("deck name must not be blank")
    cur = conn.execute(
        "INSERT INTO decks (name, description) VALUES (?, ?)",
        (name, description.strip()),
    )
    conn.commit()
    return cur.lastrowid


def list_decks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT d.id, d.name, d.description, d.created_at, COUNT(c.id) AS card_count
        FROM decks d
        LEFT JOIN cards c ON c.deck_id = d.id
        GROUP BY d.id
        ORDER BY d.id
        """
    ).fetchall()


def get_deck(conn: sqlite3.Connection, deck_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM decks WHERE id = ?", (deck_id,)).fetchone()


def delete_deck(conn: sqlite3.Connection, deck_id: int) -> bool:
    cur = conn.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    conn.commit()
    return cur.rowcount > 0


def create_card(conn: sqlite3.Connection, deck_id: int, front: str, back: str) -> int:
    front = front.strip()
    back = back.strip()
    if not front or not back:
        raise ValueError("card front and back must not be blank")
    if get_deck(conn, deck_id) is None:
        raise LookupError(f"deck {deck_id} does not exist")
    cur = conn.execute(
        "INSERT INTO cards (deck_id, front, back) VALUES (?, ?, ?)",
        (deck_id, front, back),
    )
    conn.commit()
    return cur.lastrowid


def list_cards(conn: sqlite3.Connection, deck_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM cards WHERE deck_id = ? ORDER BY id", (deck_id,)
    ).fetchall()


def list_card_ids(conn: sqlite3.Connection, deck_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT id FROM cards WHERE deck_id = ? ORDER BY id", (deck_id,)
    ).fetchall()
    return [row["id"] for row in rows]


def get_card(conn: sqlite3.Connection, card_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()


def update_card(conn: sqlite3.Connection, card_id: int, front: str, back: str) -> bool:
    front = front.strip()
    back = back.strip()
    if not front or not back:
        raise ValueError("card front and back must not be blank")
    cur = conn.execute(
        "UPDATE cards SET front = ?, back = ? WHERE id = ?", (front, back, card_id)
    )
    conn.commit()
    return cur.rowcount > 0


def delete_card(conn: sqlite3.Connection, card_id: int) -> bool:
    cur = conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    conn.commit()
    return cur.rowcount > 0
