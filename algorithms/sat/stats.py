"""[B] Solver statistics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SolverStats:
    decisions: int = 0      # branching choices made
    propagations: int = 0   # literals assigned by unit propagation
    backtracks: int = 0     # branches undone after a conflict
    conflicts: int = 0      # empty clauses met
    runtime: float = 0.0    # seconds

    def merge(self, other: "SolverStats") -> None:
        self.decisions += other.decisions
        self.propagations += other.propagations
        self.backtracks += other.backtracks
        self.conflicts += other.conflicts
        self.runtime += other.runtime

    def as_dict(self) -> dict[str, float]:
        return {
            "decisions": self.decisions,
            "propagations": self.propagations,
            "backtracks": self.backtracks,
            "conflicts": self.conflicts,
            "runtime": self.runtime,
        }
