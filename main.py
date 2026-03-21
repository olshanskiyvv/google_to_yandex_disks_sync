import argparse
import asyncio

from config import config
from logger import logger
from sync import SyncConfig, SyncManager


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Синхронизация Google Drive → Яндекс Диск"
    )
    parser.add_argument(
        "--manual-oauth",
        action="store_true",
        help="Использовать ручной ввод кода авторизации Google (по умолчанию: автоматический)",
    )
    args = parser.parse_args()

    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(error)
        logger.error(
            "Создайте .env файл на основе .env.example и заполните необходимые поля"
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

    sync_manager = SyncManager(sync_config)
    await sync_manager.run(
        google_folder_id=config.google_folder_id,
        yandex_folder=config.yandex_folder,
    )


if __name__ == "__main__":
    main()
