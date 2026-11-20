# Migration evidence on Azure

Migration [`002_add_lapses.sql`](../../services/scheduling/migrations/002_add_lapses.sql) adds a `lapses`
column to `card_schedule` in the scheduling database and fills it for the rows that already exist, by
counting each card's wrong answers (a grade below 3) in `reviews`.

| | When (UTC) | Version | What |
|---|---|---|---|
| Data created | 2026-11-19 14:41 | `3004d9f` | one deck with 5 cards, each studied once in the live UI |
| Before | 2026-11-19 14:43 | `3004d9f` | [`migration-before.txt`](migration-before.txt) |
| Deployment | 2026-11-20 14:40 | `1693219` | https://github.com/dom-potec/sdd-flashcards/actions/runs/44755391761 |
| After | 2026-11-20 14:42 | `1693219` | [`migration-after.txt`](migration-after.txt) |

**The startup log line** of the scheduling Container App, read with `az containerapp logs show`:

```
2026-11-20T14:40:48.641984326+00:00 stdout 2026-11-20 14:40:48,640 INFO app.migrate: applied migration 002_add_lapses
```

**The data before and after**, from `GET /cards/{id}/schedule` on the live scheduling service:

| card | ease_factor | repetitions | interval_days | due_at | lapses before | lapses after |
|---|---|---|---|---|---|---|
| 1 | 2.5 | 0 | 1 | 2026-11-20 | no column | 1 |
| 2 | 2.36 | 1 | 1 | 2026-11-20 | no column | 0 |
| 3 | 2.5 | 0 | 1 | 2026-11-20 | no column | 1 |
| 4 | 2.6 | 1 | 1 | 2026-11-20 | no column | 0 |
| 5 | 2.5 | 1 | 1 | 2026-11-20 | no column | 0 |

The first four value columns are identical in both snapshots: all five rows are still there and none of
their values changed. The backfill is right: cards 1 and 3 are the two that were answered wrong on
19 Nov (their `repetitions` is 0, which is what a wrong answer resets it to), and they are the two with
`lapses` 1.

The deck's due count went from 0 to 5 between the snapshots. That is the calendar, not the migration:
all five cards were due on 2026-11-20, and the second snapshot was taken on that day.

Nobody used the live app between the two snapshots. The snapshots are read through the public API
because the database firewall only lets Azure services in.
