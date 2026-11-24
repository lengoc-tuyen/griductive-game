const MARK_COLORS = ["transparent", "#EF4444", "#22C55E", "#F59E0B", "#3B82F6"];

let renderedPuzzleSignature = null;

function buildCardSlot(card, callbacks) {
  const slot = document.createElement("div");
  slot.className = "card-slot";
  slot.dataset.cell = card.cell;

  const frontAvatar = window.createAvatarSVG
    ? window.createAvatarSVG(card.name, card.profession, 58)
    : "";
  const backAvatar = window.createAvatarSVG
    ? window.createAvatarSVG(card.name, card.profession, 30)
    : "";

  slot.innerHTML = `
    <div class="card-inner">
      <div class="card-face card-front">
        <div class="card-top">
          <span class="coord-label">${card.cell}</span>
          <span class="mark-dot" title="Click or right-click to cycle note color"></span>
        </div>
        <div class="card-front-body">
          <div class="avatar-wrap">${frontAvatar}</div>
          <div class="card-name">${card.name}</div>
          <div class="mono">${card.profession}</div>
        </div>
      </div>
      <div class="card-face card-back">
        <div class="card-top">
          <span class="coord-label back-coord">${card.cell}</span>
          <span class="status-pill"></span>
        </div>
        <div class="card-back-identity">
          <div class="avatar-wrap">${backAvatar}</div>
          <div class="card-back-meta">
            <div class="card-back-name">${card.name}</div>
            <div class="mono card-back-prof">${card.profession}</div>
          </div>
        </div>
        <div class="clue-text"></div>
      </div>
    </div>
  `;

  // Direct click on corner mark dot cycles draft color without opening modal
  const markDot = slot.querySelector(".mark-dot");
  markDot.addEventListener("click", (e) => {
    e.stopPropagation();
    callbacks.onCycleMark(card.cell);
  });

  // Right-click on unrevealed card cycles draft color
  slot.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    callbacks.onCycleMark(card.cell);
  });

  // Main card click
  slot.addEventListener("click", () => {
    callbacks.onCardClick(card.cell);
  });

  return slot;
}

function renderBoard(state, uiState, callbacks) {
  const boardEl = document.getElementById("board");
  boardEl.style.gridTemplateColumns = `repeat(${state.size}, 1fr)`;
  boardEl.dataset.size = String(state.size);

  const signature = `${state.puzzle_id}::${state.size}::${state.cards.map((c) => c.cell).join(",")}`;
  if (renderedPuzzleSignature !== signature) {
    boardEl.innerHTML = "";
    state.cards.forEach((card) => {
      boardEl.appendChild(buildCardSlot(card, callbacks));
    });
    renderedPuzzleSignature = signature;
  }

  const hasActiveHighlight = uiState.activeHighlightSource !== null;
  const highlightSet = new Set(uiState.highlightedCells || []);

  state.cards.forEach((card) => {
    const slot = boardEl.querySelector(`.card-slot[data-cell="${card.cell}"]`);
    if (!slot) return;

    // Reveal / 3D Flip state
    slot.classList.toggle("flipped", Boolean(card.is_revealed));
    slot.classList.toggle("innocent", card.is_revealed && card.status === "INNOCENT");
    slot.classList.toggle("criminal", card.is_revealed && card.status === "CRIMINAL");

    // Highlight & Dim states
    const isSource = uiState.activeHighlightSource === card.cell;
    const isReferenced = hasActiveHighlight && highlightSet.has(card.cell);
    const isDimmed = hasActiveHighlight && !isSource && !isReferenced;

    slot.classList.toggle("highlight-source", isSource);
    slot.classList.toggle("highlighted", isReferenced);
    slot.classList.toggle("dimmed", isDimmed);

    // Hint target pulse
    slot.classList.toggle("hint-target", uiState.hintCell === card.cell && !card.is_revealed);

    // Draft mark color on front face
    const markIdx = uiState.marks[card.cell] || 0;
    const markDot = slot.querySelector(".mark-dot");
    if (markDot) {
      markDot.style.backgroundColor = MARK_COLORS[markIdx];
    }

    // Back face dynamic text & magnifier icon
    const backCoord = slot.querySelector(".back-coord");
    if (backCoord) {
      backCoord.textContent = isSource ? `${card.cell} 🔍` : card.cell;
    }

    const statusPill = slot.querySelector(".status-pill");
    if (statusPill) {
      statusPill.textContent = card.status || "";
    }

    const clueEl = slot.querySelector(".clue-text");
    if (clueEl) {
      clueEl.textContent = card.clue_text || "No statement.";
    }
  });

  // Update Sidebar progress & puzzle metadata
  const pct = state.total_cells > 0 ? Math.round((state.proved_count / state.total_cells) * 100) : 0;
  document.getElementById("progress-text").textContent = `${state.proved_count} / ${state.total_cells}`;
  const progressFill = document.getElementById("progress-fill");
  if (progressFill) progressFill.style.width = `${pct}%`;

  const puzzleIdLabel = document.getElementById("puzzle-id-label");
  if (puzzleIdLabel) puzzleIdLabel.textContent = state.puzzle_id;

  const sizeBadge = document.getElementById("puzzle-size-badge");
  if (sizeBadge) sizeBadge.innerHTML = `${state.size}&times;${state.size}`;
}

function triggerCardShake(cell) {
  const slot = document.querySelector(`.card-slot[data-cell="${cell}"]`);
  if (!slot) return;
  slot.classList.remove("shake");
  void slot.offsetWidth;
  slot.classList.add("shake");
}