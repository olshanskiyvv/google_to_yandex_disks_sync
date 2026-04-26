import asyncio

from src.logger import logger
from src.models import PairStats, SyncResult, SyncStats
from src.protocols import FileMetadata, StorageBackend

MAX_RETRIES = 2
RETRY_DELAY = 5


async def _retry(coro_func, max_retries: int, delay: float, label: str = "") -> None:
    """Повторяет coroutine при ошибке. Выбрасывает исключение после последней попытки."""
    last_exc: Exception = RuntimeError("no attempts made")
    for attempt in range(max_retries):
        try:
            await coro_func()
            return
        except Exception as e:
            last_exc = e
            if attempt < max_retries - 1:
                logger.warning(
                    f"Ошибка {label}: {type(e).__name__}: {e}, "
                    f"повторная попытка через {delay}с"
                )
                await asyncio.sleep(delay)
    raise last_exc


class SyncManager:
    def __init__(
        self,
        source: StorageBackend,
        destination: StorageBackend,
        semaphore_limit: int = 3,
    ):
        if source.reader is None:
            raise ValueError(f"Source backend '{source.name}' has no reader")
        if destination.writer is None:
            raise ValueError(f"Destination backend '{destination.name}' has no writer")

        self.source = source
        self.destination = destination
        self.semaphore = asyncio.Semaphore(semaphore_limit)
        self.stats_lock = asyncio.Lock()

    async def sync(self, source_folder: str, dest_folder: str) -> SyncResult:
        """
        Синхронизация папок между хранилищами.

        Args:
            source_folder: Папка источник
            dest_folder: Папка назначения

        Returns:
            SyncResult с результатами синхронизации
        """
        pair_stats = PairStats()
        pair_stats.source_id = source_folder
        pair_stats.target_path = dest_folder

        logger.info("=== Начало синхронизации ===")
        logger.info(f"  Источник: {self.source.name}:{source_folder}")
        logger.info(f"  Назначение: {self.destination.name}:{dest_folder}")

        stats = SyncStats()

        try:
            await self.destination.writer.ensure_folder_exists(dest_folder)

            source_files = await self._list_folder(self.source, source_folder)
            dest_files_list = await self._list_folder(self.destination, dest_folder)
            dest_files = {f.path: f for f in dest_files_list}

            tasks = [
                self._sync_file_limited(s_file, dest_files, dest_folder, stats)
                for s_file in source_files
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            error_type = type(e).__name__
            error_msg = f"{error_type}: {e}"
            logger.error(f"Ошибка синхронизации: {error_msg}")
            pair_stats.status = "error"
            return SyncResult(pair_stats=pair_stats, error=error_msg)

        pair_stats.downloaded = stats.downloaded
        pair_stats.updated = stats.updated
        pair_stats.skipped = stats.skipped
        pair_stats.errors = stats.errors
        pair_stats.status = "success"

        self._print_stats(stats)

        return SyncResult(pair_stats=pair_stats)

    async def _list_folder(
        self, backend: StorageBackend, folder: str
    ) -> list[FileMetadata]:
        """List files in folder using backend's list_folder method."""
        try:
            return await backend.list_folder(folder)
        except NotImplementedError:
            raise ValueError(f"Backend '{backend.name}' cannot list files")

    async def _sync_file_limited(
        self,
        s_file: FileMetadata,
        dest_files: dict[str, FileMetadata],
        dest_folder: str,
        stats: SyncStats,
    ) -> None:
        async with self.semaphore:
            await self._sync_file(s_file, dest_files, dest_folder, stats)

    async def _sync_file(
        self,
        s_file: FileMetadata,
        dest_files: dict[str, FileMetadata],
        dest_folder: str,
        stats: SyncStats,
    ) -> None:
        file_path = s_file.path
        remote_path = f"{dest_folder.rstrip('/')}/{file_path}"

        if file_path not in dest_files:
            success = await self._download_and_upload(s_file, remote_path, is_update=False)
            async with self.stats_lock:
                if success:
                    stats.downloaded += 1
                else:
                    stats.errors += 1
        else:
            d_file = dest_files[file_path]
            if s_file.modified > d_file.modified:
                success = await self._download_and_upload(s_file, remote_path, is_update=True)
                async with self.stats_lock:
                    if success:
                        stats.updated += 1
                    else:
                        stats.errors += 1
            else:
                logger.info(f"Пропуск (актуален): {file_path}")
                async with self.stats_lock:
                    stats.skipped += 1

    async def _download_and_upload(
        self, s_file: FileMetadata, remote_path: str, is_update: bool
    ) -> bool:
        file_path = s_file.path
        action = "обновление" if is_update else "загрузка"

        async def transfer() -> None:
            await self.destination.writer.ensure_parent_folders(remote_path)
            stream = self.source.reader.download_stream(s_file.id, file_path)
            await self.destination.writer.upload_stream(stream, remote_path, overwrite=is_update)

        try:
            await _retry(transfer, MAX_RETRIES, RETRY_DELAY, label=f"{action} {file_path}")
            return True
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e) if str(e) else repr(e)
            logger.error(f"Ошибка при {action} {file_path}: {error_type}: {error_msg}")

            if await self._check_file_uploaded(remote_path):
                logger.warning(f"Файл загружен несмотря на ошибку: {file_path}")
                return True

            return False

    async def _check_file_uploaded(self, remote_path: str) -> bool:
        try:
            return await self.destination.writer.file_exists(remote_path)
        except Exception:
            return False

    def _print_stats(self, stats: SyncStats) -> None:
        logger.info("=== Результаты синхронизации ===")
        logger.info(f"Загружено новых: {stats.downloaded}")
        logger.info(f"Обновлено: {stats.updated}")
        logger.info(f"Пропущено: {stats.skipped}")
        logger.info(f"Ошибок: {stats.errors}")
        logger.info("=== Синхронизация завершена ===")
