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
