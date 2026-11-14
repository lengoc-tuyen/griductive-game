// API client matching D1 JSON Contract (with full 3x3 solvable offline mock)

const MOCK_PUZZLE_STATE = {
  puzzle_id: "test_3x3_basic (Offline Mock)",
  size: 3,
  is_solved: false,
  proved_count: 1,
  total_cells: 9,
  cards: [
    { cell: "A1", row: 1, col: "A", name: "Alice", profession: "Cook", is_revealed: false, status: null, clue_id: null, clue_text: null, highlight_cells: [] },
    { cell: "B1", row: 1, col: "B", name: "Bob", profession: "Guard", is_revealed: false, status: null, clue_id: null, clue_text: null, highlight_cells: [] },
    { cell: "C1", row: 1, col: "C", name: "Clara", profession: "Nurse", is_revealed: false, status: null, clue_id: null, clue_text: null, highlight_cells: [] },
    { cell: "A2", row: 2, col: "A", name: "David", profession: "Baker", is_revealed: false, status: null, clue_id: null, clue_text: null, highlight_cells: [] },
    { cell: "B2", row: 2, col: "B", name: "Eve", profession: "Clerk", is_revealed: true, status: "INNOCENT", clue_id: "clue_B2", clue_text: "There are no criminals in {A1, A2}.", highlight_cells: ["A1", "A2"] },
    { cell: "C2", row: 2, col: "C", name: "Frank", profession: "Smith", is_revealed: false, status: null, clue_id: null, clue_text: null, highlight_cells: [] },
    { cell: "A3", row: 3, col: "A", name: "Grace", profession: "Tailor", is_revealed: false, status: null, clue_id: null, clue_text: null, highlight_cells: [] },
    { cell: "B3", row: 3, col: "B", name: "Henry", profession: "Miner", is_revealed: false, status: null, clue_id: null, clue_text: null, highlight_cells: [] },
    { cell: "C3", row: 3, col: "C", name: "Ivy", profession: "Artist", is_revealed: false, status: null, clue_id: null, clue_text: null, highlight_cells: [] }
  ]
};

const MOCK_SOLUTIONS = {
  A1: { status: "INNOCENT", clue: "Bob is a criminal.", highlight: ["B1"], req: () => true },
  A2: { status: "INNOCENT", clue: "Exactly 1 criminal in row 1.", highlight: ["A1", "B1", "C1"], req: () => true },
  B1: { status: "CRIMINAL", clue: "Frank and Ivy have the same status.", highlight: ["C2", "C3"], req: (rev) => rev.has("A1") },
  C1: { status: "INNOCENT", clue: "Exactly 2 criminals in column C.", highlight: ["C1", "C2", "C3"], req: (rev) => rev.has("A2") && rev.has("B1") },
  C2: { status: "CRIMINAL", clue: "There are no criminals in {A3, B3}.", highlight: ["A3", "B3"], req: (rev) => rev.has("C1") },
  C3: { status: "CRIMINAL", clue: "Grace is innocent.", highlight: ["A3"], req: (rev) => rev.has("C1") },
  A3: { status: "INNOCENT", clue: "Henry is innocent.", highlight: ["B3"], req: (rev) => rev.has("C2") || rev.has("C3") },
  B3: { status: "INNOCENT", clue: "There are 3 criminals in total.", highlight: ["B1", "C2", "C3"], req: (rev) => rev.has("C2") || rev.has("A3") }
};

let offlineState = JSON.parse(JSON.stringify(MOCK_PUZZLE_STATE));

async function fetchPuzzles() {
  try {
    const res = await fetch("/api/puzzles");
    if (!res.ok) throw new Error("Backend unavailable");
    return await res.json();
  } catch {
    return {
      ok: true,
      puzzles: [{ id: "test_3x3_basic", name: "test_3x3_basic (3x3 - Mock)", size: 3, path: "" }]
    };
  }
}

async function fetchState() {
  try {
    const res = await fetch("/api/state");
    if (!res.ok) throw new Error("Backend unavailable");
    return await res.json();
  } catch {
    return { ok: true, state: offlineState };
  }
}

async function loadPuzzle(payload) {
  try {
    const res = await fetch("/api/load", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Backend unavailable");
    return await res.json();
  } catch {
    if (payload.puzzle && payload.puzzle.characters) {
      const p = payload.puzzle;
      const initSet = new Set(p.initially_revealed || []);
      const cards = p.characters.map((ch) => {
        const revealed = initSet.has(ch.cell);
        const clue = (p.clues || []).find((c) => c.owner === ch.cell);
        return {
          cell: ch.cell,
          row: parseInt(ch.cell.slice(1), 10),
          col: ch.cell[0],
          name: ch.name,
          profession: ch.profession,
          is_revealed: revealed,
          status: revealed ? p.solution[ch.cell] : null,
          clue_id: revealed && clue ? clue.id : null,
          clue_text: revealed && clue ? (clue.text || JSON.stringify(clue)) : null,
          highlight_cells: revealed && clue ? (clue.cells || []) : []
        };
      });
      offlineState = {
        puzzle_id: p.id || "uploaded_puzzle",
        size: p.size,
        is_solved: false,
        proved_count: cards.filter((c) => c.is_revealed).length,
        total_cells: cards.length,
        cards
      };
    }
    return { ok: true, message: "Loaded puzzle (Offline Mock mode)", state: offlineState };
  }
}

async function restartPuzzle() {
  try {
    const res = await fetch("/api/restart", { method: "POST" });
    if (!res.ok) throw new Error("Backend unavailable");
    return await res.json();
  } catch {
    offlineState = JSON.parse(JSON.stringify(MOCK_PUZZLE_STATE));
    return { ok: true, message: "Puzzle restarted.", state: offlineState };
  }
}

async function submitVerdict(cell, status) {
  try {
    const res = await fetch("/api/verdict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cell, status })
    });
    if (!res.ok) throw new Error("Backend unavailable");
    return await res.json();
  } catch {
    const revealedSet = new Set(
      offlineState.cards.filter((c) => c.is_revealed).map((c) => c.cell)
    );
    const rule = MOCK_SOLUTIONS[cell];

    if (!rule || !rule.req(revealedSet)) {
      return {
        ok: true,
        result: "NOT_PROVABLE",
        cell,
        status,
        message: "NOT PROVABLE: Neither status is logically forced by current clues. Do not guess!",
        state: offlineState
      };
    }

    if (status !== rule.status) {
      return {
        ok: true,
        result: "CONTRADICTED",
        cell,
        status,
        message: "CONTRADICTED: The opposite status is logically forced!",
        state: offlineState
      };
    }

    const card = offlineState.cards.find((c) => c.cell === cell);
    card.is_revealed = true;
    card.status = rule.status;
    card.clue_text = rule.clue;
    card.highlight_cells = rule.highlight;

    offlineState.proved_count = offlineState.cards.filter((c) => c.is_revealed).length;
    offlineState.is_solved = offlineState.proved_count === offlineState.total_cells;

    return {
      ok: true,
      result: "ACCEPTED",
      cell,
      status,
      message: `${cell} confirmed ${status}!`,
      state: offlineState
    };
  }
}