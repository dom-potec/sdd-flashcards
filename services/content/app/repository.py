"""Deck and card persistence in SQL Server. Every function takes an open pymssql connection first.

Rows come back as dicts (the connection is opened with as_dict=True). Placeholders are %s."""

import pymssql

DECK_COLUMNS = "d.id, d.name, d.description, d.created_at"


def create_deck(conn: pymssql.Connection, name: str, description: str = "") -> int:
    name = name.strip()
    if not name:
        raise ValueError("deck name must not be blank")
    cur = conn.cursor()
    # SCOPE_IDENTITY() is the id the INSERT in this same batch just generated.
    cur.execute(
        "INSERT INTO decks (name, description) VALUES (%s, %s); SELECT CAST(SCOPE_IDENTITY() AS INT) AS id",
        (name, description.strip()),
    )
    deck_id = cur.fetchone()["id"]
    conn.commit()
    return deck_id


def list_decks(conn: pymssql.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT {DECK_COLUMNS}, COUNT(c.id) AS card_count
        FROM decks d
        LEFT JOIN cards c ON c.deck_id = d.id
        GROUP BY {DECK_COLUMNS}
        ORDER BY d.id
        """
    )
    return cur.fetchall()


def get_deck(conn: pymssql.Connection, deck_id: int) -> dict | None:
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT {DECK_COLUMNS}, COUNT(c.id) AS card_count
        FROM decks d
        LEFT JOIN cards c ON c.deck_id = d.id
        WHERE d.id = %s
        GROUP BY {DECK_COLUMNS}
        """,
        (deck_id,),
    )
    return cur.fetchone()


def delete_deck(conn: pymssql.Connection, deck_id: int) -> bool:
    """Deletes the deck and, through ON DELETE CASCADE, its cards. False if there was no such deck."""
    cur = conn.cursor()
    cur.execute("DELETE FROM decks WHERE id = %s", (deck_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    return deleted


def create_card(conn: pymssql.Connection, deck_id: int, front: str, back: str) -> int:
    front = front.strip()
    back = back.strip()
    if not front or not back:
        raise ValueError("card front and back must not be blank")
    if get_deck(conn, deck_id) is None:
        raise LookupError(f"deck {deck_id} does not exist")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO cards (deck_id, front, back) VALUES (%s, %s, %s); "
        "SELECT CAST(SCOPE_IDENTITY() AS INT) AS id",
        (deck_id, front, back),
    )
    card_id = cur.fetchone()["id"]
    conn.commit()
    return card_id


def list_cards(conn: pymssql.Connection, deck_id: int) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, deck_id, front, back, created_at FROM cards WHERE deck_id = %s ORDER BY id", (deck_id,)
    )
    return cur.fetchall()


def get_card(conn: pymssql.Connection, card_id: int) -> dict | None:
    cur = conn.cursor()
    cur.execute("SELECT id, deck_id, front, back, created_at FROM cards WHERE id = %s", (card_id,))
    return cur.fetchone()


def update_card(conn: pymssql.Connection, card_id: int, front: str, back: str) -> bool:
    front = front.strip()
    back = back.strip()
    if not front or not back:
        raise ValueError("card front and back must not be blank")
    cur = conn.cursor()
    cur.execute("UPDATE cards SET front = %s, back = %s WHERE id = %s", (front, back, card_id))
    updated = cur.rowcount > 0
    conn.commit()
    return updated


def delete_card(conn: pymssql.Connection, card_id: int) -> bool:
    cur = conn.cursor()
    cur.execute("DELETE FROM cards WHERE id = %s", (card_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    return deleted
