"""[A] Shared data types used by every module (engine, agent, data loader).

Conventions
-----------
* A cell is a string ``"<COLUMN LETTER><ROW NUMBER>"`` such as ``"C2"``.
  Columns are lettered from the left (A, B, ...), rows numbered from the top (1, 2, ...).
* "Row-major order" means A1, B1, C1, ..., A2, B2, ...

JSON shapes (see also ``data/schema.md``)
-----------------------------------------
Character: ``{"name": "Abel", "profession": "Astronaut", "cell": "A1"}``

Clue: ``{"id": "clue_A1", "owner": "A1", "type": "EXACTLY", "params": {...}}``

==============  =================================================
type            params
==============  =================================================
FACT            ``{"person": "Abel", "status": "CRIMINAL"}``
SAME            ``{"a": "Abel", "b": "Bea"}``
DIFFERENT       ``{"a": "Abel", "b": "Bea"}``
EXACTLY         ``{"region": <Region>, "k": 2}``
AT_LEAST        ``{"region": <Region>, "k": 2}``
AT_MOST         ``{"region": <Region>, "k": 2}``
==============  =================================================

Region (resolved by ``algorithms.logic.regions``):

* ``{"kind": "row", "row": 2}``
* ``{"kind": "col", "col": "B"}``
* ``{"kind": "neighbors", "of": "C2"}``  (``of`` may be a cell or a person name)
* ``{"kind": "cells", "cells": ["A1", "B3"]}``  (items may be cells or person names)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

_CELL_RE = re.compile(r"^([A-Z])([1-9][0-9]*)$")


class Status(str, Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"

    @property
    def opposite(self) -> "Status":
        return Status.INNOCENT if self is Status.CRIMINAL else Status.CRIMINAL


class ClueType(str, Enum):
    FACT = "FACT"
    SAME = "SAME"
    DIFFERENT = "DIFFERENT"
    EXACTLY = "EXACTLY"
    AT_LEAST = "AT_LEAST"
    AT_MOST = "AT_MOST"


COUNTING_TYPES = frozenset({ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST})


# --------------------------------------------------------------------------- cells
def is_cell_string(text: str) -> bool:
    return isinstance(text, str) and _CELL_RE.match(text) is not None


def parse_cell(cell: str) -> tuple[int, int]:
    """``"C2"`` -> ``(col_index, row_index)`` = ``(2, 1)`` (both 0-based)."""
    m = _CELL_RE.match(cell) if isinstance(cell, str) else None
    if m is None:
        raise ValueError(f"invalid cell identifier: {cell!r}")
    return ord(m.group(1)) - ord("A"), int(m.group(2)) - 1


def make_cell(col_index: int, row_index: int) -> str:
    """``(2, 1)`` -> ``"C2"`` (both 0-based)."""
    if not (0 <= col_index < 26) or row_index < 0:
        raise ValueError(f"invalid cell coordinates: ({col_index}, {row_index})")
    return f"{chr(ord('A') + col_index)}{row_index + 1}"


# ---------------------------------------------------------------------- characters
@dataclass(frozen=True)
class Character:
    name: str
    profession: str
    cell: str

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Character":
        return cls(name=d["name"], profession=d.get("profession", ""), cell=d["cell"])

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "profession": self.profession, "cell": self.cell}


@dataclass(frozen=True)
class Board:
    """Public, static information about the grid: size + who sits where.

    Contains NO statuses and NO clues, so it is safe to give to the agent.
    """

    size: int
    characters: tuple[Character, ...]
    _by_cell: dict[str, Character] = field(init=False, repr=False, compare=False)
    _by_name: dict[str, Character] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.size, int) or not (1 <= self.size <= 26):
            raise ValueError(f"board size must be an int in [1, 26], got {self.size!r}")
        object.__setattr__(self, "characters", tuple(self.characters))
        by_cell: dict[str, Character] = {}
        by_name: dict[str, Character] = {}
        for ch in self.characters:
            c, r = parse_cell(ch.cell)
            if c >= self.size or r >= self.size:
                raise ValueError(f"cell {ch.cell} is outside a {self.size}x{self.size} board")
            if ch.cell in by_cell:
                raise ValueError(f"two characters on cell {ch.cell}")
            if ch.name in by_name:
                raise ValueError(f"duplicate character name {ch.name!r}")
            by_cell[ch.cell] = ch
            by_name[ch.name] = ch
        if len(by_cell) != self.size * self.size:
            raise ValueError(f"expected {self.size * self.size} characters, got {len(by_cell)}")
        object.__setattr__(self, "_by_cell", by_cell)
        object.__setattr__(self, "_by_name", by_name)

    # -- lookups ---------------------------------------------------------------
    def cells(self) -> list[str]:
        """All cells in row-major order."""
        return [make_cell(c, r) for r in range(self.size) for c in range(self.size)]

    def has_cell(self, cell: str) -> bool:
        return cell in self._by_cell

    def character_at(self, cell: str) -> Character:
        try:
            return self._by_cell[cell]
        except KeyError:
            raise KeyError(f"no character on cell {cell!r}") from None

    def cell_of(self, name: str) -> str:
        try:
            return self._by_name[name].cell
        except KeyError:
            raise KeyError(f"unknown character {name!r}") from None

    def ref_to_cell(self, ref: str) -> str:
        """Accept either a cell id (``"B3"``) or a character name; return the cell."""
        if ref in self._by_cell:
            return ref
        if ref in self._by_name:
            return self._by_name[ref].cell
        raise KeyError(f"{ref!r} is neither a cell on the board nor a character name")

    @staticmethod
    def row_major_key(cell: str) -> tuple[int, int]:
        c, r = parse_cell(cell)
        return r, c

    # -- (de)serialisation -----------------------------------------------------
    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Board":
        return cls(size=d["size"], characters=tuple(Character.from_dict(x) for x in d["characters"]))

    def to_dict(self) -> dict[str, Any]:
        return {"size": self.size, "characters": [ch.to_dict() for ch in self.characters]}


# --------------------------------------------------------------------------- clues
@dataclass(frozen=True)
class Clue:
    id: str
    owner: str  # cell of the card that carries this clue
    type: ClueType
    params: Mapping[str, Any]

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Clue":
        return cls(
            id=d["id"],
            owner=d["owner"],
            type=ClueType(d["type"]),
            params=dict(d.get("params", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "owner": self.owner, "type": self.type.value, "params": dict(self.params)}


def sort_row_major(cells: Iterable[str]) -> list[str]:
    return sorted(cells, key=Board.row_major_key)
