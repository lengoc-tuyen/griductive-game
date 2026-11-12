"""[D1] Verdict result enum and response model for GameEngine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from algorithms.agent.public_state import VerdictResult
from algorithms.logic.models import Status

__all__ = [
    "VerdictResult",
    "VerdictOutcome",
]


@dataclass
class VerdictOutcome:
    result: VerdictResult
    cell: str
    status: Status
    message: str
    revealed_clue: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result.value,
            "cell": self.cell,
            "status": self.status.value,
            "message": self.message,
            "revealed_clue": self.revealed_clue,
        }
