// Where the two services live. These are the local docker compose values.
// The deploy job overwrites this file with the Azure URLs; nothing else in ui/ changes between environments.
window.CONFIG = {
  CONTENT_URL: "http://localhost:8000",
  SCHEDULING_URL: "http://localhost:8001",
};
