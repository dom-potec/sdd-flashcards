# sdd-flashcards

Spaced-repetition flashcards, Anki-style. You create decks of front/back cards, study the cards that are due today, grade each answer from 0 to 5, and the app decides when to show each card again with the SM-2 algorithm.

Live system: <https://dpotecieu2024ui.z1.web.core.windows.net>. The first request after a quiet period takes about a minute, because the containers and the databases start again (see [Operations notes](#operations-notes)).

Assignment 1 was one Flask process with one SQLite file. It is now two services and a static UI:

- **content** ([`services/content/`](services/content/)): decks and cards. A JSON API with its own SQL Server database.
- **scheduling** ([`services/scheduling/`](services/scheduling/)): the SM-2 state of each card, the review log, and what is due. A JSON API with its own SQL Server database.
- **UI** ([`ui/`](ui/)): three static HTML pages and one JavaScript file. The browser calls both services directly.

## Architecture

![Architecture after the split](docs/architecture-after.png)

The split follows the seam that Assignment 1 already had between its two packages ([before](docs/architecture-before.png), ADR-2 and ADR-6). Each service owns its tables and nobody else reads them: the two databases have different users, and each user can open only its own database. Scheduling stores card ids only, never card text.

One HTTP call crosses the seam. To pick the next card to study or to count the due cards of a deck, scheduling asks content for the deck's cards with `GET /decks/{deck_id}/cards`, with a 2 second timeout. If content does not answer, scheduling answers `503 {"error":"content service unavailable"}`. Saving a review never calls content, so it keeps working. When scheduling is down, decks and cards still work and only the due counts and the study page are missing. See [Partial failure](#partial-failure).

There is no gateway in front of the services (ADR-10). Each service allows cross-origin requests from the UI's origin only (`UI_ORIGIN`).

| Service | Endpoints |
|---|---|
| content | `GET /health` · `GET, POST /decks` · `GET, DELETE /decks/{deck_id}` · `GET, POST /decks/{deck_id}/cards` · `GET, PUT, DELETE /cards/{card_id}` |
| scheduling | `GET /health` · `GET /study/{deck_id}/next` · `GET /study/{deck_id}/due-count` · `POST /reviews` · `GET /cards/{card_id}/schedule` |

The full contracts are [`services/content/openapi.yaml`](services/content/openapi.yaml) and [`services/scheduling/openapi.yaml`](services/scheduling/openapi.yaml). The whole system is described in one file, [`system.yaml`](system.yaml).

## Run locally

You need Docker Desktop. On Apple Silicon turn on Rosetta in Docker Desktop (Settings > General > "Use Rosetta for x86_64/amd64 emulation"), because SQL Server has no arm64 image.

```bash
git clone https://github.com/dom-potec/sdd-flashcards && cd sdd-flashcards
docker compose up --build --wait
```

| What | Address |
|---|---|
| UI | <http://localhost:8080> |
| content | <http://localhost:8000/health> |
| scheduling | <http://localhost:8001/health> |
| SQL Server | `localhost:1433` |

Compose starts SQL Server, runs [`db/init.sql`](db/init.sql) once (two databases, one login each), then starts the two services, which apply their migrations, and an nginx container that serves `ui/`. The data is kept in a Docker volume between runs. `docker compose down` stops everything; `docker compose down -v` also deletes the data.

Every password in `docker-compose.yml` and `db/init.sql` is a local development credential. None of them is used on Azure.

## Run a single service

A service can run outside Docker, against the SQL Server from compose:

```bash
docker compose up -d --wait sqlserver db-init
cd services/content
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
export DATABASE_URL=...        # the content DATABASE_URL from docker-compose.yml, with host localhost instead of sqlserver
python app.py                  # http://localhost:8000
```

It is the same for `services/scheduling`, which also needs `CONTENT_URL=http://localhost:8000` and a different port, for example `PORT=8001`. `python app.py` is the development server; the container runs gunicorn with one worker and four threads.

## Tests and coverage

Each service has its own tests. They use a real SQL Server (the one from compose locally, a service container in CI) and create their own test database.

```bash
docker compose up -d --wait sqlserver db-init
cd services/content        # or services/scheduling
pytest --cov=app --cov-report=term-missing --cov-fail-under=70
flake8 app tests
```

Output on 2026-11-21, content:

