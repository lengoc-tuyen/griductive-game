# [E] Puzzle JSON Format Specification

This document defines the schema for puzzle files in `data/puzzles/` used by the Game Engine, the Deduction Agent, the GUI, and the verification pipeline.

## 1. Top-Level Structure

A puzzle JSON document contains:

```json
{
  "id": "puzzle_3x3_01",
  "size": 3,
  "characters": [
    {"name": "Alice", "profession": "Detective", "cell": "A1"},
    {"name": "Bob",   "profession": "Doctor",    "cell": "B1"},
    {"name": "Clara", "profession": "Engineer",  "cell": "C1"}
  ],
  "solution": {
    "A1": "INNOCENT",
    "B1": "CRIMINAL",
    "C1": "INNOCENT"
  },
  "initially_revealed": ["B2"],
  "clues": [
    {
      "id": "clue_B2",
      "owner": "B2",
      "type": "EXACTLY",
      "params": {
        "region": {"kind": "row", "row": 1},
        "k": 1
      }
    }
  ],
  "difficulty": "EASY",
  "metadata": {
    "criminal_ratio": 0.33,
    "difficulty_score": 12.5,
    "steps_to_solve": 8,
    "dpll_decisions": 10
  }
}
```

### Fields

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Unique identifier of the puzzle (e.g. `puzzle_3x3_01`). |
| `size` | `integer` | Board dimension $N \in \{3, 4, 5\}$ (board is $N \times N$). |
| `characters` | `list[object]` | Exactly $N^2$ characters. Ordered alphabetically by `name`. |
| `solution` | `dict[string, string]` | Mapping each cell (e.g. `"A1"`) to `"CRIMINAL"` or `"INNOCENT"`. |
| `initially_revealed` | `list[string]` | Cell coordinates that are face-up at game start (statuses and clues public). |
| `clues` | `list[object]` | List of clue objects. Typically 1 clue per card, owned by `owner`. |
| `difficulty` | `string` *(optional)* | Difficulty rating: `"EASY"`, `"MEDIUM"`, `"HARD"`. |
| `metadata` | `object` *(optional)* | Generation stats, solver statistics, benchmark information. |

---

## 2. Character Object

```json
{
  "name": "Alice",
  "profession": "Detective",
  "cell": "A1"
}
```

- `name`: Unique character name (alphabetic string).
- `profession`: Optional or descriptive profession string.
- `cell`: Cell coordinate string in row-major order: Column letter (`A`..`Z`) + 1-based Row number (`1`..`N`).

---

## 3. Clue Object & Clue Types

Every clue object has the following format:

```json
{
  "id": "clue_A1",
  "owner": "A1",
  "type": "<CLUE_TYPE>",
  "params": { ... }
}
```

- `id`: Unique string identifier for the clue.
- `owner`: Cell ID of the card on which this clue is printed.
- `type`: One of the 6 core types or extensions.
- `params`: Parameters specific to the clue type.

### Clue Types & Params

| Clue Type | Meaning | Parameters |
|---|---|---|
| `FACT` | A named person is Criminal or Innocent. | `{"person": "Alice", "status": "CRIMINAL"}` |
| `SAME` | Two people have the same status ($C_a \leftrightarrow C_b$). | `{"a": "Alice", "b": "Bob"}` |
| `DIFFERENT` | Two people have different statuses ($C_a \oplus C_b$). | `{"a": "Alice", "b": "Bob"}` |
| `EXACTLY` | Exactly $k$ people in a region are Criminals. | `{"region": <Region>, "k": 2}` |
| `AT_LEAST` | At least $k$ people in a region are Criminals. | `{"region": <Region>, "k": 2}` |
| `AT_MOST` | At most $k$ people in a region are Criminals. | `{"region": <Region>, "k": 2}` |
| `PARITY` *(ext)* | Parity of criminals in a region is ODD or EVEN. | `{"region": <Region>, "parity": "ODD"}` |
| `COMPARE` *(ext)* | Regional count comparison (`MORE`, `FEWER`, `EQUAL`). | `{"region_a": <Region>, "region_b": <Region>, "op": "MORE"}` |

> Counting clues (`EXACTLY`, `AT_LEAST`, `AT_MOST`, `PARITY`, `COMPARE`) count `CRIMINAL` by default. They can count `INNOCENT` instead by adding `"counts": "INNOCENT"` inside `params`.

---

## 4. Region Specification

- **Row**: `{"kind": "row", "row": 2}` (1-based row index)
- **Column**: `{"kind": "col", "col": "B"}`
- **Neighbors**: `{"kind": "neighbors", "of": "C2"}` (8 adjacent cells, excluding center)
- **Explicit Cells**: `{"kind": "cells", "cells": ["A1", "B2", "C3"]}`
- **Corners** *(ext)*: `{"kind": "corners"}` (the 4 corner cells)
- **Edges** *(ext)*: `{"kind": "edges"}` (all boundary cells)
- **Between** *(ext)*: `{"kind": "between", "a": "Alice", "b": "Bob"}` (cells strictly between two collinear characters)
- **Common Neighbors** *(ext)*: `{"kind": "common_neighbors", "a": "Alice", "b": "Bob"}`

---

## 5. Validity Criteria

A puzzle JSON is valid iff:
1. **Schema Integrity**: All fields match the specifications above without duplicate names or cells.
2. **Semantic Truth**: Every clue evaluates to `True` under `solution`.
3. **Unique Solution**: The full set of clues entails exactly one assignment of statuses across the entire grid.
4. **No-Guess Solvable**: Running `DeductionAgent` from `initially_revealed` solves all cells without guessing (`AgentOutcome.SOLVED`).
