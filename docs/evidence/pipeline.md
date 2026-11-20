# Pipeline evidence

## A failed run that was fixed

| | Commit | Run | Result |
|---|---|---|---|
| CI jobs added | `be775ae` | https://github.com/dom-potec/sdd-flashcards/actions/runs/44149130411 | green |
| Break | `70390de` | https://github.com/dom-potec/sdd-flashcards/actions/runs/44150724387 | red: `test (content)` |
| Fix | `3f5a3e9` | https://github.com/dom-potec/sdd-flashcards/actions/runs/44152710359 | green |

**What broke.** Commit `70390de` removed `name = name.strip()` from `create_deck` in
`services/content/app/repository.py`. I did this on purpose, to see the test gate stop a real regression.

**What CI reported.** The `test (content)` job failed with 3 of 44 tests failing; the other four jobs passed:

- `test_api.py::test_create_deck_then_list_shows_it`: `assert ' Spanish ' == 'Spanish'` (the name was stored untrimmed)
- `test_api.py::test_blank_deck_name_is_400_json`: `assert 201 == 400` (a name of only spaces was accepted)
- `test_repository.py::test_create_deck_blank_name_raises`: `DID NOT RAISE ValueError`

**The fix.** Commit `3f5a3e9` restores the line, and all five jobs pass again.

## Successful deployments from `main`

| Commit on `main` | Run | What it deployed |
|---|---|---|
| `3004d9f` | https://github.com/dom-potec/sdd-flashcards/actions/runs/44544966323 | the first deployment to Azure (19 Nov) |
| `1693219` | https://github.com/dom-potec/sdd-flashcards/actions/runs/44755391761 | migration `002_add_lapses` (20 Nov), see [`migration.md`](migration.md) |

In both runs every CI job passed first, then the `deploy` job, whose last step waits until `/health` of
both services reports the deployed commit.

