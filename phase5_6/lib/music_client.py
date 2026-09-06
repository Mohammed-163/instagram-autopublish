import os
import random
import requests
from typing import Optional

BASE_URL = "https://api.freetouse.com/v3"

# كلمات بحث موجهة لطابع روحاني/تأملي هادئ
SEARCH_QUERIES = [
    "ambient calm meditation",
    "peaceful spiritual nature",
    "soft piano ambient",
    "calm meditation background",
]

# وسوم يجب استبعاد أي مقطع يحتوي عليها (غير مناسبة لمجالس اللهو / طابع صاخب)
BLACKLIST_TAGS = {
    "party", "dance", "hype", "trap", "club", "edm", "aggressive",
    "workout", "gym", "energetic", "rock", "metal", "rap", "hip hop",
    "festival", "drop", "bass", "dj",
}


def _track_is_safe(track: dict) -> bool:
    """يتحقق أن المقطع آلي بالكامل (بلا غناء) وخالٍ من الوسوم غير المناسبة."""
    if track.get("lyrics") is not None:
        return False  # فيه كلمات غناء بأي لغة -> مرفوض

    if track.get("is_premium"):
        return False  # نتجنب المحتوى المدفوع لضمان الترخيص المجاني الآمن

    tags_categories = track.get("tags_categories", [])
    text_blob = " ".join(
        str(item[1]).lower() if isinstance(item[1], str) else str(item[1].get("name", "")).lower()
        for item in tags_categories
    )
    if any(bad_word in text_blob for bad_word in BLACKLIST_TAGS):
        return False

    if not track.get("files", {}).get("mp3"):
        return False

    return True


def get_random_instrumental_track(workdir: str, timeout: int = 15) -> Optional[str]:
    """
    يبحث عن مقطع موسيقي هادئ آلي (بلا غناء) مناسب، يحمّله محلياً لمجلد workdir،
    ويرجع المسار المحلي الكامل. يرجع None بأمان تام عند أي فشل (fail-open).
    """
    query = random.choice(SEARCH_QUERIES)

    try:
        resp = requests.get(
            f"{BASE_URL}/music/tracks/search",
            params={"query": query, "limit": 20, "order": "random"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            return None

        candidates = [t for t in data.get("data", []) if _track_is_safe(t)]
        if not candidates:
            return None

        track = random.choice(candidates)
        mp3_url = track["files"]["mp3"]

        audio_resp = requests.get(mp3_url, timeout=timeout)
        audio_resp.raise_for_status()

        output_path = os.path.join(workdir, "bg_music.mp3")
        with open(output_path, "wb") as f:
            f.write(audio_resp.content)

        return output_path

    except Exception:
        return None
