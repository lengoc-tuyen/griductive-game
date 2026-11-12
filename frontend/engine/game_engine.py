"""[D1] GameEngine: owns the complete puzzle, hidden solution, and unrevealed clues.

Responsibilities (strictly scoped to [D] Game Engine):
- Load puzzle JSON and validate clues against the board.
- Keep ``_solution`` and unrevealed ``_clues_by_owner`` private.
- Expose ``public_state()``, ``restart()``, and ``submit(cell, status)`` (conforming to
  ``EngineProtocol`` in ``algorithms/agent/public_state.py``).
- Judge player verdicts via ``algorithms.agent.entailment.check_verdict`` on public state.
- Serialize public board/card state to JSON for the Web GUI.

NOTE for [C] (Agent / Hint / Auto-Solve owner):
- ``GameEngine`` already implements ``EngineProtocol`` (``public_state()`` and ``submit()``).
- To integrate Hint or Auto-Solve later, pass this ``GameEngine`` instance (or
  ``engine.public_state()``) into ``algorithms.agent.hint.hint(...)`` or
  ``algorithms.agent.deduction_agent.DeductionAgent().run(engine)``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional

from algorithms.agent.entailment import check_verdict
from algorithms.agent.public_state import PublicState, VerdictResult
from algorithms.logic.clues import validate as validate_clue
from algorithms.logic.models import Board, Clue, Status, parse_cell
from frontend.engine.verdict import VerdictOutcome
from frontend.gui.clue_renderer import get_highlight_cells, render_clue_text


class GameEngine:
    """Authoritative game state owner.

    Hidden information (``_solution`` and unrevealed ``_clues_by_owner``) is never
    exposed through ``public_state()`` or ``serialize_state()``.
    """

    def __init__(self, puzzle: Mapping[str, Any], source_path: Optional[Path] = None) -> None:
        self.puzzle_id: str = str(puzzle.get("id") or (source_path.stem if source_path else "puzzle"))
        self.source_path: Optional[Path] = source_path
        self.board: Board = Board.from_dict(puzzle)

        raw_solution = puzzle.get("solution")
        if not isinstance(raw_solution, Mapping):
            raise ValueError("puzzle is missing a 'solution' mapping")
        self._solution: dict[str, Status] = {}
        for cell in self.board.cells():
            if cell not in raw_solution:
                raise ValueError(f"solution is missing cell {cell!r}")
            self._solution[cell] = Status(raw_solution[cell])

        self._clues_by_owner: dict[str, Clue] = {}
        for raw_clue in puzzle.get("clues", []):
            clue = Clue.from_dict(raw_clue)
            validate_clue(clue, self.board)
            if clue.owner in self._clues_by_owner:
                raise ValueError(f"multiple clues assigned to owner cell {clue.owner!r}")
            self._clues_by_owner[clue.owner] = clue

        self._initial_cells: list[str] = []
        for ref in puzzle.get("initially_revealed", []):
            cell = self.board.ref_to_cell(str(ref))
            if cell not in self._initial_cells:
                self._initial_cells.append(cell)

        self._proved: dict[str, Status] = {}
        self._revealed_clues: list[Clue] = []
        self.warnings: list[str] = []

        self.restart()

    # ------------------------------------------------------------------ loaders
    @classmethod
    def from_file(cls, path: str | Path) -> "GameEngine":
        file_path = Path(path)
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(data, source_path=file_path)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], source_path: Optional[Path] = None) -> "GameEngine":
        return cls(data, source_path=source_path)

    # --------------------------------------------------------- EngineProtocol
    def restart(self) -> None:
        """Reset the puzzle to its initial public state."""
        self._proved = {cell: self._solution[cell] for cell in self._initial_cells}
        self._revealed_clues = [
            self._clues_by_owner[cell]
            for cell in self._initial_cells
            if cell in self._clues_by_owner
        ]
        self.warnings.clear()

    def public_state(self) -> PublicState:
        """Return an immutable snapshot containing ONLY public knowledge."""
        return PublicState(
            board=self.board,
            revealed_clues=tuple(self._revealed_clues),
            proved=dict(self._proved),
        )

    def submit(self, cell: str, status: Status) -> tuple[VerdictResult, Optional[Clue]]:
        """EngineProtocol method: judge ``(cell, status)`` against public knowledge.

        On ``ACCEPTED``, reveals the card and returns ``(VerdictResult.ACCEPTED, clue)``.
        On ``NOT_PROVABLE`` or ``CONTRADICTED``, leaves state unchanged and returns ``(result, None)``.
        """
        target_status = status if isinstance(status, Status) else Status(str(status).strip().upper())
        state = self.public_state()
        result = check_verdict(state, cell, target_status)
        if result is not VerdictResult.ACCEPTED or cell in self._proved:
            return result, None
        clue = self._reveal_cell(cell, target_status)
        return VerdictResult.ACCEPTED, clue

    # --------------------------------------------------------- internal helpers
    def _reveal_cell(self, cell: str, status: Status) -> Optional[Clue]:
        if self._solution[cell] is not status:
            self.warnings.append(
                f"{cell}: logically proved {status.value}, but puzzle solution says "
                f"{self._solution[cell].value}"
            )
        self._proved[cell] = status
        clue = self._clues_by_owner.get(cell)
        if clue is not None:
            self._revealed_clues.append(clue)
        return clue

    def _clue_dict(self, clue: Optional[Clue]) -> Optional[dict[str, Any]]:
        if clue is None:
            return None
        return {
            "id": clue.id,
            "owner": clue.owner,
            "type": clue.type.value,
            "text": render_clue_text(clue, self.board),
            "highlight_cells": get_highlight_cells(clue, self.board),
        }

    # --------------------------------------------------------- Web API actions
    def submit_verdict(self, cell: str, status: Status | str) -> VerdictOutcome:
        """Judge a player's verdict and return a structured ``VerdictOutcome`` for the GUI."""
        cell = self.board.ref_to_cell(str(cell))
        target_status = status if isinstance(status, Status) else Status(str(status).strip().upper())
        ch = self.board.character_at(cell)

        if cell in self._proved:
            actual = self._proved[cell]
            if actual is target_status:
                return VerdictOutcome(
                    result=VerdictResult.ACCEPTED,
                    cell=cell,
                    status=target_status,
                    message=f"{ch.name} ({cell}) is already revealed as {actual.value}.",
                    revealed_clue=self._clue_dict(self._clues_by_owner.get(cell)),
                )
            return VerdictOutcome(
                result=VerdictResult.CONTRADICTED,
                cell=cell,
                status=target_status,
                message=f"CONTRADICTED: {ch.name} ({cell}) is already known to be {actual.value}.",
                revealed_clue=None,
            )

        result, clue = self.submit(cell, target_status)
        if result is VerdictResult.ACCEPTED:
            return VerdictOutcome(
                result=VerdictResult.ACCEPTED,
                cell=cell,
                status=target_status,
                message=f"ACCEPTED: {ch.name} ({cell}) is provably {target_status.value}!",
                revealed_clue=self._clue_dict(clue),
            )
        if result is VerdictResult.NOT_PROVABLE:
            return VerdictOutcome(
                result=VerdictResult.NOT_PROVABLE,
                cell=cell,
                status=target_status,
                message=(
                    f"NOT PROVABLE: Neither Criminal nor Innocent is logically forced for "
                    f"{ch.name} ({cell}) from the currently revealed clues. Do not guess!"
                ),
                revealed_clue=None,
            )
        return VerdictOutcome(
            result=VerdictResult.CONTRADICTED,
            cell=cell,
            status=target_status,
            message=(
                f"CONTRADICTED: Calling {ch.name} ({cell}) {target_status.value} contradicts "
                f"the current clues (the opposite status is forced)!"
            ),
            revealed_clue=None,
        )

    def revealed_clue_at(self, cell: str) -> Optional[Clue]:
        """Return the clue on ``cell`` ONLY if ``cell`` has already been revealed."""
        if cell not in self._proved:
            return None
        return self._clues_by_owner.get(cell)

    # --------------------------------------------------------- JSON serialiser
    def serialize_state(self) -> dict[str, Any]:
        """Serialize current public board state to the standard JSON contract."""
        state = self.public_state()

        cards: list[dict[str, Any]] = []
        for cell in self.board.cells():
            col_idx, row_idx = parse_cell(cell)
            ch = self.board.character_at(cell)
            is_revealed = cell in self._proved
            status = self._proved.get(cell)
            clue = self.revealed_clue_at(cell) if is_revealed else None
            cards.append(
                {
                    "cell": cell,
                    "row": row_idx + 1,
                    "col": chr(ord("A") + col_idx),
                    "name": ch.name,
                    "profession": ch.profession,
                    "is_revealed": is_revealed,
                    "status": status.value if status is not None else None,
                    "clue_id": clue.id if clue is not None else None,
                    "clue_text": render_clue_text(clue, self.board) if clue is not None else None,
                    "highlight_cells": get_highlight_cells(clue, self.board) if clue is not None else [],
                }
            )

        return {
            "puzzle_id": self.puzzle_id,
            "size": self.board.size,
            "is_solved": state.is_solved(),
            "proved_count": len(self._proved),
            "total_cells": self.board.size * self.board.size,
            "cards": cards,
        }
