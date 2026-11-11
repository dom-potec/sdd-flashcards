-- Scheduling service: SM-2 state and the reviews log. Applied once by app/migrate.py; never edit after it has run.
CREATE TABLE card_schedule (
    card_id       INT   PRIMARY KEY,          -- plain id: cards live in the content service (ADR-7)
    ease_factor   FLOAT NOT NULL DEFAULT 2.5,
    repetitions   INT   NOT NULL DEFAULT 0,
    interval_days INT   NOT NULL DEFAULT 0,
    due_at        DATE  NOT NULL
);
CREATE TABLE reviews (
    id              INT IDENTITY PRIMARY KEY,
    card_id         INT NOT NULL,
    reviewed_at     DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    grade           INT NOT NULL CHECK (grade BETWEEN 0 AND 5),
    interval_before INT NOT NULL,
    interval_after  INT NOT NULL
);
CREATE INDEX idx_schedule_due ON card_schedule(due_at);
CREATE INDEX idx_reviews_card ON reviews(card_id);
CREATE TABLE health_probe (id INT PRIMARY KEY, checked_at DATETIME2 NOT NULL);
INSERT INTO health_probe (id, checked_at) VALUES (1, SYSUTCDATETIME());
