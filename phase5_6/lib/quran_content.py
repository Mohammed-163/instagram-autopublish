"""Small, locally stored source of hopeful Quran verses with explicit references."""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date, timedelta
from difflib import SequenceMatcher


VERSE_FILE = os.path.join(os.path.dirname(__file__), "..", "assets", "quran_hope_verses.json")


def load_verses() -> list[dict]:
    with open(VERSE_FILE, encoding="utf-8") as source:
        verses = json.load(source)
    if not verses or any(not item.get("key") or not item.get("text") for item in verses):
        raise ValueError("Quran verse source is empty or missing a key/text")
    return verses


def verse_by_key(key: str) -> dict:
    for verse in load_verses():
        if verse["key"] == key:
            return verse
    raise KeyError(f"Unknown Quran verse reference: {key}")

def verse_reference_parts(verse: dict) -> tuple[str, str, str]:
    """Parse the authoritative key and validate that its ordinal matches the entry."""
    key = str(verse["key"]).strip()
    match = re.fullmatch(r"([1-9][0-9]*):([1-9][0-9]*)(?:-([1-9][0-9]*))?", key)
    if not match:
        raise ValueError(f"Invalid Quran verse key: {key!r}")
    chapter, first, last = match.groups()
    if not 1 <= int(chapter) <= 114 or int(verse["ayah"]) != int(first):
        raise ValueError(f"Mismatched Quran verse reference: {key!r}")
    if last and int(last) <= int(first):
        raise ValueError(f"Invalid Quran verse range: {key!r}")
    surah = str(verse["surah"]).strip()
    if not surah:
        raise ValueError(f"Missing surah name for {key!r}")
    return surah, first, last or first


def format_verse_reference(verse: dict) -> str:
    """Shared Arabic reference for the video and caption, including all ayat."""
    surah, first, last = verse_reference_parts(verse)
    if first == last:
        return f"{surah}، الآية {first}"
    return f"{surah}، الآيات من {first} إلى {last}"


def sunday_of(value: date) -> date:
    """Return Sunday, the first day of the Iraq-based publishing week."""
    return value - timedelta(days=(value.weekday() + 1) % 7)


def explanation_is_duplicate(candidate: str, prior: list[str]) -> bool:
    def normalize(value: str) -> str:
        value = "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.category(ch).startswith("M"))
        return " ".join(re.findall(r"[\w]+", value.casefold()))

    normalized = normalize(candidate)
    if not normalized:
        return True
    return any(
        normalized == normalize(old)
        or SequenceMatcher(None, normalized, normalize(old)).ratio() >= 0.84
        for old in prior if old
    )
