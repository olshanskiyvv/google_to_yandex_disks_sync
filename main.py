import asyncio
import sys

from config import load_config
from src.factories import get_registry
from src.logger import logger
from src.sync import SyncManager


def main() -> None:
    try:
        app_config = load_config()
    except FileNotFoundError as e:
        logger.error(f"Конфигурация не найдена: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        sys.exit(1)

    try:
        asyncio.run(_async_main(app_config))
    except KeyboardInterrupt:
        logger.info("Синхронизация прервана пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        raise


async def _async_main(app_config) -> None:
    # Регистрируем бэкенды
    from src.backends import google, local, yandex  # noqa: F401

    registry = get_registry()

    results = []

    for pair_index, pair in enumerate(app_config.sync_pairs):
        source_folder = pair.source
        target_folder = pair.target
        logger.info(f"\n=== Синхронизация пары {pair_index}: {source_folder.backend}:{source_folder.path} -> {target_folder.backend}:{target_folder.path} ===")

        source_backend_config = app_config.backends.get(source_folder.backend)
        target_backend_config = app_config.backends.get(target_folder.backend)

        if not source_backend_config:
            logger.error(f"Бэкенд '{source_folder.backend}' не найден в конфигурации")
            continue
        if not target_backend_config:
            logger.error(f"Бэкенд '{target_folder.backend}' не найден в конфигурации")
            continue

        factory = registry.get_factory(source_folder.backend)
        if not factory:
            logger.error(f"Неизвестный бэкенд: {source_folder.backend}")
            continue

        target_factory = registry.get_factory(target_folder.backend)
        if not target_factory:
            logger.error(f"Неизвестный бэкенд: {target_folder.backend}")
            continue

        source_backend = factory.from_namespace(source_backend_config)
        target_backend = target_factory.from_namespace(target_backend_config)

        async with source_backend, target_backend:
            await source_backend.authenticator.authenticate()
            await target_backend.authenticator.authenticate()

            sync_manager = SyncManager(source=source_backend, destination=target_backend)
            result = await sync_manager.sync(
                source_folder=source_folder.path,
                dest_folder=target_folder.path,
            )
            results.append(result)

    _print_summary(results)


def _print_summary(results) -> None:
    if not results:
        return

    total_downloaded = 0
    total_updated = 0
    total_skipped = 0
    total_errors = 0
    error_pairs = 0

    logger.info("")
    logger.info("=" * 60)
    logger.info("=== Итоговая статистика ===")
    logger.info("=" * 60)

    for i, result in enumerate(results, 1):
        stats = result.pair_stats

        if result.success:
            status = "✓"
            details = []
            if stats.downloaded:
                details.append(f"{stats.downloaded} загружено")
            if stats.updated:
                details.append(f"{stats.updated} обновлено")
            if stats.skipped:
                details.append(f"{stats.skipped} пропущено")
            detail_str = ", ".join(details) if details else "нет изменений"
            line = f"Пара {i}: {stats.source_id} → {stats.target_path} | {status} {detail_str}"
        else:
            status = "✗"
            error_msg = result.error or "Неизвестная ошибка"
            line = f"Пара {i}: {stats.source_id} → {stats.target_path} | {status} Ошибка: {error_msg}"
            error_pairs += 1

        logger.info(line)

        total_downloaded += stats.downloaded
        total_updated += stats.updated
        total_skipped += stats.skipped
        total_errors += stats.errors

    logger.info("")
    logger.info("Всего:")
    logger.info(f"  Загружено: {total_downloaded}")
    logger.info(f"  Обновлено: {total_updated}")
    logger.info(f"  Пропущено: {total_skipped}")
    if total_errors or error_pairs:
        logger.info(f"  Ошибок: {total_errors} (в {error_pairs} парах)")
    else:
        logger.info("  Ошибок: 0")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
