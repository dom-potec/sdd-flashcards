-- Content service: decks and cards. Applied once by app/migrate.py; never edit after it has run.
CREATE TABLE decks (
    id          INT IDENTITY PRIMARY KEY,
    name        NVARCHAR(200)  NOT NULL,
    description NVARCHAR(1000) NOT NULL DEFAULT '',
    created_at  DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE cards (
    id          INT IDENTITY PRIMARY KEY,
    deck_id     INT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    front       NVARCHAR(MAX) NOT NULL,
    back        NVARCHAR(MAX) NOT NULL,
    created_at  DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE INDEX idx_cards_deck ON cards(deck_id);

-- One row that /health updates and reads back to prove the database is writable.
CREATE TABLE health_probe (
    id         INT PRIMARY KEY,
    checked_at DATETIME2 NOT NULL
);
INSERT INTO health_probe (id, checked_at) VALUES (1, SYSUTCDATETIME());
