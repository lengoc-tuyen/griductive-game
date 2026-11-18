// Main controller for Griductive Web UI

let currentState = null;
let selectedCardForModal = null;
let timerSeconds = 0;
let timerInterval = null;
let isPaused = false;
let puzzleCatalog = [];
let pickerSelectedSize = null;

const SOLVED_STORAGE_KEY = "griductive_solved_v1";

const uiState = {
  markMode: false,
  marks: {},               // { "A1": 1..4 }
  activeClueCells: [],     // [] | [cell] (focus mode) | [c1, c2, ...] (multi-clue compare via Shift+Click)
  focusedGroupIndex: null, // number | null (clicking a colored keyword/name inside the active clue)
  crossedClues: new Set(), // Set of revealed cell ids whose clue text is crossed out
  newlyRevealed: new Set()
};

function escText(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatTime(totalSec) {
  const mins = String(Math.floor(totalSec / 60)).padStart(2, "0");
  const secs = String(totalSec % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

function getSolvedRecords() {
  try {
    const raw = localStorage.getItem(SOLVED_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function recordPuzzleSolved(puzzleId, elapsedSec) {
  if (!puzzleId) return;
  try {
    const records = getSolvedRecords();
    const prev = records[puzzleId];
    const best = prev && typeof prev.bestTimeSec === "number"
      ? Math.min(prev.bestTimeSec, elapsedSec)
      : elapsedSec;
    records[puzzleId] = { bestTimeSec: best };
    localStorage.setItem(SOLVED_STORAGE_KEY, JSON.stringify(records));
  } catch {
    // Ignore storage quota / privacy mode errors
  }
}

function detectDifficulty(puzzleId, fallback) {
  if (fallback && fallback !== "custom") return String(fallback).toLowerCase();
  const low = String(puzzleId || "").toLowerCase();
  if (low.includes("easy")) return "easy";
  if (low.includes("medium")) return "medium";
  if (low.includes("hard")) return "hard";
  if (low.includes("basic")) return "basic";
  return "custom";
}

function formatShortPuzzleTitle(puzzleId, size) {
  let clean = String(puzzleId || "Puzzle");
  clean = clean.replace(/^puzzle_/i, "").replace(/^test_/i, "");
  if (size) {
    clean = clean.replace(new RegExp(`^${size}x${size}[_\\-\\s]*`, "i"), "");
  }
  clean = clean.replace(/[_-]+/g, " ").trim();
  if (!clean) return "Puzzle";
  return clean.replace(/\b\w/g, (ch) => ch.toUpperCase());
}

function updateHeaderAndSidebarMeta() {
  if (!currentState) return;
  const diff = detectDifficulty(currentState.puzzle_id);
  const diffEl = document.getElementById("meta-diff");
  if (diffEl) diffEl.textContent = diff.toUpperCase();

  const btnLabel = document.getElementById("picker-btn-label");
  if (btnLabel) {
    const shortName = formatShortPuzzleTitle(currentState.puzzle_id, currentState.size);
    btnLabel.textContent = `${currentState.size}×${currentState.size} · ${shortName}`;
  }
}

function _runTimerTick() {
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    if (!isPaused) {
      timerSeconds++;
      document.getElementById("timer").textContent = formatTime(timerSeconds);
    }
  }, 1000);
}

function startTimer() {
  isPaused = false;
  timerSeconds = 0;
  document.getElementById("timer").textContent = "00:00";
  const dot = document.getElementById("timer-dot");
  if (dot) dot.classList.remove("paused");
  document.getElementById("page-layout").classList.remove("is-paused");
  document.getElementById("pause-modal").classList.add("hidden");
  _runTimerTick();
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}

function pauseGame() {
  if (isPaused || !currentState || currentState.is_solved) return;
  isPaused = true;
  closeVerdictModal();
  closePuzzlePicker();
  const dot = document.getElementById("timer-dot");
  if (dot) dot.classList.add("paused");
  document.getElementById("pause-time").textContent = formatTime(timerSeconds);
  document.getElementById("page-layout").classList.add("is-paused");
  document.getElementById("pause-modal").classList.remove("hidden");
}

function resumeGame() {
  if (!isPaused) return;
  isPaused = false;
  const dot = document.getElementById("timer-dot");
  if (dot) dot.classList.remove("paused");
  document.getElementById("page-layout").classList.remove("is-paused");
  document.getElementById("pause-modal").classList.add("hidden");
}

function openVerdictModal(card) {
  selectedCardForModal = card;
  document.getElementById("modal-name").textContent = card.name;
  document.getElementById("modal-meta").textContent = `${card.cell} · ${card.profession}`;
  const avatarContainer = document.getElementById("modal-avatar");
  if (avatarContainer && typeof createAvatarSVG === "function") {
    avatarContainer.innerHTML = createAvatarSVG(card.name, "avatar-modal");
  }
  document.getElementById("verdict-modal").classList.remove("hidden");
}

function closeVerdictModal() {
  selectedCardForModal = null;
  document.getElementById("verdict-modal").classList.add("hidden");
}

function openErrorModal({ kind, name, calledStatus, customTitle, customBody }) {
  const iconEl = document.getElementById("error-icon-circle");
  const titleEl = document.getElementById("error-title");
  const bodyEl = document.getElementById("error-body");

  const safeName = escText(name);
  const calledLower = String(calledStatus || "").toLowerCase();
  const oppositeLower = calledLower === "innocent" ? "criminal" : "innocent";

  if (customTitle || customBody) {
    iconEl.className = "notice-icon-circle contradicted";
    titleEl.textContent = customTitle || "Cannot load puzzle";
    bodyEl.innerHTML = escText(customBody || "Something went wrong.");
  } else if (kind === "NOT_PROVABLE") {
    iconEl.className = "notice-icon-circle warning";
    titleEl.textContent = "Conclusion not possible";
    bodyEl.innerHTML =
      `You can’t prove <strong>${safeName}</strong> is <strong>${calledLower}</strong> from the statements you’ve unlocked yet — ` +
      `there’s still a consistent case where ${safeName} is <strong>${oppositeLower}</strong>.<br>` +
      `Unlock more testimony first, or lean on a hint.`;
  } else {
    iconEl.className = "notice-icon-circle contradicted";
    titleEl.textContent = "Contradicts the clues";
    bodyEl.innerHTML =
      `Calling <strong>${safeName}</strong> <strong>${calledLower}</strong> contradicts the statements you’ve unlocked — ` +
      `the current clues logically force ${safeName} to be <strong>${oppositeLower}</strong>.`;
  }

  document.getElementById("error-modal").classList.remove("hidden");
}

function closeErrorModal() {
  document.getElementById("error-modal").classList.add("hidden");
}

function openVictoryModal() {
  if (!currentState) return;
  document.getElementById("victory-puzzle").textContent =
    `${currentState.size}×${currentState.size} · ${formatShortPuzzleTitle(currentState.puzzle_id, currentState.size)}`;
  document.getElementById("victory-time").textContent = formatTime(timerSeconds);
  document.getElementById("victory-count").textContent =
    `${currentState.proved_count} / ${currentState.total_cells}`;
  document.getElementById("victory-modal").classList.remove("hidden");
}

function closeVictoryModal() {
  document.getElementById("victory-modal").classList.add("hidden");
}

// ------------------------------------------------ Puzzle Picker Modal (Option 2)
function renderPuzzlePicker() {
  const tabsEl = document.getElementById("picker-size-tabs");
  const gridEl = document.getElementById("picker-puzzle-grid");
  if (!tabsEl || !gridEl) return;

  const solvedRecords = getSolvedRecords();
  const bySize = new Map();
  puzzleCatalog.forEach((p) => {
    const sz = p.size || 0;
    if (!bySize.has(sz)) bySize.set(sz, []);
    bySize.get(sz).push(p);
  });

  const sizes = Array.from(bySize.keys()).sort((a, b) => a - b);
  if (sizes.length === 0) {
    tabsEl.innerHTML = "";
    gridEl.innerHTML = `<div style="font-size:0.88rem;color:#676158;">No puzzles found. Use Load Custom JSON below.</div>`;
    return;
  }

  if (pickerSelectedSize === null || !bySize.has(pickerSelectedSize)) {
    const activeSize = currentState ? currentState.size : sizes[0];
    pickerSelectedSize = bySize.has(activeSize) ? activeSize : sizes[0];
  }

  // Render Size Tabs (3×3, 4×4, 5×5)
  tabsEl.innerHTML = "";
  sizes.forEach((sz) => {
    const list = bySize.get(sz) || [];
    const solvedCount = list.filter((p) => Boolean(solvedRecords[p.id])).length;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.role = "tab";
    btn.className = `picker-tab${sz === pickerSelectedSize ? " active" : ""}`;
    btn.innerHTML = `
      <span>${sz ? `${sz} × ${sz}` : "Other"}</span>
      <span class="picker-tab-count">${solvedCount}/${list.length}</span>
    `;
    btn.addEventListener("click", () => {
      pickerSelectedSize = sz;
      renderPuzzlePicker();
    });
    tabsEl.appendChild(btn);
  });

  // Render Puzzle Cards for selected size
  const activeList = bySize.get(pickerSelectedSize) || [];
  gridEl.innerHTML = "";
  activeList.forEach((p) => {
    const diff = detectDifficulty(p.id, p.difficulty);
    const shortTitle = formatShortPuzzleTitle(p.id, p.size);
    const record = solvedRecords[p.id];
    const isCurrent = currentState && currentState.puzzle_id === p.id;

    const item = document.createElement("button");
    item.type = "button";
    item.className = [
      "picker-item",
      isCurrent ? "is-current" : "",
      record ? "is-solved" : ""
    ].filter(Boolean).join(" ");

    const statusMeta = record
      ? `<span class="solved-tag">✓ Solved · ${formatTime(record.bestTimeSec)}</span>`
      : `<span>Unsolved</span>`;
    const playingTag = isCurrent ? `<span class="playing-tag">PLAYING</span>` : "";

    item.innerHTML = `
      <div class="picker-item-top">
        <span class="picker-item-title">${escText(shortTitle)}</span>
        <span class="diff-badge ${diff}">${escText(diff)}</span>
      </div>
      <div class="picker-item-meta">
        ${statusMeta}
        ${playingTag}
      </div>
    `;

    item.addEventListener("click", () => {
      closePuzzlePicker();
      loadSelectedPuzzle(p.path || p.id);
    });

    gridEl.appendChild(item);
  });
}

function openPuzzlePicker() {
  if (isPaused) return;
  closeVerdictModal();
  if (currentState && currentState.size) {
    pickerSelectedSize = currentState.size;
  }
  renderPuzzlePicker();
  document.getElementById("puzzle-picker-modal").classList.remove("hidden");
}

function closePuzzlePicker() {
  document.getElementById("puzzle-picker-modal").classList.add("hidden");
}

// ------------------------------------------------ Board & Clue Highlight Logic
function toggleClueHighlight(card, multi = false) {
  if (!card || !card.is_revealed) return;
  if (multi) {
    uiState.focusedGroupIndex = null;
    const idx = uiState.activeClueCells.indexOf(card.cell);
    if (idx >= 0) {
      uiState.activeClueCells.splice(idx, 1);
    } else {
      uiState.activeClueCells.push(card.cell);
    }
  } else {
    if (uiState.activeClueCells.length === 1 && uiState.activeClueCells[0] === card.cell) {
      uiState.activeClueCells = [];
      uiState.focusedGroupIndex = null;
    } else {
      uiState.activeClueCells = [card.cell];
      uiState.focusedGroupIndex = null;
    }
  }
  uiState.newlyRevealed = new Set();
  refreshBoard();
}

function toggleTokenFocus(card, groupIdx) {
  if (!card || !card.is_revealed) return;
  if (uiState.activeClueCells.length === 1 && uiState.activeClueCells[0] === card.cell) {
    if (uiState.focusedGroupIndex === groupIdx) {
      uiState.focusedGroupIndex = null;
    } else {
      uiState.focusedGroupIndex = groupIdx;
    }
  } else {
    uiState.activeClueCells = [card.cell];
    uiState.focusedGroupIndex = groupIdx;
  }
  uiState.newlyRevealed = new Set();
  refreshBoard();
}

function toggleClueCrossed(card) {
  if (!card || !card.is_revealed) return;
  if (uiState.crossedClues.has(card.cell)) {
    uiState.crossedClues.delete(card.cell);
  } else {
    uiState.crossedClues.add(card.cell);
  }
  uiState.newlyRevealed = new Set();
  refreshBoard();
}

function clearHighlight() {
  if (uiState.activeClueCells.length > 0 || uiState.focusedGroupIndex !== null) {
    uiState.activeClueCells = [];
    uiState.focusedGroupIndex = null;
    uiState.newlyRevealed = new Set();
    refreshBoard();
  }
}

function resetUiState() {
  uiState.marks = {};
  uiState.activeClueCells = [];
  uiState.focusedGroupIndex = null;
  uiState.crossedClues = new Set();
  uiState.newlyRevealed = new Set();
}

function refreshBoard() {
  if (!currentState) return;
  updateHeaderAndSidebarMeta();
  renderBoard(currentState, uiState, {
    onCardClick(card, shiftKey) {
      if (isPaused) return;
      if (!card.is_revealed) {
        if (uiState.markMode) {
          const next = ((uiState.marks[card.cell] || 0) + 1) % MARK_COLORS.length;
          uiState.marks[card.cell] = next;
          uiState.newlyRevealed = new Set();
          refreshBoard();
        } else {
          openVerdictModal(card);
        }
      } else {
        toggleClueHighlight(card, shiftKey);
      }
    },
    onClueSelect(card, shiftKey) {
      if (isPaused) return;
      toggleClueHighlight(card, shiftKey);
    },
    onTokenClick(card, groupIdx) {
      if (isPaused) return;
      toggleTokenFocus(card, groupIdx);
    },
    onClueLongPress(card) {
      if (isPaused) return;
      toggleClueCrossed(card);
    }
  });
}

async function handleVerdict(status) {
  if (!selectedCardForModal) return;
  const targetCard = selectedCardForModal;
  const cell = targetCard.cell;
  closeVerdictModal();

  const res = await submitVerdict(cell, status);
  if (res.state) currentState = res.state;

  if (res.result === "ACCEPTED") {
    uiState.newlyRevealed = new Set([cell]);
    delete uiState.marks[cell];
    uiState.activeClueCells = [];
    uiState.focusedGroupIndex = null;

    refreshBoard();

    if (currentState.is_solved) {
      stopTimer();
      recordPuzzleSolved(currentState.puzzle_id, timerSeconds);
      setTimeout(openVictoryModal, 520);
    }
  } else {
    uiState.newlyRevealed = new Set();
    refreshBoard();
    openErrorModal({
      kind: res.result,
      name: targetCard.name,
      calledStatus: status
    });
  }
}

async function loadSelectedPuzzle(path) {
  closeVictoryModal();
  closeErrorModal();
  closePuzzlePicker();
  const res = await loadPuzzle({ path });
  if (res.ok && res.state) {
    currentState = res.state;
    resetUiState();
    refreshBoard();
    startTimer();
  } else {
    openErrorModal({
      customTitle: "Load failed",
      customBody: res.error || "Could not load the selected puzzle."
    });
  }
}

async function handleRestart() {
  closeVictoryModal();
  closeErrorModal();
  const res = await restartPuzzle();
  if (res.ok && res.state) {
    currentState = res.state;
    resetUiState();
    refreshBoard();
    startTimer();
  }
}

async function handleNextPuzzle() {
  if (!puzzleCatalog || puzzleCatalog.length === 0) {
    closeVictoryModal();
    return;
  }
  const curIdx = currentState
    ? puzzleCatalog.findIndex((p) => p.id === currentState.puzzle_id)
    : -1;
  const next = puzzleCatalog[(curIdx + 1) % puzzleCatalog.length];
  await loadSelectedPuzzle(next.path || next.id);
}

async function init() {
  const [listRes, stateRes] = await Promise.all([fetchPuzzles(), fetchState()]);

  if (stateRes.ok && stateRes.state) {
    currentState = stateRes.state;
  }

  if (listRes.ok && Array.isArray(listRes.puzzles)) {
    puzzleCatalog = listRes.puzzles;
  }

  if (currentState) {
    refreshBoard();
    startTimer();
  }

  // Puzzle Picker modal controls
  document.getElementById("btn-puzzle-picker").addEventListener("click", (e) => {
    e.stopPropagation();
    openPuzzlePicker();
  });
  document.getElementById("btn-picker-close").addEventListener("click", closePuzzlePicker);
  document.getElementById("btn-picker-cancel").addEventListener("click", closePuzzlePicker);
  document.getElementById("puzzle-picker-modal").addEventListener("click", (e) => {
    if (e.target.id === "puzzle-picker-modal") closePuzzlePicker();
  });

  // Upload custom puzzle JSON (triggered from inside the Puzzle Picker modal)
  document.getElementById("file-upload").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (ev) => {
      try {
        const puzzleJson = JSON.parse(ev.target.result);
        closeVictoryModal();
        closeErrorModal();
        closePuzzlePicker();
        const res = await loadPuzzle({ puzzle: puzzleJson });
        if (res.ok && res.state) {
          currentState = res.state;
          resetUiState();
          refreshBoard();
          startTimer();
        } else {
          openErrorModal({
            customTitle: "Invalid puzzle",
            customBody: res.error || "Uploaded JSON does not match the puzzle schema."
          });
        }
      } catch {
        openErrorModal({
          customTitle: "Invalid JSON file",
          customBody: "Could not parse the selected file as valid JSON."
        });
      }
      e.target.value = "";
    };
    reader.readAsText(file);
  });

  // Pause & Resume controls
  document.getElementById("btn-pause").addEventListener("click", (e) => {
    e.stopPropagation();
    if (isPaused) resumeGame();
    else pauseGame();
  });
  document.getElementById("btn-resume").addEventListener("click", resumeGame);

  // Bottom bar buttons
  document.getElementById("btn-restart").addEventListener("click", handleRestart);

  document.getElementById("btn-mark").addEventListener("click", (e) => {
    uiState.markMode = !uiState.markMode;
    const btn = e.currentTarget;
    btn.classList.toggle("active-toggle", uiState.markMode);
    document.getElementById("mark-label").textContent = uiState.markMode ? "Mark: ON" : "Mark";
    document.getElementById("mark-legend").classList.toggle("hidden", !uiState.markMode);
    uiState.newlyRevealed = new Set();
    refreshBoard();
  });

  document.getElementById("btn-clear-marks").addEventListener("click", () => {
    uiState.marks = {};
    uiState.newlyRevealed = new Set();
    refreshBoard();
  });

  // Verdict modal events
  document.getElementById("btn-cancel-modal").addEventListener("click", closeVerdictModal);
  document.getElementById("verdict-modal").addEventListener("click", (e) => {
    if (e.target.id === "verdict-modal") closeVerdictModal();
  });
  document.getElementById("btn-innocent").addEventListener("click", () => handleVerdict("INNOCENT"));
  document.getElementById("btn-criminal").addEventListener("click", () => handleVerdict("CRIMINAL"));

  // Error modal events (single "Keep looking" button)
  document.getElementById("btn-keep-looking").addEventListener("click", closeErrorModal);
  document.getElementById("error-modal").addEventListener("click", (e) => {
    if (e.target.id === "error-modal") closeErrorModal();
  });

  // Victory modal events
  document.getElementById("btn-victory-next").addEventListener("click", handleNextPuzzle);
  document.getElementById("btn-victory-replay").addEventListener("click", handleRestart);
  document.getElementById("btn-victory-close").addEventListener("click", closeVictoryModal);
  document.getElementById("victory-modal").addEventListener("click", (e) => {
    if (e.target.id === "victory-modal") closeVictoryModal();
  });

  // Click empty board background to clear clue highlight
  document.body.addEventListener("click", () => {
    if (!isPaused) clearHighlight();
  });

  // Keyboard shortcuts: Escape closes modals / resumes pause; P toggles pause
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!document.getElementById("error-modal").classList.contains("hidden")) {
        closeErrorModal();
      } else if (!document.getElementById("puzzle-picker-modal").classList.contains("hidden")) {
        closePuzzlePicker();
      } else if (!document.getElementById("verdict-modal").classList.contains("hidden")) {
        closeVerdictModal();
      } else if (isPaused) {
        resumeGame();
      } else if (!document.getElementById("victory-modal").classList.contains("hidden")) {
        closeVictoryModal();
      } else {
        clearHighlight();
      }
    } else if ((e.key === "p" || e.key === "P") && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const anyModalOpen =
        !document.getElementById("verdict-modal").classList.contains("hidden") ||
        !document.getElementById("error-modal").classList.contains("hidden") ||
        !document.getElementById("puzzle-picker-modal").classList.contains("hidden") ||
        !document.getElementById("victory-modal").classList.contains("hidden");
      if (!anyModalOpen) {
        if (isPaused) resumeGame();
        else pauseGame();
      }
    }
  });
}

window.addEventListener("DOMContentLoaded", init);
