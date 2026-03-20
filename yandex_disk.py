import io
from datetime import datetime
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

    def list_files(self, folder: str) -> dict[str, dict[str, Any]]:
        if not self.client:
            raise RuntimeError("Клиент не авторизован")

        files = {}
        try:
            for item in self.client.listdir(folder):
                if item.type == "file":
                    files[item.name] = {
                        "name": item.name,
                        "modified": item.modified,
                        "size": item.size or 0,
                        "path": item.path,
                    }
        except yadisk.exceptions.PathNotFoundError:
            logger.warning(f"Папка {folder} не найдена на Яндекс Диск")

        logger.info(f"Найдено {len(files)} файлов на Яндекс Диск")
        return files

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
