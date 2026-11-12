# Architecture Decision Records

## 1. Backend framework: Flask

Date: 2026-10-01

Status: Decided

Context: The app runs as one process that serves HTML pages and stores everything in one SQLite file. It only needs routing, templates and form handling.

Decision: I decided to use Flask with Jinja templates and the standard-library sqlite3 module.

Alternatives considered: Django (rejected: ORM, admin and auth add dependencies and files for features this app does not use). FastAPI (rejected: its advantage is async I/O, which does nothing for synchronous sqlite3 calls, and it would still need a template layer).

Consequences: Three third-party packages. No ORM means writing SQL by hand, which keeps the schema explicit.

## 2. Two feature domains as separate packages with a one-way seam

Date: 2026-10-01

Status: Decided

Context: The assignment asks for two backend feature domains. Content (decks and cards) and Scheduling (SM-2 and reviews) do different jobs, so I want to test and explain each one separately.

Decision: `app/content/` and `app/scheduling/` are sibling packages. Their domain modules (`repository.py`, `sm2.py`) never import each other; only `routes.py` modules call both, and Scheduling only receives card ids, never card content.

Alternatives considered: A single models module with all tables and logic (rejected: quicker to write, but scheduling rules would get mixed into deck and card code, and SM-2 could not be tested without the rest of the app).

Consequences: Slight duplication (each package has its own repository and routes). The rule is enforced by review, not tooling. The study route is the one place both domains meet.


## 3. Scheduling state in card_schedule, history in reviews

Date: 2026-10-05

Status: Decided

Context: SM-2 decides when you see cards again, for that we need a ease factor (how easy it was for you to answer), repetitons (how many times you got it right), interval (when you'll see it again) and due date (when it will show up again)

Decision: Im going to use two tables: one for the card schedule which has primary key of card_id, the ease factor (2.5 default), repetitions interval and due date. The second table is reviews: each time you rate a card a new row gets added with card_id, time of reviewing, grade, and interval before & after to see how the gap evolves. I decided to use a ON DELETE CASCADE to delete a cards schedule and reviews when card_id is deleted.

Alternatives considered: I could have had ease_factor and due_at in the cards table, but cards belongs to content, whos code would be holding schedulings data and I would have had to migrate the table in the future.

Consequences: The study query happens in two steps. Cards with no schedule are due now, since it doesnt have a schedule row, so the moment you add a card, it is asked. Due_at has an index which makes the lookup for due cards faster.

## 4. Testing: pure scheduler and repositories first, routes covered only by smoke tests

Date: 2026-10-07

Status: Decided

Context: At least 70% coverage on core logic, the core logic in this app is the SM-2 math and the two repositories, not the routing which connects them to the web pages.

Decision: I test sm2.py in detail, the interval growth, lapses, the ease floor, grades which are invalid and the due dates. Both repositories are tested against a temp SQLite database. The routes are simple enough that all I need are 4 tests: the app start, redirects, the creation of the decks and studying an empty deck.

Alternatives considered: Testing the routes with Flasks test client, I rejected it cause passing route tests doesnt show that the scheduler calculated the right interval.

Consequences: Coverage is measured over all of app, routes are included, making the actual number slightly higher. Since the tests use a SQLite file, we also check that deleting cards removes the schedule and review row.

## 5. Not built: user accounts

Date: 2026-10-08

Status: Decided

Context: User accounts with a login page are the next feature I should add, and its left up to me whether to build them.

Decision: The app has one user and no login, whoever runs it has access to all the decks.

Alternatives considered: Flask-login with a users table. I didnt do it because it adds another dependency and another table, which I would have had to integrate with both domains, and content and scheduling dont need to know who owns the decks.

Consequences: The app cant be shared by more than one person, adding login later means just adding a owner_id column to decks, and scheduling would remain unchanged.

## 6. The split: content and scheduling as two services along the ADR-2 seam

Date: 2026-11-11

Status: Decided

Context: Assignment 2 requires one service per feature domain, each with its own container and database. I had already separated `app/content` from `app/scheduling` inside the monolith and allowed a single call across that boundary, which is the study route reading cards from the content repository.

Decision: I split the monolith along the boundary from ADR-2. `services/content` owns decks and cards and `services/scheduling` owns SM-2 state and reviews. The single call becomes a single HTTP request in which scheduling calls `GET /decks/{id}/cards` on content, with a 2 s timeout. Scheduling works out which cards are due and the due-count badge on the server, so the UI asks each service only for that service's own data. The common boilerplate (`db.py`, `migrate.py`, `logging_.py`) is copied into each service folder instead of shared, because each Dockerfile builds from its own folder.

Alternatives considered:
- Combining the study flow in the browser. Rejected: the UI would need both the full card list and the schedule state to decide what is due. That would mean reimplementing `due_card_ids` in JavaScript, and I could no longer enforce the rule that scheduling knows only card ids.
- Moving `card_schedule` into content so that no service-to-service call is needed. Rejected: content would then own scheduling data, which is what ADR-3 set out to avoid.

Consequences: Every study step costs one HTTP round trip between the services, and the study path returns 503 when content is down. The boundary in ADR-2 holds since no table had to move. The services share no code at runtime, so `db.py`, `migrate.py` and `logging_.py` exist twice on purpose and a fix in one has to be made in the other.
