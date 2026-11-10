"""[C] Hint (basic): one currently forced character, from public state only.

Pointing at the revealed clue(s) that justify the hint is planned as an extension.
"""

from __future__ import annotations

from typing import Optional

from algorithms.agent.deduction_agent import ForcedVerdict, next_forced
from algorithms.agent.public_state import PublicState


def hint(state: PublicState) -> Optional[ForcedVerdict]:
    """Return the next provable verdict, or None if nothing is forced.

    Raises ``ValueError`` if the public knowledge is inconsistent.
    """
    return next_forced(state)
