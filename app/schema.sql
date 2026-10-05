CREATE TABLE IF NOT EXISTS decks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id     INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    front       TEXT    NOT NULL,
    back        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS card_schedule (
    card_id       INTEGER PRIMARY KEY REFERENCES cards(id) ON DELETE CASCADE,
    ease_factor   REAL    NOT NULL DEFAULT 2.5,
    repetitions   INTEGER NOT NULL DEFAULT 0,
    interval_days INTEGER NOT NULL DEFAULT 0,
    due_at        TEXT    NOT NULL                 -- ISO date YYYY-MM-DD
);

CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id         INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    reviewed_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    grade           INTEGER NOT NULL CHECK (grade BETWEEN 0 AND 5),
    interval_before INTEGER NOT NULL,
    interval_after  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cards_deck    ON cards(deck_id);
CREATE INDEX IF NOT EXISTS idx_schedule_due  ON card_schedule(due_at);
