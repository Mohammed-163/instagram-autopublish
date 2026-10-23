"""
Instagram Graph API wrapper — direct publishing (no third-party agent).
Uses the container model: create container -> poll status -> publish.
Also handles token verification, exchange (renewal), and insights pulling.
"""
import time

import requests

from . import config


class InstagramAPIError(Exception):
    pass


class InstagramClient:
    def __init__(self, access_token: str, ig_business_id: str):
        self.access_token = access_token
        self.ig_business_id = ig_business_id
        self.base = config.GRAPH_API_BASE

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base}/{path}"
        params = kwargs.pop("params", {})
        params["access_token"] = self.access_token
        resp = requests.request(method, url, params=params, timeout=30, **kwargs)
        data = resp.json()
        if resp.status_code != 200 or "error" in data:
            raise InstagramAPIError(f"{resp.status_code}: {data}")
        return data

    # -- Publishing ---------------------------------------------------------
    def create_reel_container(self, video_url: str, caption: str) -> str:
        data = self._request(
            "POST", f"{self.ig_business_id}/media",
            params={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "share_to_feed": "true",
            },
        )
        return data["id"]

    def check_container_status(self, container_id: str) -> str:
        data = self._request("GET", container_id, params={"fields": "status_code"})
        return data.get("status_code", "UNKNOWN")

    def wait_for_container(self, container_id: str) -> None:
        for _ in range(config.CONTAINER_POLL_MAX_ATTEMPTS):
            status = self.check_container_status(container_id)
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise InstagramAPIError(f"Container {container_id} processing failed")
            time.sleep(config.CONTAINER_POLL_INTERVAL_SECONDS)
        raise InstagramAPIError(f"Container {container_id} timed out waiting for FINISHED status")

    def publish_container(self, container_id: str) -> str:
        data = self._request(
            "POST", f"{self.ig_business_id}/media_publish",
            params={"creation_id": container_id},
        )
        return data["id"]

    def publish_reel(self, video_url: str, caption: str) -> str:
        """Full flow: create container, wait, publish. Returns media ID."""
        container_id = self.create_reel_container(video_url, caption)
        self.wait_for_container(container_id)
        return self.publish_container(container_id)

    # -- Insights -------------------------------------------------------------
    def get_media_insights(self, media_id: str) -> dict:
        data = self._request(
            "GET", f"{media_id}/insights",
            params={"metric": "reach,saved,shares,likes,comments"},
        )
        result = {}
        for item in data.get("data", []):
            values = item.get("values", [])
            result[item["name"]] = values[0]["value"] if values else None
        return result

    def get_recent_media(self, limit: int = 30) -> list:
        data = self._request(
            "GET", f"{self.ig_business_id}/media",
            params={"fields": "id,caption,timestamp,media_type", "limit": limit},
        )
        return data.get("data", [])

    # -- Token management -------------------------------------------------------
    def verify_token(self) -> bool:
        try:
            self._request("GET", self.ig_business_id, params={"fields": "username"})
            return True
        except InstagramAPIError:
            return False

    @staticmethod
    def exchange_token(app_id: str, app_secret: str, current_token: str) -> str:
        """Exchange a long-lived token for a fresh 60-day one."""
        resp = requests.get(
            "https://graph.facebook.com/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": current_token,
            },
            timeout=30,
        )
        data = resp.json()
        if "access_token" not in data:
            raise InstagramAPIError(f"Token exchange failed: {data}")
        return data["access_token"]
