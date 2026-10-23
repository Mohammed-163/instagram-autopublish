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
        """Downloads a single vertical/large image matching keywords (no
        vetting). Kept for callers (e.g. the test script) that just need
        *an* image. daily_generate.py uses download_candidates() instead so
        Gemini can vet multiple options before one is picked."""
        urls = self._find_image_urls(keywords, n=1) or self._find_image_urls(config.PIXABAY_FALLBACK_KEYWORDS, n=1)
        if not urls:
            raise RuntimeError(f"No Pixabay results for '{keywords}' or fallback query")

        resp = requests.get(urls[0], timeout=30)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
        return output_path

    def download_candidates(self, keywords: str, output_dir: str, n: int = 5,
                             filename_prefix: str = "bg_candidate") -> list:
        """Downloads up to n distinct candidate images for the given
        keywords, so a downstream step (Gemini vetting) can pick the best/
        most compliant one instead of blindly using a random single result.
        Returns a list of local file paths (may be shorter than n if
        Pixabay has fewer matches)."""
        urls = self._find_image_urls(keywords, n=n)
        if not urls:
            return []

        paths = []
        for idx, url in enumerate(urls):
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                path = f"{output_dir}/{filename_prefix}_{idx}.jpg"
                with open(path, "wb") as f:
                    f.write(resp.content)
                paths.append(path)
            except requests.RequestException as e:
                print(f"⚠️ Failed downloading candidate image {idx} for '{keywords}': {e}")
                continue
        return paths

    def _find_image_urls(self, query: str, n: int = 5) -> list:
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
            return []
        pool = hits[: max(n * 2, 10)]
        random.shuffle(pool)
        chosen = pool[:n]
        return [h.get("largeImageURL") or h.get("webformatURL") for h in chosen if h.get("largeImageURL") or h.get("webformatURL")]
