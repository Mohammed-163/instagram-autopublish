"""Shared helper for keyword-position analyzers. Not a plugin itself."""
from __future__ import annotations

from typing import List, Optional, Tuple


def find_first_position(text: str, keywords: List[str]) -> Tuple[bool, Optional[float]]:
    """Return (present, normalized_position in [0,1]) for the earliest
    occurrence of any keyword in `keywords` (case-insensitive)."""
    if not text:
        return False, None
    lowered = text.lower()
    best_idx: Optional[int] = None
    for kw in keywords:
        idx = lowered.find(kw.lower())
        if idx != -1 and (best_idx is None or idx < best_idx):
            best_idx = idx
    if best_idx is None:
        return False, None
    return True, round(best_idx / len(text), 4)
