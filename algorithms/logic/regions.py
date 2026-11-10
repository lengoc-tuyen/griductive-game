"""[A] Region resolution.

``resolve(region, board)`` turns a region spec into the list of cells it covers,
sorted row-major, with no duplicates. Supported kinds: ``row``, ``col``,
``neighbors`` (8 directions, the cell itself excluded) and ``cells`` (explicit list).
Advanced regions (corners, edges, between two people, ...) belong to extensions.
"""

from __future__ import annotations

from typing import Any, Mapping

from algorithms.logic.models import Board, make_cell, parse_cell, sort_row_major


class RegionError(ValueError):
    pass


def _row(region: Mapping[str, Any], board: Board) -> list[str]:
    row = region.get("row")
    if not isinstance(row, int) or isinstance(row, bool) or not (1 <= row <= board.size):
        raise RegionError(f"row must be an int in [1, {board.size}], got {row!r}")
    return [make_cell(c, row - 1) for c in range(board.size)]


def _col(region: Mapping[str, Any], board: Board) -> list[str]:
    col = region.get("col")
    if not isinstance(col, str) or len(col) != 1 or not ("A" <= col < chr(ord("A") + board.size)):
        raise RegionError(f"col must be a letter A..{chr(ord('A') + board.size - 1)}, got {col!r}")
    ci = ord(col) - ord("A")
    return [make_cell(ci, r) for r in range(board.size)]


def neighbors_of(cell: str, board: Board) -> list[str]:
    c0, r0 = parse_cell(cell)
    out = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            c, r = c0 + dc, r0 + dr
            if 0 <= c < board.size and 0 <= r < board.size:
                out.append(make_cell(c, r))
    return sort_row_major(out)


def _neighbors(region: Mapping[str, Any], board: Board) -> list[str]:
    ref = region.get("of")
    try:
        center = board.ref_to_cell(ref)
    except (KeyError, TypeError) as e:
        raise RegionError(f"neighbors: {e}") from None
    return neighbors_of(center, board)


def _cells(region: Mapping[str, Any], board: Board) -> list[str]:
    items = region.get("cells")
    if not isinstance(items, (list, tuple)) or not items:
        raise RegionError("cells: expected a non-empty list")
    out = []
    for ref in items:
        try:
            out.append(board.ref_to_cell(ref))
        except (KeyError, TypeError) as e:
            raise RegionError(f"cells: {e}") from None
    if len(set(out)) != len(out):
        raise RegionError(f"cells: duplicate cells in {list(items)!r}")
    return sort_row_major(out)


_RESOLVERS = {
    "row": _row,
    "col": _col,
    "neighbors": _neighbors,
    "cells": _cells,
}


def register_region(kind: str, resolver) -> None:
    """Hook for extensions: ``resolver(region_dict, board) -> list[cell]``."""
    _RESOLVERS[kind] = resolver


def resolve(region: Mapping[str, Any], board: Board) -> list[str]:
    if not isinstance(region, Mapping):
        raise RegionError(f"region must be a mapping, got {region!r}")
    kind = region.get("kind")
    resolver = _RESOLVERS.get(kind)
    if resolver is None:
        raise RegionError(f"unknown region kind {kind!r}")
    return resolver(region, board)
