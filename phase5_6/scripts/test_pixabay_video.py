"""Manual Pixabay Video API test.

Run:
    PIXABAY_API_KEY=xxx python phase5_6/scripts/test_pixabay_video.py "mountains nature"

PowerShell:
    $env:PIXABAY_API_KEY="xxx"; python phase5_6/scripts/test_pixabay_video.py "mountains nature"

Temporary files are intentionally kept for manual inspection.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PHASE_DIR = SCRIPT_DIR.parent
if str(PHASE_DIR) not in sys.path:
    sys.path.insert(0, str(PHASE_DIR))

from lib import pixabay_client as pixabay_module
from lib.pixabay_client import PixabayClient


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Usage: python phase5_6/scripts/test_pixabay_video.py "keywords"')
        return 2
    api_key = os.environ.get("PIXABAY_API_KEY")
    if not api_key:
        print("Missing environment variable: PIXABAY_API_KEY")
        return 2

    output_dir = tempfile.mkdtemp(prefix="pixabay_video_test_")
    original_get = pixabay_module.requests.get
    hits = []
    source_by_url = {}
    downloaded_urls = []

    def recording_get(url, *args, **kwargs):
        response = original_get(url, *args, **kwargs)
        if url == "https://pixabay.com/api/videos/":
            hits.extend(response.json().get("hits", []))
            for hit in hits:
                for data in (hit.get("videos") or {}).values():
                    if data.get("url"):
                        source_by_url[data["url"]] = data
        elif url in source_by_url:
            downloaded_urls.append(url)
        return response

    try:
        pixabay_module.requests.get = recording_get
        paths = PixabayClient(api_key).download_video_candidates(
            sys.argv[1], output_dir, n=5
        )
    finally:
        pixabay_module.requests.get = original_get

    passing = []
    for hit in hits:
        choices = [
            data for data in (hit.get("videos") or {}).values()
            if data.get("url")
            and int(data.get("height") or 0) >= 1080
            and int(data.get("width") or 0) < int(data.get("height") or 0)
        ]
        if choices:
            passing.append(max(choices, key=lambda item: int(item.get("height") or 0)))

    print(f"Keywords: {sys.argv[1]}")
    print(f"Total Pixabay hits before filtering: {len(hits)}")
    print(f"Videos passing resolution filter: {len(passing)}")
    if not paths:
        print("لا توجد نتائج بالدقة المطلوبة لهذه الكلمة")
    else:
        for index, path in enumerate(paths):
            url = downloaded_urls[index] if index < len(downloaded_urls) else "unknown"
            metadata = source_by_url.get(url, {})
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"Video {index + 1}:")
            print(f"  Local path: {path}")
            print(f"  Resolution: {metadata.get('width', 'unknown')}x{metadata.get('height', 'unknown')}")
            print(f"  Size: {size_mb:.2f} MB")
            print(f"  Source URL: {url}")
    print(f"Temporary directory (not deleted): {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

