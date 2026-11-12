"""[A] CNF encoder: clues and known verdicts -> clauses (lists of signed ints).

Literal convention: ``+v`` means "cell of v is CRIMINAL", ``-v`` means INNOCENT.

* FACT(p, CRIMINAL)  -> [C_p]           FACT(p, INNOCENT) -> [-C_p]
* SAME(a, b)         -> (-a v b) (a v -b)
* DIFFERENT(a, b)    -> (a v b) (-a v -b)
* EXACTLY/AT_LEAST/AT_MOST(R, k) -> direct combinatorial encoding (``cardinality``)
* PARITY / COMPARE (extensions)  -> Tseitin encodings with auxiliary variables

Every clue is validated before it is encoded. Auxiliary variables come from the
shared ``VariableMap`` so they are always numbered after the primary C_i.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping

from algorithms.logic import cardinality, extensions
from algorithms.logic import clues as clue_rules
from algorithms.logic.models import Board, Clue, ClueType, Status
from algorithms.logic.regions import clue_region
from algorithms.logic.variable_map import VariableMap

Clause = list[int]


@dataclass
class EncodedCNF:
    clauses: list[Clause]
    num_primary: int
    num_aux: int
    clause_origin: list[str] = field(default_factory=list)  # clue id / "verdict:<cell>" per clause

    @property
    def num_vars(self) -> int:
        return self.num_primary + self.num_aux

    @property
    def num_clauses(self) -> int:
        return len(self.clauses)

    def counts(self) -> dict[str, int]:
        """Size report required by section 3.3."""
        return {"primary_vars": self.num_primary, "aux_vars": self.num_aux, "clauses": self.num_clauses}


class CNFEncoder:
    def __init__(self, board: Board, var_map: VariableMap | None = None) -> None:
        self.board = board
        self.vars = var_map or VariableMap(board)
        self._handlers: dict[ClueType, Callable[[Clue], list[Clause]]] = {
            ClueType.FACT: self._fact,
            ClueType.SAME: self._same,
            ClueType.DIFFERENT: self._different,
            ClueType.EXACTLY: self._counting(cardinality.exactly),
            ClueType.AT_LEAST: self._counting(cardinality.at_least),
            ClueType.AT_MOST: self._counting(cardinality.at_most),
            ClueType.PARITY: self._extension(extensions.encode_parity),
            ClueType.COMPARE: self._extension(extensions.encode_compare),
        }

    # -- public API ------------------------------------------------------------
    def encode_clue(self, clue: Clue) -> list[Clause]:
        clue_rules.validate(clue, self.board)
        return self._handlers[clue.type](clue)

    def encode_verdict(self, cell: str, status: Status) -> Clause:
        v = self.vars.var(cell)
        return [v] if Status(status) is Status.CRIMINAL else [-v]

    def encode(self, clues: Iterable[Clue], proved: Mapping[str, Status] | None = None) -> EncodedCNF:
        """CNF(clues) AND one unit clause per proved verdict (row-major)."""
        clauses: list[Clause] = []
        origin: list[str] = []
        for clue in clues:
            for cl in self.encode_clue(clue):
                clauses.append(cl)
                origin.append(clue.id)
        for cell, status in sorted((proved or {}).items(), key=lambda kv: Board.row_major_key(kv[0])):
            clauses.append(self.encode_verdict(cell, status))
            origin.append(f"verdict:{cell}")
        return EncodedCNF(clauses, self.vars.num_primary, self.vars.num_aux, origin)

    # -- handlers --------------------------------------------------------------
    def _fact(self, clue: Clue) -> list[Clause]:
        v = self.vars.var_of_name(clue.params["person"])
        return [[v] if Status(clue.params["status"]) is Status.CRIMINAL else [-v]]

    def _same(self, clue: Clue) -> list[Clause]:
        a = self.vars.var_of_name(clue.params["a"])
        b = self.vars.var_of_name(clue.params["b"])
        return [[-a, b], [a, -b]]

    def _different(self, clue: Clue) -> list[Clause]:
        a = self.vars.var_of_name(clue.params["a"])
        b = self.vars.var_of_name(clue.params["b"])
        return [[a, b], [-a, -b]]

    def _counting(self, fn: Callable[[list[int], int], list[Clause]]):
        def handler(clue: Clue) -> list[Clause]:
            lits = extensions.counted_literals(clue, clue_region(clue, self.board), self.vars.var)
            return fn(lits, clue.params["k"])

        return handler

    def _extension(self, fn):
        def handler(clue: Clue) -> list[Clause]:
            return fn(clue, self.board, self.vars.var, self.vars.new_aux)

        return handler
