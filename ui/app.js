// Page logic for the static UI. No framework and no build step.
// Decks and cards come from the content service; what is due and the grading go to the scheduling service.

const CONTENT = window.CONFIG.CONTENT_URL;
const SCHEDULING = window.CONFIG.SCHEDULING_URL;

const GRADES = ["Blackout", "Wrong", "Almost", "Hard", "Good", "Easy"]; // index = grade 0-5

// On Azure the services scale to zero. The first request after a quiet period gets no usable answer
// while the container starts and the database resumes: either the browser reports a network error, or
// Azure itself answers 502/503/504 without the JSON body the services always send.
const STARTUP_RETRIES = 6;
const STARTUP_WAIT_MS = 5000;
const STARTING_UP = "The service is starting up. This can take a minute";

// One request to a service. Returns the parsed JSON (null for 204 No Content).
// Throws an Error carrying the service's own message when the status is not 2xx.
// While a service is starting up, a GET is tried again every few seconds and the page says so.
// Anything that writes is not repeated, so nothing is saved twice: the user is asked to try again.
async function api(base, path, options = {}) {
  const isRead = !options.method || options.method === "GET";
  for (let attempt = 0; ; attempt++) {
    let res = null;
    let body = {};
    try {
      res = await fetch(base + path, { headers: { "Content-Type": "application/json" }, ...options });
      if (res.status === 204) return null;
      body = await res.json().catch(() => ({}));
    } catch (e) {
      res = null; // the service could not be reached at all
    }
    const startingUp = !res || (res.status >= 502 && res.status <= 504 && !body.error);
    if (!startingUp) {
      if (attempt > 0) clearNotice();
      if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
      return body;
    }
    if (!isRead) throw new Error(`${STARTING_UP}, then try again`);
    if (attempt >= STARTUP_RETRIES) throw new Error("the service did not answer, try again in a minute");
    showNotice(`${STARTING_UP}, retrying…`);
    await new Promise((resolve) => setTimeout(resolve, STARTUP_WAIT_MS));
  }
}

function byId(id) {
  return document.getElementById(id);
}

// Build an element with plain text inside. textContent, never innerHTML: card text is user input.
function el(tag, text = "", attrs = {}) {
  const node = document.createElement(tag);
  node.textContent = text;
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
  return node;
}

function showNotice(message) {
  byId("notice").textContent = message;
  byId("notice").hidden = false;
}

function clearNotice() {
  byId("notice").hidden = true;
}

function queryNumber(name) {
  return Number(new URLSearchParams(location.search).get(name));
}

function post(body) {
  return { method: "POST", body: JSON.stringify(body) };
}

// ---------- index.html: list of decks ----------

async function loadDecks() {
  let decks;
  try {
    decks = await api(CONTENT, "/decks");
  } catch (e) {
    showNotice(`Decks are unavailable right now (${e.message}).`);
    return;
  }
  byId("decks").hidden = decks.length === 0;
  byId("empty").hidden = decks.length > 0;

  const rows = byId("decks").querySelector("tbody");
  rows.replaceChildren();
  for (const deck of decks) {
    const row = el("tr");
    const name = el("td");
    name.append(el("a", deck.name, { href: `deck.html?id=${deck.id}` }));
    const due = el("td", "…", { id: `due-${deck.id}` });
    const study = el("td");
    study.append(el("a", "Study", { href: `study.html?deck=${deck.id}` }));
    const remove = el("td");
    const button = el("button", "Delete", { type: "button" });
    button.addEventListener("click", () => deleteDeck(deck.id));
    remove.append(button);
    row.append(name, el("td", deck.description), el("td", String(deck.card_count)), due, study, remove);
    rows.append(row);
  }
  await loadDueCounts(decks);
}

// The due badge needs the scheduling service. If it is down the decks still show, with a dash.
async function loadDueCounts(decks) {
  const results = await Promise.allSettled(
    decks.map((deck) => api(SCHEDULING, `/study/${deck.id}/due-count`))
  );
  results.forEach((result, i) => {
    const cell = byId(`due-${decks[i].id}`);
    cell.textContent = result.status === "fulfilled" ? String(result.value.due) : "—";
  });
  if (results.some((result) => result.status === "rejected")) {
    showNotice("Scheduling is unavailable: due counts cannot be shown right now.");
  }
}

async function deleteDeck(deckId) {
  clearNotice();
  try {
    await api(CONTENT, `/decks/${deckId}`, { method: "DELETE" });
  } catch (e) {
    showNotice(`Could not delete the deck (${e.message}).`);
    return;
  }
  await loadDecks();
}

