"""[D1] Convert structured Clue objects into natural-language strings, color-coded segments,
and highlight groups for the Web UI.

Each colored segment in ``segments`` carries a ``group`` index referencing the corresponding
entry in ``highlight_groups``, so clicking any individual keyword or character name inside
a clue (e.g. "Abel", "Ivy", "cells between", "row 2", "neighbors") can isolate ONLY that
group on the board.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from algorithms.logic import regions
from algorithms.logic.clues import ClueValidationError, referenced_cells
from algorithms.logic.models import Board, Clue, ClueType, Status, sort_row_major

# High-contrast Knotwise-inspired palette for warm parchment (#F4F0E8)
COLOR_REGION_A = "#2580C3"    # Crisp blue
COLOR_ANCHOR = "#C28416"      # Warm amber gold (referenced characters)
COLOR_REGION_B = "#9B36B5"    # Rich plum purple (2nd region / 2nd person)
COLOR_NEIGHBORS = "#2B2BB8"   # Deep indigo (neighbor regions)


def _counted_nouns(clue: Clue) -> tuple[str, str]:
    """Return (singular, plural) nouns for the status counted by ``clue``."""
    raw = str(clue.params.get("counts", Status.CRIMINAL.value)).upper()
    if raw == Status.INNOCENT.value:
        return "innocent", "innocents"
    return "criminal", "criminals"


def _person_label(ref: Any, board: Optional[Board] = None) -> str:
    """Display character name when available (short & clear on compact cards)."""
    text = str(ref)
    if board is not None and board.has_cell(text):
        ch = board.character_at(text)
        return ch.name if ch.name else text
    return text


def _safe_ref_cell(ref: Any, board: Optional[Board]) -> Optional[str]:
    if board is None or ref is None:
        return None
    try:
        return board.ref_to_cell(str(ref))
    except KeyError:
        return None


def _safe_resolve_region(region: Mapping[str, Any], board: Optional[Board]) -> list[str]:
    if board is None or not isinstance(region, Mapping):
        return []
    try:
        return regions.resolve(region, board)
    except regions.RegionError:
        return []


def _capitalize_first(text: str) -> str:
    return text[0].upper() + text[1:] if text else text


def _capitalize_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not segments:
        return segments
    out = [dict(s) for s in segments]
    for seg in out:
        if seg.get("text"):
            seg["text"] = _capitalize_first(str(seg["text"]))
            break
    return out


def _offset_segment_groups(segments: list[dict[str, Any]], offset: int) -> list[dict[str, Any]]:
    out = []
    for seg in segments:
        copy = dict(seg)
        if copy.get("group") is not None:
            copy["group"] = int(copy["group"]) + offset
        out.append(copy)
    return out


def render_region_text(region: Mapping[str, Any], board: Optional[Board] = None) -> str:
    """Turn a region dictionary into concise natural English."""
    if not isinstance(region, Mapping):
        return str(region)
    kind = region.get("kind")
    if kind == "row":
        return f"row {region.get('row')}"
    if kind == "col":
        return f"column {region.get('col')}"
    if kind == "neighbors":
        target = _person_label(region.get("of", "?"), board)
        return f"{target}'s neighbors"
    if kind == "cells":
        cells = region.get("cells", [])
        if isinstance(cells, (list, tuple)):
            if len(cells) == 1:
                return str(cells[0])
            return "{" + ", ".join(str(c) for c in cells) + "}"
        return str(cells)
    if kind == "corners":
        return "the corners"
    if kind in ("edges", "boundary"):
        return "the boundary cells"
    if kind == "between":
        a = _person_label(region.get("a", "?"), board)
        b = _person_label(region.get("b", "?"), board)
        return f"cells between {a} and {b}"
    if kind == "common_neighbors":
        a = _person_label(region.get("a", "?"), board)
        b = _person_label(region.get("b", "?"), board)
        return f"common neighbors of {a} & {b}"
    if kind == "intersection":
        r1 = render_region_text(region.get("a", {}), board)
        r2 = render_region_text(region.get("b", {}), board)
        return f"overlap of {r1} and {r2}"
    return str(region)


def _region_visuals(
    region: Mapping[str, Any],
    board: Optional[Board],
    region_color: str,
    anchor_color: str = COLOR_ANCHOR,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return ``(segments, highlight_groups)`` with local group indices starting at 0."""
    resolved = _safe_resolve_region(region, board)
    kind = region.get("kind") if isinstance(region, Mapping) else None
    groups: list[dict[str, Any]] = []

    def add_group(color: str, cells: list[str], tint_name: bool) -> Optional[int]:
        if not cells:
            return None
        idx = len(groups)
        groups.append({"color": color, "cells": cells, "tint_name": tint_name})
        return idx

    if kind == "neighbors":
        target_ref = region.get("of", "?")
        target_name = _person_label(target_ref, board)
        center_cell = _safe_ref_cell(target_ref, board)
        g_anchor = add_group(anchor_color, [center_cell] if center_cell else [], True)
        g_reg = add_group(region_color, resolved, False)
        segs = [
            {"text": target_name, "color": anchor_color, "group": g_anchor},
            {"text": "'s ", "color": None, "group": None},
            {"text": "neighbors", "color": region_color, "group": g_reg},
        ]
        return segs, groups

    if kind == "between":
        a_ref, b_ref = region.get("a", "?"), region.get("b", "?")
        a_name, b_name = _person_label(a_ref, board), _person_label(b_ref, board)
        cell_a, cell_b = _safe_ref_cell(a_ref, board), _safe_ref_cell(b_ref, board)
        g_reg = add_group(region_color, resolved, False)
        g_a = add_group(anchor_color, [cell_a] if cell_a else [], True)
        g_b = add_group(anchor_color, [cell_b] if cell_b else [], True)
        segs = [
            {"text": "cells between", "color": region_color, "group": g_reg},
            {"text": " ", "color": None, "group": None},
            {"text": a_name, "color": anchor_color, "group": g_a},
            {"text": " and ", "color": None, "group": None},
            {"text": b_name, "color": anchor_color, "group": g_b},
        ]
        return segs, groups

    if kind == "common_neighbors":
        a_ref, b_ref = region.get("a", "?"), region.get("b", "?")
        a_name, b_name = _person_label(a_ref, board), _person_label(b_ref, board)
        cell_a, cell_b = _safe_ref_cell(a_ref, board), _safe_ref_cell(b_ref, board)
        g_reg = add_group(region_color, resolved, False)
        g_a = add_group(anchor_color, [cell_a] if cell_a else [], True)
        g_b = add_group(anchor_color, [cell_b] if cell_b else [], True)
        segs = [
            {"text": "common neighbors", "color": region_color, "group": g_reg},
            {"text": " of ", "color": None, "group": None},
            {"text": a_name, "color": anchor_color, "group": g_a},
            {"text": " & ", "color": None, "group": None},
            {"text": b_name, "color": anchor_color, "group": g_b},
        ]
        return segs, groups

    reg_str = render_region_text(region, board)
    g_reg = add_group(region_color, resolved, False)
    segs = [{"text": reg_str, "color": region_color, "group": g_reg}]
    return segs, groups


