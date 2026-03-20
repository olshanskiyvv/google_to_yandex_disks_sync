import io
from typing import Any

import yadisk

from config import config
from logger import logger


class YandexDiskClient:
    def __init__(self):
        self.client: yadisk.Client | None = None

    def authenticate(self) -> None:
        if not config.yandex_token:
            raise ValueError("YANDEX_TOKEN не указан в .env")

        self.client = yadisk.Client(token=config.yandex_token)

        if not self.client.check_token():
            raise ValueError("Неверный токен Яндекс Диск")

        logger.info("Успешная авторизация в Яндекс Диск")

    def ensure_folder_exists(self, folder: str) -> None:
        if not self.client:
            raise RuntimeError("Клиент не авторизован")

        if not self.client.exists(folder):
            logger.info(f"Создание папки: {folder}")
            self.client.mkdir(folder)

    def ensure_parent_folders(self, remote_path: str) -> None:
        if not self.client:
            raise RuntimeError("Клиент не авторизован")

        parts = [p for p in remote_path.rstrip("/").split("/")[:-1] if p]
        current_path = ""

        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else f"/{part}"
            if not self.client.exists(current_path):
                logger.info(f"Создание папки: {current_path}")
                self.client.mkdir(current_path)

    def list_files(self, folder: str) -> dict[str, dict[str, Any]]:
        if not self.client:
            raise RuntimeError("Клиент не авторизован")

        files = {}
        try:
            self._list_files_recursive(folder, "", files)
        except yadisk.exceptions.PathNotFoundError:
            logger.warning(f"Папка {folder} не найдена на Яндекс Диск")

        logger.info(f"Найдено {len(files)} файлов на Яндекс Диск")
        return files

    def _list_files_recursive(
        self, folder: str, base_path: str, files: dict[str, dict[str, Any]]
    ) -> None:
        if not self.client:
            raise RuntimeError("Клиент не авторизован")

        for item in self.client.listdir(folder):
            item_name = item.name or ""
            item_path = f"{base_path}/{item_name}" if base_path else item_name

            if item.type == "dir" and item.path:
                self._list_files_recursive(item.path, item_path, files)
            elif item.type == "file" and item_path:
                files[item_path] = {
                    "name": item_name,
                    "path": item_path,
                    "modified": item.modified,
                    "size": item.size or 0,
                    "full_path": item.path or "",
                }

    def upload_file(
        self, file_buffer: io.BytesIO, remote_path: str, overwrite: bool = False
    ) -> None:
        if not self.client:
            raise RuntimeError("Клиент не авторизован")

        logger.info(f"Загрузка: {remote_path}")

        self.client.upload(
            file_buffer,
            remote_path,
            overwrite=overwrite,
        )

        logger.info(f"Файл успешно загружен: {remote_path}")

    def delete_file(self, remote_path: str) -> None:
        if not self.client:
            raise RuntimeError("Клиент не авторизован")

        logger.info(f"Удаление: {remote_path}")
        self.client.remove(remote_path)
