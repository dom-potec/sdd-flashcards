# Partial-failure evidence

What a user gets when one of the two services is down, recorded on 2026-11-21 against the local
`docker compose` stack, plus one read-only check on Azure. Nothing on Azure was stopped or changed for
this: stopping a deployed Container App by hand would be a manual change to infrastructure that only the
pipeline may change.

On this machine ports 8000, 8001 and 8080 were taken by another project, so the stack ran with the host
ports 18000 (content), 18001 (scheduling) and 18080 (UI). Nothing else differs from `docker-compose.yml`.
The data: one deck "Capitals" with two cards, card 1 reviewed once.

## Summary

| Situation | Request | Answer | Raw output |
|---|---|---|---|
| content stopped | `GET /study/1/next` on scheduling | `503 {"error":"content service unavailable"}` in 0.02 s | [content-down](partial-failure-content-down.txt) |
| content stopped | `GET /study/1/due-count` on scheduling | the same 503 | [content-down](partial-failure-content-down.txt) |
| content stopped | `GET /health` on scheduling | `200`, `db: ok` | [content-down](partial-failure-content-down.txt) |
| content stopped | `POST /reviews` on scheduling | `201`, the review is saved | [content-down](partial-failure-content-down.txt) |
| content stopped | `GET /cards/2/schedule` on scheduling | `200`, shows the review just saved | [content-down](partial-failure-content-down.txt) |
| content frozen, never answers | `GET /study/1/next` on scheduling | the same 503 after 2.03 s (the timeout is 2 s) | [content-slow](partial-failure-content-slow.txt) |
| content frozen | `POST /reviews` on scheduling | `201` in 0.04 s | [content-slow](partial-failure-content-slow.txt) |
| content back | `GET /study/1/next` on scheduling | `200` at once, no restart needed | [content-slow](partial-failure-content-slow.txt) |
| scheduling stopped | `GET /health`, `GET /decks`, `GET /decks/1/cards`, `POST /decks/1/cards` on content | `200`, `200`, `200`, `201` | [scheduling-down](partial-failure-scheduling-down.txt) |
| Azure, content scaled to zero | `GET /health` on scheduling | `200`, and content still has no running container afterwards | [azure-health](partial-failure-azure-health.txt) |

"Frozen" is `docker compose pause content`: the container keeps its address but answers nothing, which is
how a hung service looks from outside. It is the case that needs the timeout. A stopped container is
refused immediately, so the 503 comes back in milliseconds.

## The response

```
$ curl -i http://localhost:18001/study/1/next
HTTP/1.1 503 SERVICE UNAVAILABLE
Content-Type: application/json
Access-Control-Allow-Origin: http://localhost:18080

{"error":"content service unavailable"}

[503 in 2.029345 s]
```

## What the user sees in the UI

Read from the pages in Chrome, in real time, with one service stopped.

| Stopped | Page | What it shows |
|---|---|---|
| content | Study | "Study is unavailable right now (content service unavailable)." at once. No card is shown. |
| content | Decks | "The service is starting up. This can take a minute, retrying…" for 30 s, then "Decks are unavailable right now (the service did not answer, try again in a minute)." |
| scheduling | Decks | The decks are listed and can be opened, added to and deleted. The "due" column shows "…" while the page retries for 30 s, then "—" and "Scheduling is unavailable: due counts cannot be shown right now." |
| scheduling | Study | The deck name is shown (it comes from content). "The service is starting up… retrying…" for 30 s, then "Study is unavailable right now (the service did not answer, try again in a minute)." |

The 30 seconds of retrying exist because on Azure a service that scaled to zero looks the same to the
browser as one that is down: no answer yet. The page cannot tell the two apart, so it waits for the length
of a cold start before it gives up. A 503 that carries the service's own JSON `error` is not retried,
because then the service is up and has said what is wrong.

## A fault found while recording this

With content stopped, the Study page first showed the right notice and then replaced it with "The service
is starting up… retrying…", and that text stayed. The page asks content for the deck name, only to use it
as the heading, and since the retry was added on 19 Nov that request wrote its retry message over the
notice of the request that matters. The request helper in `ui/app.js` now takes a `quiet` flag: the
heading request is still retried, but it never writes or clears the notice. The table above was recorded
after the fix.
