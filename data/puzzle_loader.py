"""[E] Load / save puzzle JSON -> Puzzle object (validated against schema)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from algorithms.logic.clues import validate as validate_clue
from algorithms.logic.models import Board, Character, Clue, Status


class PuzzleValidationError(ValueError):
    """Raised when puzzle content violates format or semantic rules."""
    pass


@dataclass(frozen=True)
class Puzzle:
    id: str
    size: int
    characters: tuple[Character, ...]
    solution: dict[str, Status]
    initially_revealed: tuple[str, ...]
    clues: tuple[Clue, ...]
    difficulty: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    _board: Board = field(init=False, repr=False, compare=False)
    _clue_of: dict[str, Clue] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        board = Board(self.size, self.characters)
        object.__setattr__(self, "_board", board)
        clue_map = {c.owner: c for c in self.clues}
        object.__setattr__(self, "_clue_of", clue_map)

    @property
    def board(self) -> Board:
        return self._board

    def clue_at(self, cell: str) -> Optional[Clue]:
        return self._clue_of.get(cell)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Puzzle":
        size = d.get("size")
        if not isinstance(size, int) or not (1 <= size <= 26):
            raise PuzzleValidationError(f"Invalid puzzle size: {size!r}")

        characters_raw = d.get("characters", [])
        characters = tuple(Character.from_dict(c) for c in characters_raw)

        raw_solution = d.get("solution", {})
        solution = {c: Status(s) for c, s in raw_solution.items()}

        raw_init = d.get("initially_revealed", [])
        initially_revealed = tuple(raw_init)

        raw_clues = d.get("clues", [])
        clues = tuple(Clue.from_dict(c) for c in raw_clues)

        puzzle = cls(
            id=str(d.get("id", "unnamed_puzzle")),
            size=size,
            characters=characters,
            solution=solution,
            initially_revealed=initially_revealed,
            clues=clues,
            difficulty=d.get("difficulty"),
            metadata=dict(d.get("metadata", {})) if d.get("metadata") else None,
        )
        validate_puzzle(puzzle)
        return puzzle

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "size": self.size,
            "characters": [c.to_dict() for c in self.characters],
            "solution": {cell: st.value for cell, st in self.solution.items()},
            "initially_revealed": list(self.initially_revealed),
            "clues": [c.to_dict() for c in self.clues],
        }
        if self.difficulty is not None:
            data["difficulty"] = self.difficulty
        if self.metadata is not None:
            data["metadata"] = self.metadata
        return data


def validate_puzzle(puzzle: Puzzle) -> None:
    board = puzzle.board
    all_cells = set(board.cells())

    if len(puzzle.solution) != len(all_cells) or set(puzzle.solution.keys()) != all_cells:
        raise PuzzleValidationError(
            f"Solution does not cover all cells (expected {len(all_cells)}, got {len(puzzle.solution)})"
        )

    for cell in puzzle.initially_revealed:
        if cell not in all_cells:
            raise PuzzleValidationError(f"Initially revealed cell {cell!r} is not on the board")

    seen_owners = set()
    for clue in puzzle.clues:
        if clue.owner not in all_cells:
            raise PuzzleValidationError(f"Clue owner {clue.owner!r} is not on board")
        if clue.owner in seen_owners:
            raise PuzzleValidationError(f"Multiple clues for cell {clue.owner!r}")
        seen_owners.add(clue.owner)
        validate_clue(clue, board)


def load_puzzle(path: Path | str) -> Puzzle:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Puzzle.from_dict(data)


def save_puzzle(puzzle: Puzzle, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(puzzle.to_dict(), f, indent=2, ensure_ascii=False)
