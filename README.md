# sdd-flashcards

Spaced-repetition flashcards (Anki-style) built with Flask and SQLite. Setup, configuration and run docs will follow.

## Run in Docker

The `Dockerfile` is the course-provided template with its four `TODO` lines filled in (base image, dependency install, source copy, start command); nothing else in it was changed.

```bash
docker build -t sdd-flashcards .
docker run -p 8000:8000 -v sdd-flashcards-data:/data sdd-flashcards          # http://localhost:8000
docker run -e PORT=9000 -p 9000:9000 -v sdd-flashcards-data:/data sdd-flashcards
```

Inside the container `DATA_DIR=/data`, so the database is `/data/flashcards.db` on the named volume and survives the container being removed and recreated. The schema is created with `CREATE TABLE IF NOT EXISTS` on every start; there is no seed data and nothing is dropped, so a restart never changes the data.

### Contract check

Output of the course's `container/run.sh` on 2026-10-09 (run on `PORT=8100` because 8000 was in use by another container on the host; the second start on port 9123 is the checker's own `PORT` override test):

```
=== SDD Assignment 1 contract check ===
Repository: /Users/dominicpotec/Desktop/year3/devops/assignemt1/sdd-flashcards

==> Repository shape
  PASS  one Dockerfile, one manifest (requirements.txt)

==> Build from a clean context, no build args
  PASS  image built
  PASS  image size 53 MB

==> Start on PORT=8100 and reach it from the host
  PASS  HTTP 302 from http://localhost:8100/

==> SQLite file under DATA_DIR
  PASS  found in /data: flashcards.db 

==> Data persists, and a second boot does not re-seed
  PASS  volume at /data persists
  PASS  row counts unchanged across restart: card_schedule=0 cards=0 decks=0 reviews=0 

==> PORT override is honoured (not hardcoded)
  PASS  HTTP 302 from http://localhost:9123/

=== ALL CHECKS PASSED ===
Paste this output into your README as the §7 evidence.
```

## Testing

```bash
pytest --cov=app --cov-report=term-missing
```

Output on 2026-10-09:

```
Name                           Stmts   Miss Branch BrPart  Cover   Missing
--------------------------------------------------------------------------
app/__init__.py                   25      0      4      1    97%   13->16
app/config.py                      5      0      0      0   100%
app/content/__init__.py            0      0      0      0   100%
app/content/repository.py         45      0      8      0   100%
app/content/routes.py             50     21      6      0    55%   33-34, 40-44, 49-55, 60-61, 66-70
app/db.py                         13      0      0      0   100%
app/scheduling/__init__.py         0      0      0      0   100%
app/scheduling/repository.py      27      0      4      0   100%
app/scheduling/routes.py          35     14      8      2    58%   34, 39-41, 48-57
app/scheduling/sm2.py             24      0      8      0   100%
--------------------------------------------------------------------------
TOTAL                            224     35     38      3    83%
============================== 39 passed in 0.19s ==============================
```

Coverage is measured on all of `app/` with branch coverage on (see `.coveragerc`; pytest options are in `pytest.ini`). The scheduler (`sm2.py`) and both repositories are at 100%; the uncovered lines are route handlers, which are covered only by the four smoke tests in `tests/test_app_smoke.py` (see ADR-4).
