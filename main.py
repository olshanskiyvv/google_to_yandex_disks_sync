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
        sync_manager = SyncManager()
        sync_manager.run()
    except FileNotFoundError as e:
        logger.error(f"Файл не найден: {e}")
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        raise


if __name__ == "__main__":
    main()
