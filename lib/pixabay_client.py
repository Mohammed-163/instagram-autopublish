"""
Pixabay API wrapper — downloads a background image matching given keywords.
"""
import random

import requests

from . import config


class PixabayClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def download_background(self, keywords: str, output_path: str) -> str:
        """Downloads a vertical/large image matching keywords. Falls back to a
        generic abstract query if no results are found. Returns output_path."""
        image_url = self._find_image_url(keywords) or self._find_image_url(config.PIXABAY_FALLBACK_KEYWORDS)
        if not image_url:
            raise RuntimeError(f"No Pixabay results for '{keywords}' or fallback query")

        resp = requests.get(image_url, timeout=30)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
        return output_path

    def _find_image_url(self, query: str) -> str | None:
        resp = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": self.api_key,
                "q": query,
                "image_type": "photo",
                "orientation": "vertical",
                "safesearch": "true",
                "per_page": 20,
            },
            timeout=20,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        if not hits:
            return None
        chosen = random.choice(hits[:10])
        return chosen.get("largeImageURL") or chosen.get("webformatURL")
