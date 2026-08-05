"""
Google Drive wrapper (google-api-python-client).
Handles monthly folder creation, video upload, making files public,
and cleanup deletion.
"""
import json
import io
import time

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive"]


class DriveClient:
    def __init__(self, service_account_json: str, root_folder_id: str):
        info = json.loads(service_account_json)
        creds = Credentials.from_authorized_user_info(info, scopes=SCOPES)
        self.service = build("drive", "v3", credentials=creds)
        self.root_folder_id = root_folder_id

    def get_or_create_month_folder(self, month_label: str) -> str:
        """month_label e.g. '2026-07'. Returns folder ID, creating it if needed."""
        query = (
            f"'{self.root_folder_id}' in parents and "
            f"name = '{month_label}' and "
            f"mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        if files:
            return files[0]["id"]

        metadata = {
            "name": month_label,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [self.root_folder_id],
        }
        folder = self.service.files().create(body=metadata, fields="id").execute()
        return folder["id"]

    def upload_video(self, local_path: str, filename: str, parent_folder_id: str) -> str:
        metadata = {"name": filename, "parents": [parent_folder_id]}
        media = MediaFileUpload(local_path, mimetype="video/mp4", resumable=True)
        file = self.service.files().create(body=metadata, media_body=media, fields="id").execute()
        return file["id"]

    def upload_image(self, local_path: str, filename: str, parent_folder_id: str) -> str:
        metadata = {"name": filename, "parents": [parent_folder_id]}
        media = MediaFileUpload(local_path, mimetype="image/jpeg", resumable=True)
        file = self.service.files().create(body=metadata, media_body=media, fields="id").execute()
        return file["id"]

    def upload_json(self, data: dict, filename: str, parent_folder_id: str) -> str:
        metadata = {"name": filename, "parents": [parent_folder_id]}
        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/json")
        file = self.service.files().create(body=metadata, media_body=media, fields="id").execute()
        return file["id"]

    def make_public(self, file_id: str) -> None:
        permission = {"type": "anyone", "role": "reader"}
        self.service.permissions().create(fileId=file_id, body=permission).execute()

    def get_public_download_url(self, file_id: str) -> str:
        # Direct-download form; more reliable than the /view URL for external fetchers.
        return f"https://drive.google.com/uc?id={file_id}&export=download"

    def verify_video_link_ready(self, url: str, max_attempts: int = 6, delay_seconds: int = 5) -> bool:
        """Confirms the public Drive link actually serves video bytes before
        we hand it to Instagram. Two known failure modes this catches:
          1. Drive shows an HTML "can't scan this file for viruses" warning
             page instead of the file for some larger files - Instagram's
             fetcher would just choke on that HTML with a confusing error.
          2. Permission propagation lag right after make_public() - retries
             with a short backoff instead of failing on the very first check.
        Returns True once a video/* content-type is observed, False if it
        never resolves to one within max_attempts.
        """
        import requests

        for attempt in range(max_attempts):
            try:
                resp = requests.get(url, stream=True, timeout=20, allow_redirects=True)
                content_type = resp.headers.get("Content-Type", "")
                resp.close()
                if content_type.startswith("video/"):
                    return True
                if "text/html" in content_type:
                    # Likely the virus-scan warning interstitial - wait for
                    # propagation, or (rare) a truly stuck state.
                    time.sleep(delay_seconds)
                    continue
            except requests.RequestException:
                time.sleep(delay_seconds)
                continue
        return False

    def find_file_id_by_name(self, filename: str, parent_folder_id: str) -> str | None:
        """Returns the file ID of the first file matching this exact name inside
        the given folder, or None if not found."""
        safe_name = filename.replace("'", "\\'")
        query = (
            f"name = '{safe_name}' and '{parent_folder_id}' in parents and trashed = false"
        )
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        return files[0]["id"] if files else None

    def download_json(self, filename: str, parent_folder_id: str) -> dict | None:
        """Finds and parses a JSON file by name inside a folder. Returns None
        if the file doesn't exist (e.g. Manus hasn't uploaded it yet this month)."""
        file_id = self.find_file_id_by_name(filename, parent_folder_id)
        if not file_id:
            return None
        buf = io.BytesIO()
        request = self.service.files().get_media(fileId=file_id)
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return json.loads(buf.getvalue().decode("utf-8"))

    def delete_file(self, file_id: str) -> None:
        self.service.files().delete(fileId=file_id).execute()

    def download_file(self, file_id: str, output_path: str) -> None:
        request = self.service.files().get_media(fileId=file_id)
        with open(output_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
