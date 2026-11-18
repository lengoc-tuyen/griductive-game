// Board, 3D Flip Card, Multi-Color Split Borders, Clickable Clue Tokens, and Long-Press Strikethrough

const MARK_COLORS = ["transparent", "#F97066", "#32D583", "#FDB022", "#70B8FF"];
const CLUE_PALETTE = ["#2580C3", "#C28416", "#9B36B5", "#2B2BB8", "#D6336C", "#0D9488"];
const LONG_PRESS_MS = 400;

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function hexToRgba(hex, alpha) {
  if (!hex || !hex.startsWith("#") || hex.length !== 7) {
    return `rgba(37, 128, 195, ${alpha})`;
  }
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function buildMultiBorderCSS(colors) {
  if (!colors || colors.length === 0) return "";
  if (colors.length === 1) {
    return `linear-gradient(${colors[0]}, ${colors[0]})`;
  }
  if (colors.length === 2) {
    return `linear-gradient(to right, ${colors[0]} 50%, ${colors[1]} 50%)`;
  }
  const step = 100 / colors.length;
  const stops = colors.map((c, idx) => {
    const start = (idx * step).toFixed(2);
    const end = ((idx + 1) * step).toFixed(2);
    return `${c} ${start}% ${end}%`;
  });
  return `conic-gradient(from -45deg, ${stops.join(", ")})`;
}

/**
 * Compute per-cell border colors, name tint colors, and per-clue accent colors
 * from ``uiState.activeClueCells`` and ``uiState.focusedGroupIndex``.
 */
function computeHighlightMap(state, uiState) {
  const activeOwners = (uiState.activeClueCells || []).filter((cell) =>
    state.cards.some((c) => c.cell === cell && c.is_revealed)
  );
  const hasActive = activeOwners.length > 0;
  const isMultiMode = activeOwners.length >= 2;
  const focusedGroupIdx =
    !isMultiMode && uiState.focusedGroupIndex !== null && uiState.focusedGroupIndex !== undefined
      ? uiState.focusedGroupIndex
      : null;

  const cellColors = new Map();     // cell -> string[]
  const cellNameColor = new Map();  // cell -> string
  const clueAccentColor = new Map(); // ownerCell -> string

  function addCellColor(cell, color, tintName) {
    if (!cell || !color) return;
    if (!cellColors.has(cell)) cellColors.set(cell, []);
    const arr = cellColors.get(cell);
    if (!arr.includes(color)) arr.push(color);
    if (tintName && !cellNameColor.has(cell)) {
      cellNameColor.set(cell, color);
    }
  }

  const cardByCell = new Map(state.cards.map((c) => [c.cell, c]));

  if (activeOwners.length === 1) {
    const owner = activeOwners[0];
    const card = cardByCell.get(owner);
    const primary = (card && card.clue_color) || CLUE_PALETTE[0];
    clueAccentColor.set(owner, primary);

    const allGroups = card && Array.isArray(card.highlight_groups) && card.highlight_groups.length > 0
      ? card.highlight_groups
      : card && card.highlight_cells && card.highlight_cells.length > 0
        ? [{ color: primary, cells: card.highlight_cells, tint_name: false }]
        : [];

    // If the player clicked a specific colored keyword/name token, isolate ONLY that group!
    const groupsToShow =
      focusedGroupIdx !== null && focusedGroupIdx >= 0 && focusedGroupIdx < allGroups.length
        ? [allGroups[focusedGroupIdx]]
        : allGroups;

    groupsToShow.forEach((g) => {
      (g.cells || []).forEach((targetCell) => {
        addCellColor(targetCell, g.color || primary, Boolean(g.tint_name));
      });
    });
  } else if (isMultiMode) {
    activeOwners.forEach((owner, idx) => {
      const card = cardByCell.get(owner);
      const assignedColor = CLUE_PALETTE[idx % CLUE_PALETTE.length];
      clueAccentColor.set(owner, assignedColor);

      const targets = new Set(card ? card.highlight_cells || [] : []);
      if (card && Array.isArray(card.highlight_groups)) {
        card.highlight_groups.forEach((g) => {
          (g.cells || []).forEach((tc) => targets.add(tc));
        });
      }
      targets.forEach((tc) => addCellColor(tc, assignedColor, false));
      addCellColor(owner, assignedColor, false);
    });
  }

  return {
    hasActive,
    isMultiMode,
    focusedGroupIdx,
    activeSet: new Set(activeOwners),
    cellColors,
    cellNameColor,
    clueAccentColor
  };
}

function renderClueInnerHtml(card, isActiveSource, isMultiMode, focusedGroupIdx) {
  if (!card.clue_text) return "(No clue)";

  // In single-clue focus mode, every colored keyword/name is a clickable token!
  if (isActiveSource && !isMultiMode && Array.isArray(card.clue_segments) && card.clue_segments.length > 0) {
    return card.clue_segments
      .map((seg) => {
        const safe = escapeHtml(seg.text);
        if (seg.color && seg.group !== null && seg.group !== undefined) {
          const isFocused = focusedGroupIdx === seg.group;
          const isDimmed = focusedGroupIdx !== null && focusedGroupIdx !== seg.group;
          const cls = [
            "clue-token",
            isFocused ? "is-focused" : "",
            isDimmed ? "is-dimmed-token" : ""
          ].filter(Boolean).join(" ");
          const style =
            `color:${seg.color};` +
            `--tok-color:${seg.color};` +
            `--tok-tint:${hexToRgba(seg.color, 0.14)};` +
            `--tok-hover-tint:${hexToRgba(seg.color, 0.12)};`;
          return `<span class="${cls}" data-group-idx="${seg.group}" style="${style}" title="Click to focus only ${safe}">${safe}</span>`;
        }
        if (seg.color) {
          return `<span style="color:${seg.color};font-weight:700">${safe}</span>`;
        }
        return safe;
      })
      .join("");
  }
  return escapeHtml(card.clue_text);
}

function attachLongPress(el, onLongPress) {
  let timer = null;
  let startX = 0;
  let startY = 0;

  function cancel() {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
    el.classList.remove("is-holding");
  }

  el.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    startX = e.clientX;
    startY = e.clientY;
    el.classList.add("is-holding");
    timer = setTimeout(() => {
      timer = null;
      el.classList.remove("is-holding");
      el.dataset.longPressed = "1";
      onLongPress();
    }, LONG_PRESS_MS);
  });

  el.addEventListener("pointermove", (e) => {
    if (timer === null) return;
    if (Math.hypot(e.clientX - startX, e.clientY - startY) > 8) {
      cancel();
    }
  });

  el.addEventListener("pointerup", cancel);
  el.addEventListener("pointerleave", cancel);
  el.addEventListener("pointercancel", cancel);
}

