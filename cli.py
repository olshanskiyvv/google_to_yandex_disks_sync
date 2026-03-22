import argparse
import asyncio
import sys

from config import config
from src import SyncConfig, SyncManager
from src.logger import logger


def parse_folders(args) -> tuple[str, str]:
    """
    Извлекает и валидирует аргументы папок.

    Returns:
        tuple[str, str]: (google_folder, yandex_folder)

    Raises:
        SystemExit: при ошибке валидации
    """
    google_folder = None
    yandex_folder = None
    google_source = None
    yandex_source = None

    if args.folders:
        if len(args.folders) == 1:
            logger.error("Ошибка: укажите оба позиционных аргумента")
            logger.error("Пример: cli.py GOOGLE_FOLDER YANDEX_FOLDER")
            sys.exit(1)
        if len(args.folders) >= 2:
            google_folder = args.folders[0]
            yandex_folder = args.folders[1]
            google_source = "positional"
            yandex_source = "positional"

    if args.google_folder:
        if google_source == "positional":
            logger.error(
                "Ошибка: GOOGLE_FOLDER указан дважды (позиционный и --google-folder)"
            )
            sys.exit(1)
        google_folder = args.google_folder
        google_source = "named"

    if args.yandex_folder:
        if yandex_source == "positional":
            logger.error(
                "Ошибка: YANDEX_FOLDER указан дважды (позиционный и --yandex-folder)"
            )
            sys.exit(1)
        yandex_folder = args.yandex_folder
        yandex_source = "named"

    if not google_folder:
        logger.error("Ошибка: GOOGLE_FOLDER не указан")
        logger.error("Используйте позиционный аргумент или --google-folder")
        sys.exit(1)

    if not yandex_folder:
        logger.error("Ошибка: YANDEX_FOLDER не указан")
        logger.error("Используйте позиционный аргумент или --yandex-folder")
        sys.exit(1)

    return google_folder, yandex_folder


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Синхронизация Google Drive → Яндекс Диск",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  cli.py "https://drive.google.com/drive/folders/xxx" "/backup/videos"
  cli.py --google-folder "1ABC123xyz" --yandex-folder "/backup/videos"
  cli.py "google_folder" --yandex-folder "/backup/videos"
  cli.py --google-folder "google_folder" "yandex_folder"
        """,
    )

    parser.add_argument(
        "folders",
        nargs="*",
        metavar="FOLDER",
        help="GOOGLE_FOLDER YANDEX_FOLDER (позиционные)",
    )

    parser.add_argument(
        "-g",
        "--google-folder",
        metavar="FOLDER",
        help="URL или ID папки Google Drive",
    )
    parser.add_argument(
        "-y",
        "--yandex-folder",
        metavar="FOLDER",
        help="URL или путь к папке Яндекс Диск",
    )
    parser.add_argument(
        "--manual-oauth",
        action="store_true",
        help="Ручной ввод кода авторизации Google",
    )

    args = parser.parse_args()

    google_folder, yandex_folder = parse_folders(args)

    try:
        asyncio.run(
            _async_main(
                google_folder=google_folder,
                yandex_folder=yandex_folder,
                use_auto_oauth=not args.manual_oauth,
            )
        )
    except FileNotFoundError as e:
        logger.error(f"Файл не найден: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Синхронизация прервана пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        raise


async def _async_main(
    google_folder: str,
    yandex_folder: str,
    use_auto_oauth: bool = True,
) -> None:
    sync_config = SyncConfig(
        google_credentials_file=config.google_credentials_file,
        google_token_file=config.google_token_file,
        google_use_auto_oauth=use_auto_oauth,
        yandex_token=config.yandex_token,
    )

    sync_manager = SyncManager(sync_config)
    await sync_manager.sync(
        google_folder=google_folder,
        yandex_folder=yandex_folder,
    )


if __name__ == "__main__":
    main()
