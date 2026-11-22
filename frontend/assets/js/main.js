let currentState = null;
let selectedCardForModal = null;
let timerSeconds = 0;
let timerInterval = null;

const uiState = {
  markMode: false,
  marks: {}, // { "A1": 1 }
  activeHighlightSource: null,
  highlightedCells: [],
  hintCell: null
};

function setBanner(msg, type = "", shouldShake = false) {
  const banner = document.getElementById("status-banner");
  banner.textContent = msg;
  banner.className = `banner ${type}`.trim();
  if (shouldShake) {
    banner.classList.remove("shake");
    void banner.offsetWidth;
    banner.classList.add("shake");
  }
}

function startTimer() {
  if (timerInterval) clearInterval(timerInterval);
  timerSeconds = 0;
  document.getElementById("timer").textContent = "00:00";
  timerInterval = setInterval(() => {
    timerSeconds++;
    const mins = String(Math.floor(timerSeconds / 60)).padStart(2, "0");
    const secs = String(timerSeconds % 60).padStart(2, "0");
    document.getElementById("timer").textContent = `${mins}:${secs}`;
  }, 1000);
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}

function getCardByCell(cell) {
  if (!currentState || !currentState.cards) return null;
  return currentState.cards.find((c) => c.cell === cell) || null;
}

function openVerdictModal(card) {
  selectedCardForModal = card;
  document.getElementById("modal-cell").textContent = card.cell;
  document.getElementById("modal-name").textContent = card.name;
  document.getElementById("modal-prof").textContent = card.profession;

  const modalAvatarEl = document.getElementById("modal-avatar");
  if (modalAvatarEl && window.createAvatarSVG) {
    modalAvatarEl.innerHTML = window.createAvatarSVG(card.name, card.profession, 74);
  }

  document.getElementById("verdict-modal").classList.remove("hidden");
}

function closeVerdictModal() {
  selectedCardForModal = null;
  document.getElementById("verdict-modal").classList.add("hidden");
}

function updateMarkButtons() {
  const markBtn = document.getElementById("btn-mark");
  markBtn.innerHTML = `<span class="mark-preview" aria-hidden="true"></span>Mark: ${uiState.markMode ? "ON" : "OFF"}`;
  markBtn.classList.toggle("active-toggle", uiState.markMode);
  markBtn.setAttribute("aria-pressed", String(uiState.markMode));

  const hasAnyMarks = Object.values(uiState.marks).some((idx) => idx > 0);
  const clearBtn = document.getElementById("btn-clear-marks");
  if (clearBtn) {
    clearBtn.classList.toggle("hidden", !hasAnyMarks);
  }
}

function cycleMarkForCell(cell) {
  const card = getCardByCell(cell);
  if (!card || card.is_revealed) return;
  const next = ((uiState.marks[cell] || 0) + 1) % MARK_COLORS.length;
  uiState.marks[cell] = next;
  updateMarkButtons();
  refreshBoard();
}