function renderHeaders(size) {
  const wrapper = document.getElementById("board-wrapper");
  wrapper.className = `board-wrapper size-${size}`;

  const colHeaders = document.getElementById("col-headers");
  colHeaders.style.gridTemplateColumns = `repeat(${size}, 1fr)`;
  colHeaders.innerHTML = "";
  for (let c = 0; c < size; c++) {
    const lbl = document.createElement("div");
    lbl.className = "col-header-label";
    lbl.textContent = String.fromCharCode(65 + c);
    colHeaders.appendChild(lbl);
  }

  const rowHeaders = document.getElementById("row-headers");
  rowHeaders.style.gridTemplateRows = `repeat(${size}, 1fr)`;
  rowHeaders.innerHTML = "";
  for (let r = 1; r <= size; r++) {
    const lbl = document.createElement("div");
    lbl.className = "row-header-label";
    lbl.textContent = String(r);
    rowHeaders.appendChild(lbl);
  }
}

function renderRevealedCluesSidebar(state, uiState, hlMap, callbacks) {
  const listEl = document.getElementById("revealed-clues-list");
  const countEl = document.getElementById("clues-count");
  if (!listEl || !countEl) return;

  const revealed = state.cards.filter((c) => c.is_revealed && c.clue_text);
  countEl.textContent = String(revealed.length);
  listEl.innerHTML = "";

  if (revealed.length === 0) {
    listEl.innerHTML = `<div style="font-size:0.8rem;color:#676158;">No clues revealed yet.</div>`;
    return;
  }

  const crossedSet = uiState.crossedClues || new Set();

  revealed.forEach((card) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "clue-list-item";
    const isActive = hlMap.activeSet.has(card.cell);
    const isCrossed = crossedSet.has(card.cell);
    const itemColor = hlMap.clueAccentColor.get(card.cell) || card.clue_color || CLUE_PALETTE[0];

    if (isActive) {
      btn.classList.add("active");
      btn.style.setProperty("--clue-item-color", itemColor);
      btn.style.setProperty("--clue-item-tint", hexToRgba(itemColor, 0.1));
    } else if (hlMap.hasActive) {
      btn.classList.add("dimmed");
    }

    if (isCrossed) {
      btn.classList.add("clue-crossed");
    }

    const dotHtml = isActive
      ? `<span class="clue-color-dot" style="background:${itemColor}"></span>`
      : "";

    btn.innerHTML = `
      ${dotHtml}<span class="clue-list-coord ${card.status}">${escapeHtml(card.cell)}</span>
      <span class="clue-list-text"><strong>${escapeHtml(card.name)}:</strong> ${escapeHtml(card.clue_text)}</span>
    `;

    attachLongPress(btn, () => callbacks.onClueLongPress(card));

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (btn.dataset.longPressed === "1") {
        delete btn.dataset.longPressed;
        return;
      }
      callbacks.onClueSelect(card, e.shiftKey);
    });

    listEl.appendChild(btn);
  });
}

