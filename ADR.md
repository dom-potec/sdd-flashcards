# Architecture Decision Records

<!-- Dom: rewrite Context in your own words before committing -->
## 1. Backend framework: Flask
Date: 2026-10-01
Status: Decided
Context: The app is a single process serving HTML from one SQLite file. It needs routing, templates and form handling, and nothing else.
Decision: Flask with Jinja templates and the standard-library sqlite3 module.
Alternatives considered: Django (rejected: ORM, admin and auth add dependencies and files for features this app does not use). FastAPI (rejected: its advantage is async I/O, which does nothing for synchronous sqlite3 calls, and it would still need a template layer).
Consequences: Three third-party packages. No ORM means writing SQL by hand, which keeps the schema explicit and makes ADR-3 concrete.
