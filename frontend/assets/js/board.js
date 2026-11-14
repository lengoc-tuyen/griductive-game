const MARK_COLORS = ["transparent", "#EF4444", "#22C55E", "#F59E0B", "#3B82F6"];

function renderBoard(state, uiState, callbacks) {
  const boardEl = document.getElementById("board");
  boardEl.style.gridTemplateColumns = `repeat(${state.size}, 1fr)`;
  boardEl.innerHTML = "";

  const hasActiveHighlight = uiState.activeHighlightSource !== null;
  const highlightSet = new Set(uiState.highlightedCells || []);

  state.cards.forEach((card) => {
    const cardEl = document.createElement("div");
    cardEl.className = "card";

    if (card.is_revealed) {
      cardEl.classList.add(card.status === "INNOCENT" ? "innocent" : "criminal");
    }

    if (hasActiveHighlight) {
      if (highlightSet.has(card.cell) || card.cell === uiState.activeHighlightSource) {
        cardEl.classList.add("highlighted");
      } else {
        cardEl.classList.add("dimmed");
      }
    }

    const markIdx = uiState.marks[card.cell] || 0;
    const markColor = MARK_COLORS[markIdx];
    const magnifier = uiState.activeHighlightSource === card.cell ? " 🔍" : "";

    cardEl.innerHTML = `
      <div class="card-top">
        <span>${card.cell}${magnifier}</span>
        ${!card.is_revealed ? `<span class="mark-dot" style="background:${markColor}"></span>` : `<span>${card.status}</span>`}
      </div>
      <div class="card-body">
        <div class="card-name">${card.name}</div>
        <div class="mono">${card.profession}</div>
        ${card.is_revealed && card.clue_text ? `<div class="clue-text">${card.clue_text}</div>` : ""}
      </div>
    `;

    cardEl.addEventListener("click", () => callbacks.onCardClick(card));
    boardEl.appendChild(cardEl);
  });

  document.getElementById("progress-text").textContent = `${state.proved_count} / ${state.total_cells}`;
}