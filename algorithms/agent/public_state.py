"""[C] Contract between the Game Engine (D) and the Logic Agent (C).

The engine owns the full puzzle (hidden solution + unrevealed clues). It hands the
agent ONLY a ``PublicState``: the board layout, the revealed clues, and the proved
verdicts. The agent never receives the puzzle object itself.

D implements ``EngineProtocol`` in ``frontend/engine/game_engine.py``. To judge a
user's verdict the engine should call ``algorithms.agent.entailment.check_verdict``
on its current public state (not compare with the hidden solution).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Protocol

from algorithms.logic.models import Board, Clue, Status


class VerdictResult(str, Enum):
    ACCEPTED = "ACCEPTED"          # verdict is entailed by public knowledge -> reveal card
    NOT_PROVABLE = "NOT_PROVABLE"  # neither status is currently forced
    CONTRADICTED = "CONTRADICTED"  # the opposite status is currently forced


@dataclass(frozen=True)
class PublicState:
    board: Board
    revealed_clues: tuple[Clue, ...] = ()
    proved: Mapping[str, Status] = field(default_factory=dict)  # cell -> status

    def unresolved_cells(self) -> list[str]:
        """Cells without a proved status, row-major."""
        return [c for c in self.board.cells() if c not in self.proved]

    def is_solved(self) -> bool:
        return len(self.proved) == self.board.size * self.board.size

    def clue_ids(self) -> list[str]:
        return [c.id for c in self.revealed_clues]


class EngineProtocol(Protocol):
    def public_state(self) -> PublicState:
        """Current public knowledge."""
        ...

    def submit(self, cell: str, status: Status) -> tuple[VerdictResult, Optional[Clue]]:
        """Submit a verdict. On ACCEPTED, the card is revealed and its clue (or None
        if the card has no clue) is returned. Otherwise the state is unchanged."""
        ...
