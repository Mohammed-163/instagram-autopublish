"""
Google Drive wrapper (google-api-python-client).
Handles monthly folder creation, video upload, making files public,
and cleanup deletion.
"""
import json
import io

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

    def delete_file(self, file_id: str) -> None:
        self.service.files().delete(fileId=file_id).execute()

    def download_file(self, file_id: str, output_path: str) -> None:
        request = self.service.files().get_media(fileId=file_id)
        with open(output_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
