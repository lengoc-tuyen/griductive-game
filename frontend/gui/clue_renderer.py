"""[D1] Convert structured Clue objects into natural-language strings and highlight cell lists.

Used by:
- ``GameEngine.serialize_state()`` to populate ``clue_text`` and ``highlight_cells`` in JSON for the Web UI.
- Any desktop/test UI that renders clue descriptions or highlights referenced regions.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from algorithms.logic.clues import ClueValidationError, referenced_cells
from algorithms.logic.models import Board, Clue, ClueType, Status, sort_row_major


def _format_ref(ref: str, board: Optional[Board] = None) -> str:
    """Format a cell or character reference nicely (e.g. keep name or cell id)."""
    if board is None:
        return str(ref)
    if board.has_cell(ref):
        ch = board.character_at(ref)
        return f"{ch.name} ({ref})" if ch.name else ref
    return str(ref)


def render_region_text(region: Mapping[str, Any], board: Optional[Board] = None) -> str:
    """Turn a region dictionary into natural English."""
    if not isinstance(region, Mapping):
        return str(region)
    kind = region.get("kind")
    if kind == "row":
        return f"row {region.get('row')}"
    if kind == "col":
        return f"column {region.get('col')}"
    if kind == "neighbors":
        target = region.get("of", "?")
        if board is not None and board.has_cell(str(target)):
            ch = board.character_at(str(target))
            return f"the neighbors of {ch.name} ({target})"
        return f"the neighbors of {target}"
    if kind == "cells":
        cells = region.get("cells", [])
        if isinstance(cells, (list, tuple)):
            return "{" + ", ".join(str(c) for c in cells) + "}"
        return str(cells)
    # Support future extension region kinds gracefully (corners, edges, between, common_neighbors, etc.)
    if kind == "corners":
        return "the corner cells"
    if kind == "edges" or kind == "boundary":
        return "the boundary cells"
    if kind == "between":
        return f"the cells between {region.get('a', '?')} and {region.get('b', '?')}"
    if kind == "common_neighbors":
        return f"the common neighbors of {region.get('a', '?')} and {region.get('b', '?')}"
    if kind == "intersection":
        r1 = render_region_text(region.get("a", {}), board)
        r2 = render_region_text(region.get("b", {}), board)
        return f"the intersection of {r1} and {r2}"
    return str(region)


def render_clue_text(clue: Clue, board: Optional[Board] = None) -> str:
    """Convert a structured ``Clue`` into a concise natural-language sentence."""
    p = clue.params
    # Allow explicit natural-language override if present in JSON params
    if isinstance(p.get("text"), str) and p["text"].strip():
        return p["text"].strip()

    ctype = clue.type
    if ctype is ClueType.FACT:
        person = p.get("person", "?")
        status_raw = str(p.get("status", "")).upper()
        if status_raw == Status.CRIMINAL.value:
            return f"{person} is a criminal."
        if status_raw == Status.INNOCENT.value:
            return f"{person} is innocent."
        return f"{person} is {status_raw.lower()}."

    if ctype is ClueType.SAME:
        return f"{p.get('a', '?')} and {p.get('b', '?')} have the same status."

    if ctype is ClueType.DIFFERENT:
        return f"{p.get('a', '?')} and {p.get('b', '?')} have different statuses."

    if ctype in (ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST):
        k = p.get("k", 0)
        reg_str = render_region_text(p.get("region", {}), board)
        if ctype in (ClueType.EXACTLY, ClueType.AT_MOST) and k == 0:
            return f"There are no criminals in {reg_str}."
        prefix = {
            ClueType.EXACTLY: "Exactly",
            ClueType.AT_LEAST: "At least",
            ClueType.AT_MOST: "At most",
        }[ctype]
        noun = "criminal" if k == 1 else "criminals"
        return f"{prefix} {k} {noun} in {reg_str}."

    return f"{ctype.value}: {dict(p)}"


def get_highlight_cells(clue: Clue, board: Board) -> list[str]:
    """Return the row-major sorted list of cells referenced or counted by ``clue``."""
    try:
        return sort_row_major(set(referenced_cells(clue, board)))
    except ClueValidationError:
        return []


def get_clue_highlight_cells(clue: Clue, board: Board) -> set[str]:
    """Set variant of ``get_highlight_cells``."""
    return set(get_highlight_cells(clue, board))


# Backwards-compatible aliases
region_text = render_region_text
clue_text = render_clue_text
