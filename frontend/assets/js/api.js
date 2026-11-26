// API client for the Griductive web server (frontend/gui/app.py).
// The browser never holds the hidden solution: every decision is made server-side.

async function requestJson(url, options = {}) {
  try {
    const res = await fetch(url, options);
    return await res.json();
  } catch (err) {
    const message = "Cannot reach the game server. Is `python main.py` running?";
    return { ok: false, error: message, message };
  }
}

function postJson(url, payload) {
  const options = { method: "POST" };
  if (payload !== undefined) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(payload);
  }
  return requestJson(url, options);
}

function fetchPuzzles() {
  return requestJson("/api/puzzles");
}

function fetchState() {
  return requestJson("/api/state");
}

function loadPuzzle(payload) {
  return postJson("/api/load", payload);
}

function restartPuzzle() {
  return postJson("/api/restart");
}

function submitVerdict(cell, status) {
  return postJson("/api/verdict", { cell, status });
}

// Agent endpoints (subsystem C): hint / single step.
function fetchHint() {
  return postJson("/api/hint");
}

function stepAgent() {
  return postJson("/api/step");
}