function initIndex() {
  byId("new-deck").addEventListener("submit", async (event) => {
    event.preventDefault();
    clearNotice();
    const form = event.target;
    try {
      await api(CONTENT, "/decks", post({ name: form.name.value, description: form.description.value }));
    } catch (e) {
      showNotice(`Could not create the deck (${e.message}).`);
      return;
    }
    form.reset();
    await loadDecks();
  });
  loadDecks();
}

// ---------- deck.html?id=N: one deck and its cards ----------

async function loadDeck(deckId) {
  let deck, cards;
  try {
    deck = await api(CONTENT, `/decks/${deckId}`);
    cards = await api(CONTENT, `/decks/${deckId}/cards`);
  } catch (e) {
    showNotice(`This deck is unavailable right now (${e.message}).`);
    return;
  }
  document.title = deck.name;
  byId("deck-name").textContent = deck.name;
  byId("deck-description").textContent = deck.description;
  byId("cards").hidden = cards.length === 0;
  byId("empty").hidden = cards.length > 0;

  const rows = byId("cards").querySelector("tbody");
  rows.replaceChildren();
  for (const card of cards) {
    const row = el("tr");
    const remove = el("td");
    const button = el("button", "Delete", { type: "button" });
    button.addEventListener("click", () => deleteCard(deckId, card.id));
    remove.append(button);
    row.append(el("td", card.front), el("td", card.back), remove);
    rows.append(row);
  }
}

async function deleteCard(deckId, cardId) {
  clearNotice();
  try {
    await api(CONTENT, `/cards/${cardId}`, { method: "DELETE" });
  } catch (e) {
    showNotice(`Could not delete the card (${e.message}).`);
    return;
  }
  await loadDeck(deckId);
}

function initDeck() {
  const deckId = queryNumber("id");
  byId("study-link").href = `study.html?deck=${deckId}`;
  byId("new-card").addEventListener("submit", async (event) => {
    event.preventDefault();
    clearNotice();
    const form = event.target;
    try {
      await api(CONTENT, `/decks/${deckId}/cards`, post({ front: form.front.value, back: form.back.value }));
    } catch (e) {
      showNotice(`Could not add the card (${e.message}).`);
      return;
    }
    form.reset();
    await loadDeck(deckId);
  });
  loadDeck(deckId);
}

// ---------- study.html?deck=N: one card at a time ----------

// Asks scheduling for the next due card. Scheduling gets the card text from content itself,
// so this page never calls content for cards.
async function loadNextCard(deckId) {
  clearNotice();
  byId("card").hidden = true;
  byId("done").hidden = true;
  let next;
  try {
    next = await api(SCHEDULING, `/study/${deckId}/next`);
  } catch (e) {
    showNotice(`Study is unavailable right now (${e.message}).`);
    return;
  }
  if (next.done) {
    byId("done").hidden = false;
    return;
  }
  byId("remaining").textContent = String(next.remaining);
  byId("front").textContent = next.card.front;
  byId("back").textContent = next.card.back;
  byId("answer").hidden = true;
  byId("show-answer").hidden = false;

  const grades = byId("grades");
  grades.replaceChildren();
  GRADES.forEach((label, grade) => {
    const button = el("button", `${grade} ${label}`, { type: "button" });
    button.addEventListener("click", () => gradeCard(deckId, next.card.id, grade));
    grades.append(button);
  });
  byId("card").hidden = false;
}

async function gradeCard(deckId, cardId, grade) {
  try {
    await api(SCHEDULING, "/reviews", post({ card_id: cardId, grade: grade }));
  } catch (e) {
    showNotice(`Could not save the grade (${e.message}).`);
    return;
  }
  await loadNextCard(deckId);
}

function initStudy() {
  const deckId = queryNumber("deck");
  byId("deck-link").href = `deck.html?id=${deckId}`;
  byId("show-answer").addEventListener("click", () => {
    byId("answer").hidden = false;
    byId("show-answer").hidden = true;
  });
  // The deck name is only a heading. If content cannot give it, the page still works.
  api(CONTENT, `/decks/${deckId}`)
    .then((deck) => {
      byId("deck-name").textContent = `Study: ${deck.name}`;
    })
    .catch(() => {});
  loadNextCard(deckId);
}

// Each page says which one it is with <body data-page="...">.
const PAGES = { index: initIndex, deck: initDeck, study: initStudy };
PAGES[document.body.dataset.page]();
