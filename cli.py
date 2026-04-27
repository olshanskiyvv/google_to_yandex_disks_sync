import argparse
import asyncio
import sys

from config import load_config
from src.factories import get_registry
from src.logger import logger
from src.sync import SyncManager


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Синхронизация между хранилищами",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  cli.py                           # запустить все sync_pairs
  cli.py -c prod_config.yaml       # альтернативный config
  cli.py -s prod_sync.yaml        # альтернативный sync
  cli.py -c prod.yaml -s prod_sync.yaml
  cli.py --pair 0                  # запустить только первую пару
        """,
    )

    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="Путь к config.yaml (по умолчанию: config.yaml)",
    )
    parser.add_argument(
        "-s",
        "--sync",
        default="sync.yaml",
        help="Путь к sync.yaml (по умолчанию: sync.yaml)",
    )
    parser.add_argument(
        "-p",
        "--pair",
        type=int,
        action="append",
        dest="pairs",
        help="Индекс пары для синхронизации (можно указать несколько)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Показать что будет синхронизировано без реального запуска",
    )

    args = parser.parse_args()

    try:
        app_config = load_config(args.config, args.sync)
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
    # Регистрируем фабрики бэкендов
    _register_backends()

    # Выбираем пары для синхронизации
    pairs_to_run = args.pairs if args.pairs is not None else range(len(app_config.sync_pairs))

    for pair_index in pairs_to_run:
        if pair_index >= len(app_config.sync_pairs):
            logger.error(f"Пара {pair_index} не существует (всего {len(app_config.sync_pairs)})")
            continue

        pair = app_config.sync_pairs[pair_index]
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

        source_backend = _create_backend(source_folder.backend, source_backend_config)
        target_backend = _create_backend(target_folder.backend, target_backend_config)

        async with source_backend, target_backend:
            await source_backend.authenticator.authenticate()
            await target_backend.authenticator.authenticate()

            sync_manager = SyncManager(source=source_backend, destination=target_backend)
            await sync_manager.sync(
                source_folder=source_folder.path,
                dest_folder=target_folder.path,
            )


def _register_backends() -> None:
    """Register all available backend factories."""
    # Importing modules triggers @register_backend decorators
    from src.backends import google, local, yandex  # noqa: F401


def _create_backend(name: str, config: dict):
    """Create a backend instance from configuration."""
    registry = get_registry()
    factory = registry.get_factory(name)

    if not factory:
        raise ValueError(f"Неизвестный бэкенд: {name}")

    return factory.from_namespace(config)


if __name__ == "__main__":
    main()
