import argparse
import asyncio
import sys

from config import load_config
from src.factories import get_registry
from src.logger import logger
from src.sync import SyncManager


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Синхронизация между хранилищами"
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="Путь к config.yaml (по умолчанию: config.yaml)",
    )
    parser.add_argument(
        "-p",
        "--pair",
        type=int,
        action="append",
        dest="pairs",
        help="Индекс пары для синхронизации (можно указать несколько)",
    )

    args = parser.parse_args()

    try:
        app_config = load_config(args.config)
    except FileNotFoundError as e:
        logger.error(f"Конфигурация не найдена: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        sys.exit(1)

    try:
        asyncio.run(_async_main(app_config, args))
    except KeyboardInterrupt:
        logger.info("Синхронизация прервана пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        raise


async def _async_main(app_config, args) -> None:
    # Регистрируем бэкенды
    from src.backends import google, local, yandex  # noqa: F401

    registry = get_registry()

    # Выбираем пары для синхронизации
    pairs_to_run = args.pairs if args.pairs is not None else range(len(app_config.sync_pairs))

    results = []

    for pair_index in pairs_to_run:
        if pair_index >= len(app_config.sync_pairs):
            logger.error(f"Пара {pair_index} не существует (всего {len(app_config.sync_pairs)})")
            continue

        pair = app_config.sync_pairs[pair_index]
        logger.info(f"\n=== Синхронизация пары {pair_index}: {pair.source} -> {pair.target} ===")

        try:
            source_folder = app_config.folders[pair.source]
            target_folder = app_config.folders[pair.target]
        except KeyError as e:
            logger.error(f"Папка не найдена: {e}")
            continue

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

        source_backend = factory.from_namespace(source_backend_config)
        target_backend = registry.get_factory(target_folder.backend).from_namespace(target_backend_config)

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