function refreshBoard() {
  if (!currentState) return;
  renderBoard(currentState, uiState, {
    onCycleMark(cell) {
      cycleMarkForCell(cell);
    },
    onCardClick(cell) {
      const card = getCardByCell(cell);
      if (!card) return;

      if (!card.is_revealed) {
        if (uiState.markMode) {
          cycleMarkForCell(card.cell);
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
    if (uiState.hintCell === cell) uiState.hintCell = null;
    delete uiState.marks[cell];
    updateMarkButtons();

    setBanner(res.message || `${cell} confirmed as ${status}.`, "success");
    if (currentState.is_solved) {
      stopTimer();
      setBanner("Puzzle Solved! All characters deduced logically.", "success");
    }
  } else {
    triggerCardShake(cell);
    setBanner(
      res.message || `${res.result}: Cannot confirm ${cell} as ${status}.`,
      "error",
      true
    );
  }
  refreshBoard();
}

function syncPuzzleDropdown(selectEl, puzzleId) {
  if (!selectEl || !puzzleId) return;
  for (const opt of selectEl.options) {
    if (opt.value === puzzleId || opt.textContent.includes(puzzleId)) {
      selectEl.value = opt.value;
      return;
    }
  }
}

async function init() {
  const selectEl = document.getElementById("puzzle-select");
  const fileInputEl = document.getElementById("file-upload");
  const modalEl = document.getElementById("verdict-modal");

  // 1. Load puzzle list
  const listRes = await fetchPuzzles();
  if (listRes.ok && Array.isArray(listRes.puzzles) && listRes.puzzles.length > 0) {
    selectEl.innerHTML = listRes.puzzles
      .map((p) => `<option value="${p.path || p.id}">${p.name}</option>`)
      .join("");
  }

  // 2. Load initial state and sync dropdown
  const stateRes = await fetchState();
  if (stateRes.ok && stateRes.state) {
    currentState = stateRes.state;
    syncPuzzleDropdown(selectEl, currentState.puzzle_id);
    updateMarkButtons();
    refreshBoard();
    if (!currentState.is_solved) startTimer();
  }

  // 3. Puzzle dropdown change
  selectEl.addEventListener("change", async (e) => {
    if (!e.target.value) return;
    const res = await loadPuzzle({ path: e.target.value });
    if (res.ok && res.state) {
      currentState = res.state;
      uiState.marks = {};
      uiState.activeHighlightSource = null;
      uiState.highlightedCells = [];
      uiState.hintCell = null;
      updateMarkButtons();
      refreshBoard();
      startTimer();
      setBanner(`Loaded puzzle: ${currentState.puzzle_id}`);
    } else {
      setBanner(res.message || "Failed to load selected puzzle.", "error", true);
    }
  });

  // 4. Upload custom JSON file
  fileInputEl.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (ev) => {
      try {
        const puzzleJson = JSON.parse(ev.target.result);
        const res = await loadPuzzle({ puzzle: puzzleJson });
        if (res.ok && res.state) {
          currentState = res.state;
          uiState.marks = {};
          uiState.activeHighlightSource = null;
          uiState.highlightedCells = [];
          uiState.hintCell = null;
          selectEl.value = "";
          updateMarkButtons();
          refreshBoard();
          startTimer();
          setBanner(`Uploaded puzzle: ${currentState.puzzle_id}`, "success");
        } else {
          setBanner(res.message || "Puzzle validation failed.", "error", true);
        }
      } catch {
        setBanner("Invalid JSON file format.", "error", true);
      } finally {
        fileInputEl.value = "";
      }
    };
    reader.readAsText(file);
  });

  // 5. Restart button
  document.getElementById("btn-restart").addEventListener("click", async () => {
    const res = await restartPuzzle();
    if (res.ok && res.state) {
      currentState = res.state;
      uiState.marks = {};
      uiState.activeHighlightSource = null;
      uiState.highlightedCells = [];
      uiState.hintCell = null;
      updateMarkButtons();
      refreshBoard();
      startTimer();
      setBanner("Puzzle reset to initial state.");
    }
  });

  // 6. Mark mode & Clear marks buttons
  document.getElementById("btn-mark").addEventListener("click", () => {
    uiState.markMode = !uiState.markMode;
    updateMarkButtons();
  });

  document.getElementById("btn-clear-marks").addEventListener("click", () => {
    uiState.marks = {};
    updateMarkButtons();
    refreshBoard();
  });

  // 7. Hint button (Subsystem C integration hook)
  document.getElementById("btn-hint").addEventListener("click", async () => {
    if (!currentState || currentState.is_solved) return;
    const res = await fetchHint();
    if (res.ok && res.cell) {
      uiState.hintCell = res.cell;
      refreshBoard();
      setBanner(res.message || `Hint: Check cell ${res.cell}.`, "hint");
    } else {
      setBanner(res.message || "No hint available.", "error", true);
    }
  });

  // 8. Modal buttons & backdrop/keyboard interactions
  document.getElementById("modal-close").addEventListener("click", closeVerdictModal);
  document.getElementById("btn-innocent").addEventListener("click", () => handleVerdict("INNOCENT"));
  document.getElementById("btn-criminal").addEventListener("click", () => handleVerdict("CRIMINAL"));

  modalEl.addEventListener("click", (e) => {
    if (e.target === modalEl) closeVerdictModal();
  });

  document.addEventListener("keydown", (e) => {
    const isModalOpen = !modalEl.classList.contains("hidden");
    if (isModalOpen) {
      if (e.key === "Escape") {
        closeVerdictModal();
      } else if (e.key === "i" || e.key === "I" || e.key === "1") {
        handleVerdict("INNOCENT");
      } else if (e.key === "c" || e.key === "C" || e.key === "2") {
        handleVerdict("CRIMINAL");
      }
      return;
    }

    if (e.key === "Escape" && uiState.activeHighlightSource !== null) {
      uiState.activeHighlightSource = null;
      uiState.highlightedCells = [];
      refreshBoard();
    }
  });
}

window.addEventListener("DOMContentLoaded", init);