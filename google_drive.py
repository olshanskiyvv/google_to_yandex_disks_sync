import io
from datetime import datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from config import config
from logger import logger

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class GoogleDriveClient:
    def __init__(self):
        self.service = None
        self.creds = None

    def authenticate(self) -> None:
        creds_path = Path(config.google_credentials_file)
        token_path = Path(config.google_token_file)

        if token_path.exists():
            self.creds = Credentials.from_authorized_user_file(
                str(token_path), SCOPES
            )

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not creds_path.exists():
                    raise FileNotFoundError(
                        f"Файл credentials не найден: {creds_path}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(creds_path), SCOPES
                )
                self.creds = flow.run_local_server(port=0)

            token_path.write_text(self.creds.to_json())

        self.service = build("drive", "v3", credentials=self.creds)
        logger.info("Успешная авторизация в Google Drive")

    def list_videos(self, folder_id: str) -> list[dict[str, Any]]:
        if not self.service:
            raise RuntimeError("Клиент не авторизован")

        videos = []
        query = (
            f"'{folder_id}' in parents and "
            f"mimeType contains 'video/' and "
            f"trashed = false"
        )

        page_token = None
        while True:
            results = (
                self.service.files()
                .list(
                    q=query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name, modifiedTime, size)",
                    pageToken=page_token,
                )
                .execute()
            )

            items = results.get("files", [])
            for item in items:
                videos.append({
                    "id": item["id"],
                    "name": item["name"],
                    "modified": datetime.fromisoformat(
                        item["modifiedTime"].replace("Z", "+00:00")
                    ),
                    "size": int(item.get("size", 0)),
                })

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        logger.info(f"Найдено {len(videos)} видео в Google Drive")
        return videos

    def download_file(self, file_id: str, file_name: str) -> io.BytesIO:
        if not self.service:
            raise RuntimeError("Клиент не авторизован")

        logger.info(f"Скачивание: {file_name}")

        request = self.service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logger.debug(f"Прогресс {file_name}: {progress}%")

        buffer.seek(0)
        return buffer
