import asyncio

from config import config
from logger import logger
from sync import SyncManager


def main() -> None:
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(error)
        logger.error(
            "Создайте .env файл на основе .env.example и заполните необходимые поля"
        )
        return

    try:
        asyncio.run(_async_main())
    except FileNotFoundError as e:
        logger.error(f"Файл не найден: {e}")
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
    except KeyboardInterrupt:
        logger.info("Синхронизация прервана пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        raise


async def _async_main() -> None:
    sync_manager = SyncManager()
    await sync_manager.run()


if __name__ == "__main__":
    main()