def render_clue_visuals(clue: Clue, board: Optional[Board] = None) -> dict[str, Any]:
    """Return structured visual metadata for rendering color-coded clues & card borders."""
    p = clue.params
    if isinstance(p.get("text"), str) and p["text"].strip():
        txt = p["text"].strip()
        cells = get_highlight_cells(clue, board) if board is not None else []
        groups = [{"color": COLOR_REGION_A, "cells": cells, "tint_name": False}] if cells else []
        return {
            "text": txt,
            "primary_color": COLOR_REGION_A,
            "segments": [{"text": txt, "color": COLOR_REGION_A if cells else None, "group": 0 if cells else None}],
            "highlight_groups": groups,
        }

    ctype = clue.type
    singular, plural = _counted_nouns(clue)

    if ctype is ClueType.FACT:
        person_ref = p.get("person", "?")
        person = _person_label(person_ref, board)
        cell = _safe_ref_cell(person_ref, board)
        status_raw = str(p.get("status", "")).upper()
        if status_raw == Status.CRIMINAL.value:
            suffix = " is a criminal."
        elif status_raw == Status.INNOCENT.value:
            suffix = " is innocent."
        else:
            suffix = f" is {status_raw.lower()}."
        groups = [{"color": COLOR_ANCHOR, "cells": [cell], "tint_name": True}] if cell else []
        segs = [
            {"text": person, "color": COLOR_ANCHOR, "group": 0 if cell else None},
            {"text": suffix, "color": None, "group": None},
        ]
        return {
            "text": f"{person}{suffix}",
            "primary_color": COLOR_ANCHOR,
            "segments": segs,
            "highlight_groups": groups,
        }

    if ctype in (ClueType.SAME, ClueType.DIFFERENT):
        a_ref, b_ref = p.get("a", "?"), p.get("b", "?")
        a_name, b_name = _person_label(a_ref, board), _person_label(b_ref, board)
        cell_a, cell_b = _safe_ref_cell(a_ref, board), _safe_ref_cell(b_ref, board)
        tail = " have the same status." if ctype is ClueType.SAME else " have different statuses."
        groups: list[dict[str, Any]] = []
        g_a = None
        g_b = None
        if cell_a:
            g_a = len(groups)
            groups.append({"color": COLOR_ANCHOR, "cells": [cell_a], "tint_name": True})
        if cell_b:
            g_b = len(groups)
            groups.append({"color": COLOR_REGION_B, "cells": [cell_b], "tint_name": True})
        segs = [
            {"text": a_name, "color": COLOR_ANCHOR, "group": g_a},
            {"text": " and ", "color": None, "group": None},
            {"text": b_name, "color": COLOR_REGION_B, "group": g_b},
            {"text": tail, "color": None, "group": None},
        ]
        return {
            "text": f"{a_name} and {b_name}{tail}",
            "primary_color": COLOR_ANCHOR,
            "segments": segs,
            "highlight_groups": groups,
        }

    if ctype in (ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST):
        k = p.get("k", 0)
        region = p.get("region", {})
        kind = region.get("kind") if isinstance(region, Mapping) else None
        reg_color = COLOR_NEIGHBORS if kind in ("neighbors", "common_neighbors") else COLOR_REGION_A
        reg_segs, groups = _region_visuals(region, board, reg_color, COLOR_ANCHOR)

        if ctype in (ClueType.EXACTLY, ClueType.AT_MOST) and k == 0:
            lead = f"No {plural} in "
        else:
            prefix = {
                ClueType.EXACTLY: "Exactly",
                ClueType.AT_LEAST: "At least",
                ClueType.AT_MOST: "At most",
            }[ctype]
            noun = singular if k == 1 else plural
            lead = f"{prefix} {k} {noun} in "

        segs = [{"text": lead, "color": None, "group": None}, *reg_segs, {"text": ".", "color": None, "group": None}]
        return {
            "text": "".join(s["text"] for s in segs),
            "primary_color": reg_color,
            "segments": segs,
            "highlight_groups": groups,
        }

    if ctype is ClueType.PARITY:
        parity = str(p.get("parity", "EVEN")).upper()
        region = p.get("region", {})
        kind = region.get("kind") if isinstance(region, Mapping) else None
        reg_color = COLOR_NEIGHBORS if kind in ("neighbors", "common_neighbors") else COLOR_REGION_A
        reg_segs, groups = _region_visuals(region, board, reg_color, COLOR_ANCHOR)
        word = "Odd" if parity == "ODD" else "Even"
        lead = f"{word} number of {plural} in "
        segs = [{"text": lead, "color": None, "group": None}, *reg_segs, {"text": ".", "color": None, "group": None}]
        return {
            "text": "".join(s["text"] for s in segs),
            "primary_color": reg_color,
            "segments": segs,
            "highlight_groups": groups,
        }

    if ctype is ClueType.COMPARE:
        region_a = p.get("region_a", {})
        region_b = p.get("region_b", {})
        op = str(p.get("op", "EQUAL")).upper()
        segs_a, groups_a = _region_visuals(region_a, board, COLOR_REGION_A, COLOR_ANCHOR)
        segs_b_raw, groups_b = _region_visuals(region_b, board, COLOR_REGION_B, COLOR_ANCHOR)
        segs_a = _capitalize_segments(segs_a)
        segs_b = _offset_segment_groups(segs_b_raw, len(groups_a))

        if op == "MORE":
            segs = [
                *segs_a,
                {"text": f" has more {plural} than ", "color": None, "group": None},
                *segs_b,
                {"text": ".", "color": None, "group": None},
            ]
        elif op == "FEWER":
            segs = [
                *segs_a,
                {"text": f" has fewer {plural} than ", "color": None, "group": None},
                *segs_b,
                {"text": ".", "color": None, "group": None},
            ]
        else:
            segs = [
                *segs_a,
                {"text": " and ", "color": None, "group": None},
                *segs_b,
                {"text": f" have equal {plural}.", "color": None, "group": None},
            ]

        return {
            "text": "".join(s["text"] for s in segs),
            "primary_color": COLOR_REGION_A,
            "segments": segs,
            "highlight_groups": [*groups_a, *groups_b],
        }

    fallback = f"{ctype.value}: {dict(p)}"
    return {
        "text": fallback,
        "primary_color": COLOR_REGION_A,
        "segments": [{"text": fallback, "color": None, "group": None}],
        "highlight_groups": [],
    }


def render_clue_text(clue: Clue, board: Optional[Board] = None) -> str:
    """Convert a structured ``Clue`` into a concise natural-language sentence."""
    return render_clue_visuals(clue, board)["text"]


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