```
Name                Stmts   Miss Branch BrPart  Cover   Missing
---------------------------------------------------------------
app/__init__.py        50      1      8      1    97%   53
app/config.py           4      0      0      0   100%
app/db.py              29      0      8      2    95%   36->exit, 49->52
app/logging_.py        16      0      0      0   100%
app/migrate.py         37      0     12      0   100%
app/repository.py      61      0      8      0   100%
app/routes.py          73      0     12      0   100%
---------------------------------------------------------------
TOTAL                 270      1     48      3    99%
Required test coverage of 70% reached. Total coverage: 98.74%
44 passed in 2.46s
```

scheduling:

```
Name                    Stmts   Miss Branch BrPart  Cover   Missing
-------------------------------------------------------------------
app/__init__.py            57      1      8      1    97%   63
app/config.py               4      0      0      0   100%
app/content_client.py      18      0      4      0   100%
app/db.py                  29      0      8      2    95%   36->exit, 49->52
app/logging_.py            16      0      0      0   100%
app/migrate.py             37      0     12      0   100%
app/repository.py          44      0      6      0   100%
app/routes.py              40      0      4      0   100%
app/sm2.py                 24      0      8      0   100%
-------------------------------------------------------------------
TOTAL                     269      1     50      3    99%
Required test coverage of 70% reached. Total coverage: 98.75%
72 passed in 2.26s
```

In the scheduling unit tests the call to content is replaced by a stub. The **integration tests** in [`tests/integration/`](tests/integration/) stub nothing: they run against the whole compose stack over HTTP, so scheduling really calls content.

```bash
docker compose up --build --wait
pip install -r requirements-dev.txt        # from the repo root
pytest tests/integration                   # 2 tests
RUN_FAILURE_TEST=1 pytest tests/integration   # 3 tests
```

`RUN_FAILURE_TEST=1` also runs the outage test. It stops the content container, checks that the study endpoint answers 503 and that a review is still saved, and starts content again. It is off by default because it stops a container of your running stack. CI always runs it.

## Configuration

Everything is read from environment variables, in `app/config.py` of each service. Only `DATABASE_URL` is a secret and has no default.

| Variable | Service | Default | Meaning |
|---|---|---|---|
| `PORT` | both | `8000` | Port the service listens on |
| `DATABASE_URL` | both | none, **secret** | `mssql://user:password@host:1433/database` of the service's own database |
| `UI_ORIGIN` | both | `http://localhost:8080` | The only origin allowed by CORS |
| `GIT_SHA` | both | `dev` | Commit the image was built from; `/health` reports it as `version` |
| `DB_CONNECT_ATTEMPTS` | both | `8` | Connection attempts with backoff, about two minutes, while Azure SQL resumes |
| `MIGRATIONS_DIR` | both | `migrations` | Folder of the numbered SQL migrations |
| `CONTENT_URL` | scheduling | `http://content:8000` | Base URL of the content service |
| `CONTENT_TIMEOUT_S` | scheduling | `2` | Timeout in seconds for a call to content |

On Azure, `DATABASE_URL` is a Container App secret that the deploy job builds from a GitHub Actions secret. The UI has one setting, [`ui/config.js`](ui/config.js), with the addresses of the two services. The repository holds the local values, and the deploy job writes the Azure ones.

## Database and migrations

| content | scheduling |
|---|---|
| ![content schema](docs/schema-content.png) | ![scheduling schema](docs/schema-scheduling.png) |

In Assignment 1 the scheduling tables had a foreign key to `cards.id` ([old schema](docs/schema-before.png)). A foreign key cannot cross databases, so `card_id` is now a plain number. Deleting a card leaves its schedule and reviews behind in the scheduling database; they are never shown, because scheduling only looks at the card ids content returns (ADR-7). `health_probe` is the one row that `/health` writes and reads back.

Each service has numbered SQL files in its `migrations/` folder. At startup `app/migrate.py` applies, in order, the ones not yet listed in the service's `schema_migrations` table, each in one transaction. An applied file is never edited; a change is a new file.

`services/scheduling/migrations/002_add_lapses.sql` changed a table that already held data on Azure: it adds `lapses` to `card_schedule` and fills it from the existing `reviews`. The evidence is in [`docs/evidence/migration.md`](docs/evidence/migration.md): the deployment run, the startup log line `applied migration 002_add_lapses`, and the live data before and after, with all five rows kept and the two cards that had been answered wrong showing `lapses` 1.

## Pipeline

