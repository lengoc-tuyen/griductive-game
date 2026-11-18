"""[E] Character names and professions pool for board generation.

PDF Requirement 2.1:
"Characters are ordered alphabetically by display name."
"""

from __future__ import annotations

import random
from typing import Optional

from algorithms.logic.models import Character, make_cell

# 26 names ordered alphabetically A..Z
DEFAULT_NAMES = [
    "Abel", "Bea", "Clara", "Derek", "Eliza",
    "Franz", "Grant", "Hannah", "Ivy", "Jonas",
    "Karl", "Leo", "Mara", "Noah", "Owen",
    "Priya", "Quinn", "Rose", "Sam", "Tina",
    "Uma", "Victor", "Wendy", "Xander", "Yara", "Zack"
]

DEFAULT_PROFESSIONS = [
    "Detective", "Doctor", "Engineer", "Clerk", "Guard",
    "Cook", "Painter", "Farmer", "Astronaut", "Teacher",
    "Scientist", "Pilot", "Lawyer", "Writer", "Nurse",
    "Architect", "Mechanic", "Librarian", "Musician", "Baker",
    "Judge", "Sailor", "Tailor", "Photographer", "Electrician", "Florist"
]


def generate_characters(size: int, seed: Optional[int] = None) -> list[Character]:
    """Generate N*N characters mapped to cells in row-major order with names sorted alphabetically."""
    num_cells = size * size
    if num_cells > len(DEFAULT_NAMES):
        raise ValueError(f"Board size {size}x{size} requires {num_cells} characters, pool has {len(DEFAULT_NAMES)}")

    rng = random.Random(seed) if seed is not None else random.Random()
    professions = list(DEFAULT_PROFESSIONS)
    rng.shuffle(professions)

    characters = []
    idx = 0
    for r in range(size):
        for c in range(size):
            cell = make_cell(c, r)
            name = DEFAULT_NAMES[idx]
            prof = professions[idx % len(professions)]
            characters.append(Character(name=name, profession=prof, cell=cell))
            idx += 1

    return characters

