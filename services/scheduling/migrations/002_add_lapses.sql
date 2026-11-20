-- Adds lapses to card_schedule: how many times the card was answered wrong (a grade below 3).
-- Existing rows are kept. The new column starts at 0 for them, and then the UPDATE fills it in
-- by counting the wrong answers already recorded in the reviews log.
-- GO ends the first batch: SQL Server compiles a whole batch before running it, so the UPDATE
-- could not name the column in the same batch that adds it.
ALTER TABLE card_schedule ADD lapses INT NOT NULL DEFAULT 0;
GO
UPDATE s SET lapses = (SELECT COUNT(*) FROM reviews r WHERE r.card_id = s.card_id AND r.grade < 3)
FROM card_schedule s;
