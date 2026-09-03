"""
Pixabay API wrapper — downloads a background image matching given keywords.
"""
import random
import os
import subprocess

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

    def download_video_candidates(
        self,
        keywords: str,
        output_dir: str,
        n: int = 5,
        filename_prefix: str = "bg_video_candidate",
    ) -> list:
        """Download up to n original, vertical Pixabay videos at >=1080p."""
        resp = requests.get(
            "https://pixabay.com/api/videos/",
            params={
                "key": self.api_key,
                "q": keywords,
                "video_type": "film",
                "safesearch": "true",
                "per_page": 20,
            },
            timeout=20,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        random.shuffle(hits)
        selected_urls = []
        for hit in hits:
            sizes = hit.get("videos") or {}
            matching = [
                data for data in sizes.values()
                if data.get("url")
                and int(data.get("height") or 0) >= config.MIN_VIDEO_HEIGHT_FOR_PUBLISH
                and int(data.get("width") or 0) < int(data.get("height") or 0)
            ]
            if not matching:
                continue
            best = max(matching, key=lambda data: int(data.get("height") or 0))
            selected_urls.append(best["url"])
            if len(selected_urls) >= n:
                break

        paths = []
        for idx, url in enumerate(selected_urls):
            path = os.path.join(output_dir, f"{filename_prefix}_{idx}.mp4")
            try:
                video = requests.get(url, timeout=60)
                video.raise_for_status()
                with open(path, "wb") as fh:
                    fh.write(video.content)
                paths.append(path)
            except requests.RequestException as exc:
                print(f"⚠️ Failed downloading video candidate {idx} for '{keywords}': {exc}")
        return paths

    def create_review_copy(self, video_path: str, output_path: str) -> str:
        """Create a 480p review copy while leaving the original untouched."""
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"scale=-2:{config.VIDEO_REVIEW_MAX_HEIGHT}",
            "-c:v", "libx264", "-c:a", "copy",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg review-copy failed: {result.stderr}")
        if not os.path.exists(output_path):
            raise RuntimeError(f"ffmpeg reported success but did not create {output_path}")
        return output_path

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