function renderBoard(state, uiState, callbacks) {
  renderHeaders(state.size);

  const boardEl = document.getElementById("board");
  boardEl.style.gridTemplateColumns = `repeat(${state.size}, 1fr)`;
  boardEl.innerHTML = "";

  const hlMap = computeHighlightMap(state, uiState);
  const newlyRevealed = uiState.newlyRevealed || new Set();
  const crossedSet = uiState.crossedClues || new Set();

  state.cards.forEach((card) => {
    const scene = document.createElement("div");
    scene.className = "card-scene";

    const shouldAnimateFlip = card.is_revealed && newlyRevealed.has(card.cell);
    if (card.is_revealed && !shouldAnimateFlip) {
      scene.classList.add("is-flipped");
    }

    const isSource = hlMap.activeSet.has(card.cell);
    const borderColors = hlMap.cellColors.get(card.cell) || [];
    const hasBorder = borderColors.length > 0;
    const isVisibleInFocus = isSource || hasBorder;

    if (isSource) {
      scene.classList.add("is-active-source");
    }

    if (hlMap.hasActive) {
      if (hasBorder) {
        scene.classList.add("has-color-border");
        scene.style.setProperty("--multi-border-bg", buildMultiBorderCSS(borderColors));
      }
      if (!isVisibleInFocus) {
        scene.classList.add("dimmed");
      }
    }

    const markIdx = uiState.marks[card.cell] || 0;
    const markColor = MARK_COLORS[markIdx];
    const hasMark = markIdx > 0;
    const statusClass = card.status || "";
    const statusLabel = card.status === "INNOCENT" ? "INNOCENT" : card.status === "CRIMINAL" ? "CRIMINAL" : "";
    const nameColor = hlMap.cellNameColor.get(card.cell) || "";
    const nameStyle = nameColor ? `style="color:${nameColor}"` : "";

    const isCrossed = crossedSet.has(card.cell);
    const clueBodyClasses = [
      "back-clue-body",
      isCrossed ? "clue-crossed" : ""
    ].filter(Boolean).join(" ");

    const avatarLarge = typeof createAvatarSVG === "function"
      ? createAvatarSVG(card.name, "avatar-card")
      : "";
    const avatarMini = typeof createAvatarSVG === "function"
      ? createAvatarSVG(card.name, "avatar-mini")
      : "";

    const clueHtml = renderClueInnerHtml(card, isSource, hlMap.isMultiMode, hlMap.focusedGroupIdx);

    scene.innerHTML = `
      <div class="card-inner">
        <!-- Face-Down Front -->
        <div class="card-face card-front">
          <div class="card-top-row">
            <span class="coord-tag">${escapeHtml(card.cell)}</span>
            <span class="mark-dot ${hasMark ? "has-mark" : uiState.markMode ? "mark-mode-hint" : ""}"
                  style="background:${markColor}"></span>
          </div>
          <div class="front-center">
            ${avatarLarge}
            <div class="suspect-name" ${nameStyle}>${escapeHtml(card.name)}</div>
            <div class="suspect-prof">${escapeHtml(card.profession)}</div>
          </div>
        </div>

        <!-- Face-Up Back (Knotwise layout) -->
        <div class="card-face card-back ${statusClass}">
          <span class="coord-tag back-coord-corner">${escapeHtml(card.cell)}</span>
          ${isSource ? `<span class="magnifier-badge back-magnifier-corner" title="Inspecting this clue">🔍</span>` : ""}
          <div class="back-header-centered">
            ${avatarMini}
            <div class="back-identity">
              <div class="back-name" ${nameStyle}>${escapeHtml(card.name)}</div>
              <div class="back-prof">${escapeHtml(card.profession)}</div>
            </div>
          </div>
          <div class="${clueBodyClasses}" title="Click a colored keyword to filter · Hold to cross off">
            <span>${clueHtml}</span>
          </div>
        </div>
      </div>
    `;

    // Attach long-press on the clue body of revealed cards to toggle strikethrough
    const clueBodyEl = scene.querySelector(".back-clue-body");
    if (card.is_revealed && clueBodyEl && card.clue_text) {
      attachLongPress(clueBodyEl, () => {
        scene.dataset.longPressed = "1";
        callbacks.onClueLongPress(card);
      });

      // Attach click handlers on individual colored keywords/names inside the active clue
      clueBodyEl.querySelectorAll(".clue-token").forEach((tokEl) => {
        tokEl.addEventListener("click", (e) => {
          e.stopPropagation();
          if (scene.dataset.longPressed === "1") {
            delete scene.dataset.longPressed;
            return;
          }
          const grpIdx = parseInt(tokEl.dataset.groupIdx, 10);
          if (!Number.isNaN(grpIdx)) {
            callbacks.onTokenClick(card, grpIdx);
          }
        });
      });
    }

    scene.addEventListener("click", (e) => {
      e.stopPropagation();
      if (scene.dataset.longPressed === "1") {
        delete scene.dataset.longPressed;
        return;
      }
      callbacks.onCardClick(card, e.shiftKey);
    });

    boardEl.appendChild(scene);

    if (shouldAnimateFlip) {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          scene.classList.add("is-flipped");
        });
      });
    }
  });

  // Update progress bar and sidebar meta
  const pct = state.total_cells > 0 ? Math.round((state.proved_count / state.total_cells) * 100) : 0;
  document.getElementById("progress-text").textContent = `${state.proved_count} / ${state.total_cells}`;
  const fillEl = document.getElementById("progress-fill");
  if (fillEl) fillEl.style.width = `${pct}%`;

  const sizeEl = document.getElementById("meta-size");
  if (sizeEl) sizeEl.textContent = `${state.size} × ${state.size}`;

  renderRevealedCluesSidebar(state, uiState, hlMap, callbacks);
}