One GitHub Actions workflow, [`.github/workflows/pipeline.yml`](.github/workflows/pipeline.yml), runs on every push to any branch and on every pull request to `main`. A job that fails makes the run red, and a red pull request is not merged.

| Job | Runs | Fails when |
|---|---|---|
| `test` | once per service, against a throwaway SQL Server container | flake8 reports a problem, a test fails, or coverage of `app/` is below 70% |
| `validate-docs` | once | an `openapi.yaml` is not valid OpenAPI, or `system.yaml` does not match `system.schema.json` or names a path that does not exist |
| `images` | once per service | the Dockerfile does not build; on `main` it also pushes the image to GHCR tagged with the commit SHA |
| `integration` | once | the compose stack does not become healthy, or a test in `tests/integration` fails, including the one that stops the content service |
| `deploy` | on `main` only, after the four jobs above pass | a deployment command fails, or `/health` of either service does not report the new commit within five minutes |

CI never touches Azure SQL: the `test` job and the compose stack each use their own local SQL Server. What `deploy` does is described at the end of the next section.

Evidence, in [`docs/evidence/pipeline.md`](docs/evidence/pipeline.md):

- a successful run with deployment: <https://github.com/dom-potec/sdd-flashcards/actions/runs/44755391761> (commit `1693219`, the one that deployed migration 002);
- a failed run and its fix: <https://github.com/dom-potec/sdd-flashcards/actions/runs/44150724387> was red in `test (content)` because a commit removed the trimming of deck names and three tests caught it; <https://github.com/dom-potec/sdd-flashcards/actions/runs/44152710359> is the fix, green.

## Deployment and Azure initial setup

![Deployment](docs/deployment.png)

The system runs in my own Azure for Students subscription and follows the course's A2 deployment guide. Everything is created once by [`infra/azure-setup.sh`](infra/azure-setup.sh), run by hand from the repo root. Every `az` and `gh` command of the setup is in that script. After it, the pipeline does every deployment and nothing is created or changed in the portal.

What it creates, all in the resource group `rg-dpotec-ieu2024`:

| Resource | Name | Settings |
|---|---|---|
| Storage account | `dpotecieu2024ui` | StorageV2, Standard_LRS, static website with `index.html`: the UI |
| SQL logical server | `dpotec-ieu2024-sql` | firewall rule "allow Azure services" only |
| SQL database, content | `dpotec-ieu2024-content-db` | serverless, General Purpose Gen5, 0.5 to 1 vCore, local backups, free offer (pauses after 60 idle minutes) |
| SQL database, scheduling | `dpotec-ieu2024-scheduling-db` | same |
| Container Apps environment | `dpotec-ieu2024-env` | Consumption; Azure creates its Log Analytics workspace with it |
| Container App, content | `dpotec-ieu2024-content` | 0 to 1 replicas, public HTTPS ingress on port 8000 |
| Container App, scheduling | `dpotec-ieu2024-scheduling` | same |
| Managed identity | `dpotec-ieu2024-github` | Contributor on this resource group only; the pipeline signs in as it |

Steps:

1. `az login` with the IE account and `az account set --subscription <the Azure for Students id>`. Have `gh` signed in as the repository owner and Docker running (the script uses the SQL Server image to run `sqlcmd`).
2. Run `./infra/azure-setup.sh`. It shows the subscription, region and repository and asks before creating anything. In order, it:
   - registers the resource providers and creates the resource group;
   - creates the storage account and turns on its static website. The web endpoint becomes `UI_ORIGIN`, the only origin CORS allows; CORS is done by the services themselves, and the Container Apps ingress CORS setting stays off;
   - creates the SQL server and the two serverless databases on the free offer;
   - opens the SQL firewall for this machine's IP, runs [`infra/azure-user.sql`](infra/azure-user.sql) on each database (a contained user that exists in that database only, with the roles needed to run migrations and read and write data), then removes the firewall rule;
   - creates the Container Apps environment and both apps on a placeholder image, with the database URL stored as a Container App secret and `CONTENT_URL` on scheduling pointing at the content app;
   - creates the managed identity, makes it Contributor on the resource group, and adds two federated credentials for the `main` branch of this repository (GitHub can name the repository by name or by numeric id);
   - stores what the pipeline needs in GitHub (table below);
   - gives the two professors the Reader role on the resource group.

