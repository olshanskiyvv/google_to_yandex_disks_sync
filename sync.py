from typing import Any

from config import config
from google_drive import GoogleDriveClient
from logger import logger
from yandex_disk import YandexDiskClient


class SyncManager:
    def __init__(self):
        self.google_client = GoogleDriveClient()
        self.yandex_client = YandexDiskClient()
        self.stats = {
            "downloaded": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }

    def run(self) -> None:
        logger.info("=== Начало синхронизации ===")

        self.google_client.authenticate()
        self.yandex_client.authenticate()

        self.yandex_client.ensure_folder_exists(config.yandex_folder)

        google_files = self.google_client.list_videos(config.google_folder_id)
        yandex_files = self.yandex_client.list_files(config.yandex_folder)

        for g_file in google_files:
            self._sync_file(g_file, yandex_files)

        self._print_stats()

    def _sync_file(
        self, g_file: dict[str, Any], yandex_files: dict[str, dict[str, Any]]
    ) -> None:
        file_name = g_file["name"]
        remote_path = f"{config.yandex_folder.rstrip('/')}/{file_name}"

        if file_name not in yandex_files:
            self._download_and_upload(g_file, remote_path, is_update=False)
            self.stats["downloaded"] += 1
        else:
            y_file = yandex_files[file_name]
            if g_file["modified"] > y_file["modified"]:
                self._download_and_upload(g_file, remote_path, is_update=True)
                self.stats["updated"] += 1
            else:
                logger.info(f"Пропуск (актуален): {file_name}")
                self.stats["skipped"] += 1

    def _download_and_upload(
        self, g_file: dict[str, Any], remote_path: str, is_update: bool
    ) -> None:
        file_name = g_file["name"]
        action = "Обновление" if is_update else "Загрузка"

        try:
            buffer = self.google_client.download_file(g_file["id"], file_name)
            self.yandex_client.upload_file(buffer, remote_path, overwrite=is_update)
        except Exception as e:
            logger.error(f"Ошибка при {action.lower()} {file_name}: {e}")
            self.stats["errors"] += 1

    def _print_stats(self) -> None:
        logger.info("=== Результаты синхронизации ===")
        logger.info(f"Загружено новых: {self.stats['downloaded']}")
        logger.info(f"Обновлено: {self.stats['updated']}")
        logger.info(f"Пропущено: {self.stats['skipped']}")
        logger.info(f"Ошибок: {self.stats['errors']}")
        logger.info("=== Синхронизация завершена ===")
