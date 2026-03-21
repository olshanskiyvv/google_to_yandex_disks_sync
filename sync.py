import asyncio
from dataclasses import dataclass
from typing import Any

from google_drive import GoogleDriveClient
from logger import logger
from url_parser import parse_google_folder_url, parse_yandex_folder_url
from yandex_disk import YandexDiskClient

MAX_RETRIES = 2
RETRY_DELAY = 5


@dataclass
class SyncConfig:
    google_credentials_file: str
    google_token_file: str
    google_use_auto_oauth: bool
    yandex_token: str


class SyncManager:
    def __init__(self, config: SyncConfig):
        self.config = config
        self.google_client: GoogleDriveClient | None = None
        self.yandex_client: YandexDiskClient | None = None
        self.semaphore = asyncio.Semaphore(5)
        self.stats = {
            "downloaded": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }
        self.stats_lock = asyncio.Lock()
        self._yandex_folder: str = ""

    async def sync(self, google_folder: str, yandex_folder: str) -> None:
        """
        Синхронизация папок.

        Args:
            google_folder: URL папки Google Drive или ID папки
            yandex_folder: URL папки Яндекс Диск или путь к папке
        """
        logger.info("=== Начало синхронизации ===")

        google_folder_id = parse_google_folder_url(google_folder)
        yandex_folder_path = parse_yandex_folder_url(yandex_folder)

        self._yandex_folder = yandex_folder_path

        async with (
            GoogleDriveClient(
                credentials_file=self.config.google_credentials_file,
                token_file=self.config.google_token_file,
                use_auto_oauth=self.config.google_use_auto_oauth,
            ) as google,
            YandexDiskClient(token=self.config.yandex_token) as yandex,
        ):
            self.google_client = google
            self.yandex_client = yandex

            await self.google_client.authenticate()
            await self.yandex_client.authenticate()

            await self.yandex_client.ensure_folder_exists(yandex_folder_path)

            google_files = await self.google_client.list_files(google_folder_id)
            yandex_files = await self.yandex_client.list_files(yandex_folder_path)

            tasks = [
                self._sync_file_limited(g_file, yandex_files) for g_file in google_files
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

        self._print_stats()

    async def _sync_file_limited(
        self, g_file: dict[str, Any], yandex_files: dict[str, dict[str, Any]]
    ) -> None:
        async with self.semaphore:
            await self._sync_file(g_file, yandex_files)

    async def _sync_file(
        self, g_file: dict[str, Any], yandex_files: dict[str, dict[str, Any]]
    ) -> None:
        file_path = g_file["path"]
        remote_path = f"{self._yandex_folder.rstrip('/')}/{file_path}"

        if file_path not in yandex_files:
            success = await self._download_and_upload(
                g_file, remote_path, is_update=False
            )
            async with self.stats_lock:
                if success:
                    self.stats["downloaded"] += 1
                else:
                    self.stats["errors"] += 1
        else:
            y_file = yandex_files[file_path]
            if g_file["modified"] > y_file["modified"]:
                success = await self._download_and_upload(
                    g_file, remote_path, is_update=True
                )
                async with self.stats_lock:
                    if success:
                        self.stats["updated"] += 1
                    else:
                        self.stats["errors"] += 1
            else:
                logger.info(f"Пропуск (актуален): {file_path}")
                async with self.stats_lock:
                    self.stats["skipped"] += 1

    async def _download_and_upload(
        self, g_file: dict[str, Any], remote_path: str, is_update: bool
    ) -> bool:
        if not self.google_client or not self.yandex_client:
            logger.error("Клиенты не инициализированы")
            return False

        file_path = g_file["path"]
        action = "Обновление" if is_update else "Загрузка"

        for attempt in range(MAX_RETRIES):
            try:
                await self.yandex_client.ensure_parent_folders(remote_path)
                stream = self.google_client.download_stream(g_file["id"], file_path)
                await self.yandex_client.upload_stream(
                    stream, remote_path, overwrite=is_update
                )
                return True
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e) if str(e) else repr(e)

                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"Ошибка при {action.lower()} {file_path}: {error_type}: {error_msg}, "
                        f"повторная попытка через {RETRY_DELAY}с"
                    )
                    await asyncio.sleep(RETRY_DELAY)
                    continue

                logger.error(
                    f"Ошибка при {action.lower()} {file_path}: {error_type}: {error_msg}"
                )

                if await self._check_file_uploaded(remote_path):
                    logger.warning(f"Файл загружен несмотря на ошибку: {file_path}")
                    return True

                return False

        return False

    async def _check_file_uploaded(self, remote_path: str) -> bool:
        if not self.yandex_client:
            return False

        try:
            return await self.yandex_client.file_exists(remote_path)
        except Exception:
            return False

    def _print_stats(self) -> None:
        logger.info("=== Результаты синхронизации ===")
        logger.info(f"Загружено новых: {self.stats['downloaded']}")
        logger.info(f"Обновлено: {self.stats['updated']}")
        logger.info(f"Пропущено: {self.stats['skipped']}")
        logger.info(f"Ошибок: {self.stats['errors']}")
        logger.info("=== Синхронизация завершена ===")
