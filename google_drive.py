import json
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from logger import logger
from oauth_callback_server import OAuthServer

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
GOOGLE_API_BASE = "https://www.googleapis.com/drive/v3"


class GoogleDriveClient:
    def __init__(
        self,
        credentials_file: str = "credentials.json",
        token_file: str = "token.json",
        use_auto_oauth: bool = True,
    ):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.use_auto_oauth = use_auto_oauth
        self.http_client: httpx.AsyncClient | None = None
        self.client_id: str | None = None
        self.client_secret: str | None = None
        self.access_token: str | None = None
        self.refresh_token: str | None = None

    async def __aenter__(self) -> "GoogleDriveClient":
        self.http_client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self.http_client:
            await self.http_client.aclose()

    async def authenticate(self) -> None:
        self._load_credentials()

        if await self._try_load_token():
            logger.info("Успешная авторизация в Google Drive")
            return

        if self.use_auto_oauth:
            await self._oauth_flow_auto()
        else:
            await self._oauth_flow_manual()

        logger.info("Успешная авторизация в Google Drive")

    def _load_credentials(self) -> None:
        creds_path = Path(self.credentials_file)
        if not creds_path.exists():
            raise FileNotFoundError(f"Файл credentials не найден: {creds_path}")

        with open(creds_path) as f:
            data = json.load(f)

        installed = data.get("installed", {})
        self.client_id = installed.get("client_id")
        self.client_secret = installed.get("client_secret")

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "client_id или client_secret не найдены в credentials.json"
            )

    async def _try_load_token(self) -> bool:
        token_path = Path(self.token_file)
        if not token_path.exists():
            return False

        with open(token_path) as f:
            data = json.load(f)

        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")

        if await self._check_token_valid():
            return True

        if self.refresh_token:
            await self._refresh_access_token()
            self._save_token()
            return True

        return False

    async def _check_token_valid(self) -> bool:
        if not self.access_token or not self.http_client:
            return False

        try:
            response = await self.http_client.get(
                f"{GOOGLE_API_BASE}/about",
                params={"fields": "user"},
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            return response.status_code == 200
        except Exception:
            return False

    async def _refresh_access_token(self) -> None:
        if not self.http_client or not self.client_id or not self.client_secret:
            raise RuntimeError("Клиент не инициализирован")

        response = await self.http_client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
        )

        if response.status_code != 200:
            raise ValueError(f"Ошибка обновления токена: {response.text}")

        data = response.json()
        self.access_token = data["access_token"]

    async def _oauth_flow_auto(self) -> None:
        if not self.client_id:
            raise RuntimeError("client_id не загружен")

        server = OAuthServer()
        server.start()

        auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={self.client_id}&"
            f"redirect_uri={server.redirect_uri}&"
            "response_type=code&"
            f"scope={' '.join(SCOPES)}&"
            "access_type=offline&"
            "prompt=consent"
        )

        logger.info("Открываю браузер для авторизации...")
        logger.info(f"Если браузер не открылся, перейдите по ссылке:\n{auth_url}")

        webbrowser.open(auth_url)

        logger.info("Ожидаю авторизацию в браузере (таймаут: 2 минуты)...")

        code = await server.wait_for_code(120)

        await self._exchange_code_for_token(code, server.redirect_uri)
        self._save_token()

    async def _oauth_flow_manual(self) -> None:
        if not self.client_id:
            raise RuntimeError("client_id не загружен")

        auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={self.client_id}&"
            "redirect_uri=http://localhost&"
            "response_type=code&"
            f"scope={' '.join(SCOPES)}&"
            "access_type=offline&"
            "prompt=consent"
        )

        print("\n" + "=" * 70)
        print("Для авторизации откройте в браузере:")
        print(auth_url)
        print("=" * 70)
        print(
            "\nПосле авторизации вы будете перенаправлены на http://localhost?code=XXX"
        )
        print("Скопируйте параметр code из адресной строки\n")

        code = input("Введите код авторизации: ").strip()

        await self._exchange_code_for_token(code, "http://localhost")
        self._save_token()

    async def _exchange_code_for_token(
        self, code: str, redirect_uri: str = "http://localhost"
    ) -> None:
        if not self.http_client or not self.client_id or not self.client_secret:
            raise RuntimeError("Клиент не инициализирован")

        response = await self.http_client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )

        if response.status_code != 200:
            raise ValueError(f"Ошибка получения токена: {response.text}")

        data = response.json()
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token")

    def _save_token(self) -> None:
        token_path = Path(self.token_file)
        token_path.write_text(
            json.dumps(
                {
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                },
                indent=2,
            )
        )

    async def list_files(self, folder_id: str) -> list[dict[str, Any]]:
        if not self.access_token or not self.http_client:
            raise RuntimeError("Клиент не авторизован")

        files: list[dict[str, Any]] = []
        await self._list_files_recursive(folder_id, "", files)

        logger.info(f"Найдено {len(files)} файлов в Google Drive")
        return files

    async def _list_files_recursive(
        self, folder_id: str, base_path: str, files: list[dict[str, Any]]
    ) -> None:
        if not self.http_client or not self.access_token:
            raise RuntimeError("Клиент не авторизован")

        page_token: str | None = None

        while True:
            params = {
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                "pageSize": 100,
                "pageToken": page_token,
            }

            response = await self.http_client.get(
                f"{GOOGLE_API_BASE}/files",
                params=params,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            if response.status_code != 200:
                raise RuntimeError(f"Ошибка API Google Drive: {response.text}")

            data = response.json()
            items = data.get("files", [])

            for item in items:
                mime_type = item["mimeType"]
                item_name = item["name"]
                item_path = f"{base_path}/{item_name}" if base_path else item_name

                if mime_type == "application/vnd.google-apps.folder":
                    await self._list_files_recursive(item["id"], item_path, files)
                else:
                    modified_str = item.get("modifiedTime", "")
                    try:
                        modified = datetime.fromisoformat(
                            modified_str.replace("Z", "+00:00")
                        )
                    except ValueError:
                        modified = datetime.now(timezone.utc)

                    files.append(
                        {
                            "id": item["id"],
                            "name": item_name,
                            "path": item_path,
                            "modified": modified,
                            "size": int(item.get("size", 0)),
                        }
                    )

            page_token = data.get("nextPageToken")
            if not page_token:
                break

    async def download_stream(
        self, file_id: str, file_path: str
    ) -> AsyncIterator[bytes]:
        if not self.http_client or not self.access_token:
            raise RuntimeError("Клиент не авторизован")

        logger.info(f"Скачивание: {file_path}")

        url = f"{GOOGLE_API_BASE}/files/{file_id}"
        params = {"alt": "media"}
        headers = {"Authorization": f"Bearer {self.access_token}"}

        async with self.http_client.stream(
            "GET", url, params=params, headers=headers
        ) as response:
            if response.status_code != 200:
                raise RuntimeError(f"Ошибка скачивания файла: {response.status_code}")

            async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                yield chunk
