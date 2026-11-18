let currentState = null;
let selectedCardForModal = null;
let timerSeconds = 0;
let timerInterval = null;

const uiState = {
  markMode: false,
  marks: {}, // { "A1": 1 }
  activeHighlightSource: null,
  highlightedCells: []
};

function setBanner(msg, type = "") {
  const banner = document.getElementById("status-banner");
  banner.textContent = msg;
  banner.className = `banner ${type}`;
}

function startTimer() {
  if (timerInterval) clearInterval(timerInterval);
  timerSeconds = 0;
  timerInterval = setInterval(() => {
    timerSeconds++;
    const mins = String(Math.floor(timerSeconds / 60)).padStart(2, "0");
    const secs = String(timerSeconds % 60).padStart(2, "0");
    document.getElementById("timer").textContent = `${mins}:${secs}`;
  }, 1000);
}

function openVerdictModal(card) {
  selectedCardForModal = card;
  document.getElementById("modal-cell").textContent = card.cell;
  document.getElementById("modal-name").textContent = card.name;
  document.getElementById("modal-prof").textContent = card.profession;
  document.getElementById("verdict-modal").classList.remove("hidden");
}

function closeVerdictModal() {
  selectedCardForModal = null;
  document.getElementById("verdict-modal").classList.add("hidden");
}

function refreshBoard() {
  if (!currentState) return;
  renderBoard(currentState, uiState, {
    onCardClick(card) {
      if (!card.is_revealed) {
        if (uiState.markMode) {
          const next = ((uiState.marks[card.cell] || 0) + 1) % MARK_COLORS.length;
          uiState.marks[card.cell] = next;
          refreshBoard();
        } else {
          openVerdictModal(card);
        }
      } else {
        // Toggle clue region highlight
        if (uiState.activeHighlightSource === card.cell) {
          uiState.activeHighlightSource = null;
          uiState.highlightedCells = [];
        } else {
          uiState.activeHighlightSource = card.cell;
          uiState.highlightedCells = card.highlight_cells || [];
        }
        refreshBoard();
      }
    }
  });
}

async function handleVerdict(status) {
  if (!selectedCardForModal) return;
  const cell = selectedCardForModal.cell;
  closeVerdictModal();

  const res = await submitVerdict(cell, status);
  if (res.state) currentState = res.state;

  if (res.result === "ACCEPTED") {
    uiState.activeHighlightSource = null;
    uiState.highlightedCells = [];
    setBanner(res.message || `${cell} marked as ${status}.`, "success");
    if (currentState.is_solved) {
      clearInterval(timerInterval);
      setBanner("Puzzle Solved! All characters deduced logically.", "success");
    }
  } else {
    setBanner(res.message || `${res.result}: Cannot confirm ${cell} as ${status}.`, "error");
  }
  refreshBoard();
}

async function init() {
  // Load puzzle list
  const listRes = await fetchPuzzles();
  const selectEl = document.getElementById("puzzle-select");
  if (listRes.ok && listRes.puzzles && listRes.puzzles.length > 0) {
    selectEl.innerHTML = listRes.puzzles
      .map((p) => `<option value="${p.path || p.id}">${p.name}</option>`)
      .join("");
  }

  // Load initial state
  const stateRes = await fetchState();
  if (stateRes.ok) {
    currentState = stateRes.state;
    refreshBoard();
    startTimer();
  }

  // Controls listeners
  selectEl.addEventListener("change", async (e) => {
    const res = await loadPuzzle({ path: e.target.value });
    if (res.ok) {
      currentState = res.state;
      uiState.marks = {};
      uiState.activeHighlightSource = null;
      refreshBoard();
      startTimer();
      setBanner(`Loaded puzzle: ${currentState.puzzle_id}`);
    }
  });

  document.getElementById("file-upload").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (ev) => {
      try {
        const puzzleJson = JSON.parse(ev.target.result);
        const res = await loadPuzzle({ puzzle: puzzleJson });
        if (res.ok) {
          currentState = res.state;
          uiState.marks = {};
          uiState.activeHighlightSource = null;
          refreshBoard();
          startTimer();
          setBanner(`Uploaded puzzle: ${currentState.puzzle_id}`, "success");
        }
      } catch {
        setBanner("Invalid JSON file format.", "error");
      }
    };
    reader.readAsText(file);
  });

  document.getElementById("btn-restart").addEventListener("click", async () => {
    const res = await restartPuzzle();
    if (res.ok) {
      currentState = res.state;
      uiState.marks = {};
      uiState.activeHighlightSource = null;
      refreshBoard();
      startTimer();
      setBanner("Puzzle reset to initial state.");
    }
  });

  document.getElementById("btn-mark").addEventListener("click", (e) => {
    uiState.markMode = !uiState.markMode;
    e.target.textContent = `Mark: ${uiState.markMode ? "ON" : "OFF"}`;
    e.target.classList.toggle("active-toggle", uiState.markMode);
  });

  document.getElementById("modal-close").addEventListener("click", closeVerdictModal);
  document.getElementById("btn-innocent").addEventListener("click", () => handleVerdict("INNOCENT"));
  document.getElementById("btn-criminal").addEventListener("click", () => handleVerdict("CRIMINAL"));
}

window.addEventListener("DOMContentLoaded", init);