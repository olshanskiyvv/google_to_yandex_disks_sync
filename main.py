import argparse
import asyncio

from config import config
from src import PairStats, SyncConfig, SyncManager, SyncResult
from src.logger import logger

SYNC_PAIRS: list[tuple[str, str]] = [
    (config.google_folder, config.yandex_folder)
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Синхронизация Google Drive → Яндекс Диск (через .env)"
    )
    parser.add_argument(
        "--manual-oauth",
        action="store_true",
        help="Ручной ввод кода авторизации Google",
    )
    args = parser.parse_args()

    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(error)
        logger.error(
            "Заполните .env или используйте cli.py для передачи аргументов"
        )
        return

    try:
        asyncio.run(_async_main(use_auto_oauth=not args.manual_oauth))
    except FileNotFoundError as e:
        logger.error(f"Файл не найден: {e}")
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
    except KeyboardInterrupt:
        logger.info("Синхронизация прервана пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        raise


async def _async_main(use_auto_oauth: bool = True) -> None:
    sync_config = SyncConfig(
        google_credentials_file=config.google_credentials_file,
        google_token_file=config.google_token_file,
        google_use_auto_oauth=use_auto_oauth,
        yandex_token=config.yandex_token,
    )

    if not SYNC_PAIRS:
        logger.error(
            "Нет пар для синхронизации. Заполните SYNC_PAIRS или .env"
        )
        return

    sync_manager = SyncManager(sync_config)
    results: list[SyncResult] = []

    for i, (google_folder, yandex_folder) in enumerate(SYNC_PAIRS, 1):
        logger.info("=" * 60)
        logger.info(f"[{i}/{len(SYNC_PAIRS)}] Обработка пары")
        logger.info("=" * 60)

        result = await sync_manager.sync(
            google_folder=google_folder,
            yandex_folder=yandex_folder,
        )
        results.append(result)

    _print_summary(results)


def _print_summary(results: list[SyncResult]) -> None:
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
        stats: PairStats = result.pair_stats
        google_id = stats.google_id or "?"
        yandex_path = stats.yandex_path or "?"

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
            line = f"Пара {i}: {google_id} → {yandex_path} | {status} {detail_str}"
        else:
            status = "✗"
            error_msg = result.error or "Неизвестная ошибка"
            line = f"Пара {i}: {google_id} → {yandex_path} | {status} Ошибка: {error_msg}"
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