| GitHub Actions | Name | Value |
|---|---|---|
| secret | `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | which identity, directory and subscription the pipeline signs in to. There is no stored Azure password: Azure trusts the token GitHub issues for `main` (OIDC) |
| secret | `CONTENT_DB_PASSWORD`, `SCHEDULING_DB_PASSWORD` | the password of each service's database user; the deploy job builds each `DATABASE_URL` from it |
| secret | `CI_SA_PASSWORD` | any strong password; used only by the throwaway SQL Server in CI. Set by hand, not by the script |
| variable | `PREFIX`, `RESOURCE_GROUP`, `UI_STORAGE` | `dpotec-ieu2024`, `rg-dpotec-ieu2024`, `dpotecieu2024ui` |

The script keeps resources that already exist, so it can be run again after a failure. The three passwords (SQL administrator and the two database users) are generated inside the script, sent to Azure and to GitHub secrets, and never typed, printed or written to a file. Running the script again sets new ones everywhere.

On every push to `main`, after all CI jobs pass, the `deploy` job points each Container App at the image of that commit, writes the services' addresses into `ui/config.js`, uploads `ui/` to the storage account's `$web` container, and fails unless `/health` of both services reports that commit within five minutes.

## Partial failure

The two services fail separately. Scheduling calls content in one place only, to get a deck's cards for the study page and the due count, with a 2 second timeout.

| Down | Still works | What the user gets |
|---|---|---|
| content | saving a review (`POST /reviews`), reading a card's schedule, scheduling's `/health` | `GET /study/{deck_id}/next` and `/due-count` answer `503 {"error":"content service unavailable"}` within the timeout. The Study page says "Study is unavailable right now (content service unavailable)." Decks cannot be listed, because that is content's own job. |
| scheduling | listing, creating and deleting decks and cards | The Decks page lists the decks with "—" in the due column and says "Scheduling is unavailable: due counts cannot be shown right now." The Study page says "Study is unavailable right now". |

Neither `/health` calls the other service. The recorded responses, with timings, are in [`docs/evidence/partial-failure.md`](docs/evidence/partial-failure.md).

## Operations notes

- **Cold start.** After an idle period both Container Apps are at zero replicas and both databases are paused. Measured on 2026-11-20 after a night without requests: the first request to content was answered after 66 s and the first to scheduling after 60 s, both with 200 ([`docs/evidence/cold-start.txt`](docs/evidence/cold-start.txt)). The service retries its database connection while the database resumes, and the UI shows "The service is starting up… retrying…" and repeats a read every 5 seconds. The next requests are fast.
- **A migration that fails in production.** The migration is rolled back, the service does not start, and the deploy job fails at its health gate, so the run is red and the previous revision stays active. Nothing is half applied. The fix is a new commit with a corrected migration file; an applied file is never edited (ADR-7).
- **Logs.** Each service writes one line per request and one line per applied migration to stdout: `docker compose logs content` locally, `az containerapp logs show` on Azure.

## Project layout

```
docker-compose.yml          the local stack: SQL Server, db-init, content, scheduling, ui
db/init.sql                 local only: the two databases and their logins
services/
  content/                  app/ (factory, config, db, migrate, repository, routes), migrations/, tests/,
                            Dockerfile, gunicorn.conf.py, openapi.yaml, requirements*.txt
  scheduling/               the same, plus app/content_client.py (the call to content) and app/sm2.py
ui/                         index.html, deck.html, study.html, app.js, config.js, style.css
tests/integration/          tests across both services, against the compose stack
infra/                      azure-setup.sh and azure-user.sql: the one-time Azure setup
.github/workflows/          pipeline.yml: CI and deployment
system.yaml                 the system in one file, validated against system.schema.json
docs/                       diagrams (PNG and Mermaid source) and evidence/
ADR.md, AI_USAGE.md         process logs
```

## Process

- [`ADR.md`](ADR.md): ten architecture decision records. 1 to 5 are from Assignment 1; 6 to 10 cover the split, the data per service, the hosting on Azure, the pipeline gates and the API gateway that was not built.
- [`AI_USAGE.md`](AI_USAGE.md): one row per AI interaction, with what was accepted, modified or rejected, and how the resulting code works.
- [`system.yaml`](system.yaml), [`services/content/openapi.yaml`](services/content/openapi.yaml), [`services/scheduling/openapi.yaml`](services/scheduling/openapi.yaml): the machine-readable description of the system, checked in CI.
- [`docs/evidence/`](docs/evidence/): migration, partial failure, pipeline and cold start.

### Incident log

No secret has been committed to this repository. Nothing to report.
