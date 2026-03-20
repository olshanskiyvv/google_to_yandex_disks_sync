from typing import Any, AsyncIterator

import yadisk

from config import config
from logger import logger


class YandexDiskClient:
    def __init__(self):
        self.client: yadisk.AsyncClient | None = None

    async def __aenter__(self) -> "YandexDiskClient":
        if not config.yandex_token:
            raise ValueError("YANDEX_TOKEN не указан в .env")

        self.client = yadisk.AsyncClient(token=config.yandex_token)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self.client:
            await self.client.close()

    async def authenticate(self) -> None:
        if not self.client:
            raise RuntimeError("Клиент не инициализирован")

        if not await self.client.check_token():
            raise ValueError("Неверный токен Яндекс Диск")

        logger.info("Успешная авторизация в Яндекс Диск")

    async def ensure_folder_exists(self, folder: str) -> None:
        if not self.client:
            raise RuntimeError("Клиент не авторизован")

        if not await self.client.exists(folder):
            logger.info(f"Создание папки: {folder}")
            await self.client.mkdir(folder)

    async def ensure_parent_folders(self, remote_path: str) -> None:
        if not self.client:
            raise RuntimeError("Клиент не авторизован")

        parts = [p for p in remote_path.rstrip("/").split("/")[:-1] if p]
        current_path = ""

        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else f"/{part}"
            if not await self.client.exists(current_path):
                logger.info(f"Создание папки: {current_path}")
                await self.client.mkdir(current_path)

    async def list_files(self, folder: str) -> dict[str, dict[str, Any]]:
        if not self.client:
            raise RuntimeError("Клиент не авторизован")

        files: dict[str, dict[str, Any]] = {}
        try:
            await self._list_files_recursive(folder, "", files)
        except yadisk.exceptions.PathNotFoundError:
            logger.warning(f"Папка {folder} не найдена на Яндекс Диск")

        logger.info(f"Найдено {len(files)} файлов на Яндекс Диск")
        return files

    async def _list_files_recursive(
        self, folder: str, base_path: str, files: dict[str, dict[str, Any]]
    ) -> None:
        if not self.client:
            raise RuntimeError("Клиент не авторизован")

        async for item in self.client.listdir(folder):
            item_name = item.name or ""
            item_path = f"{base_path}/{item_name}" if base_path else item_name

            if item.type == "dir" and item.path:
                await self._list_files_recursive(item.path, item_path, files)
            elif item.type == "file" and item_path:
                files[item_path] = {
                    "name": item_name,
                    "path": item_path,
                    "modified": item.modified,
                    "size": item.size or 0,
                    "full_path": item.path or "",
                }

    async def upload_stream(
        self,
        source: AsyncIterator[bytes],
        remote_path: str,
        overwrite: bool = False,
    ) -> None:
        if not self.client:
            raise RuntimeError("Клиент не авторизован")

        logger.info(f"Загрузка: {remote_path}")

        async def stream_generator() -> AsyncIterator[bytes]:
            async for chunk in source:
                yield chunk

        await self.client.upload(
            stream_generator,
            remote_path,
            overwrite=overwrite,
        )

        logger.info(f"Файл успешно загружен: {remote_path}")

    async def delete_file(self, remote_path: str) -> None:
        if not self.client:
            raise RuntimeError("Клиент не авторизован")

        logger.info(f"Удаление: {remote_path}")
        await self.client.remove(remote_path)

    async def file_exists(self, remote_path: str) -> bool:
        if not self.client:
            return False

        return await self.client.exists(remote_path)
