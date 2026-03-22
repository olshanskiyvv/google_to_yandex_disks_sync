import argparse
import asyncio
import json
from pathlib import Path

from config import config
from src import PairStats, SyncConfig, SyncManager, SyncResult
from src.logger import logger

DEFAULT_PAIRS_FILE = "sync_pairs.json"


def _load_pairs(file_path: str) -> list[tuple[str, str]]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON должен содержать массив объектов")

    if not data:
        raise ValueError("Массив пар пуст")

    pairs: list[tuple[str, str]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Элемент {i + 1} должен быть объектом")

        if "google" not in item or not isinstance(item["google"], str): # type: ignore
            raise ValueError(f"Элемент {i + 1} должен содержать ключ 'google' со строковым значением")
        if "yandex" not in item or not isinstance(item["yandex"], str): # type: ignore
            raise ValueError(f"Элемент {i + 1} должен содержать ключ 'yandex' со строковым значением")

        google, yandex = item["google"], item["yandex"] # type: ignore

        if not isinstance(google, str):
            raise ValueError(
                f"Элемент {i + 1}: ключ 'google' должен быть строкой"
            )
        if not isinstance(yandex, str):
            raise ValueError(
                f"Элемент {i + 1}: ключ 'yandex' должен быть строкой"
            )

        pairs.append((google, yandex))

    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Синхронизация Google Drive → Яндекс Диск (через JSON файл)"
    )
    parser.add_argument(
        "pairs_file",
        nargs="?",
        default=DEFAULT_PAIRS_FILE,
        help=f"Путь к JSON файлу с парами (по умолчанию: {DEFAULT_PAIRS_FILE})",
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
        logger.error("Заполните .env")
        return

    try:
        pairs = _load_pairs(args.pairs_file)
        logger.info(f"Загружено {len(pairs)} пар из {args.pairs_file}")
    except FileNotFoundError as e:
        logger.error(str(e))
        return
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return
    except ValueError as e:
        logger.error(str(e))
        return

    try:
        asyncio.run(
            _async_main(pairs=pairs, use_auto_oauth=not args.manual_oauth)
        )
    except FileNotFoundError as e:
        logger.error(f"Файл не найден: {e}")
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
    except KeyboardInterrupt:
        logger.info("Синхронизация прервана пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        raise


async def _async_main(
        pairs: list[tuple[str, str]], use_auto_oauth: bool = True
) -> None:
    sync_config = SyncConfig(
        google_credentials_file=config.google_credentials_file,
        google_token_file=config.google_token_file,
        google_use_auto_oauth=use_auto_oauth,
        yandex_token=config.yandex_token,
    )

    sync_manager = SyncManager(sync_config)
    results: list[SyncResult] = []

    for i, (google_folder, yandex_folder) in enumerate(pairs, 1):
        logger.info("=" * 60)
        logger.info(f"[{i}/{len(pairs)}] Обработка пары")
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
