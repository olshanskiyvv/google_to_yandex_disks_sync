import re
from urllib.parse import unquote


def parse_google_folder_url(url_or_id: str) -> str:
    """
    Парсит URL папки Google Drive или возвращает ID как есть.

    Поддерживаемые форматы:
    - https://drive.google.com/drive/folders/xxx
    - https://drive.google.com/drive/u/0/folders/xxx
    - https://drive.google.com/open?id=xxx
    - xxx (только ID)

    Raises:
        ValueError: если не удалось извлечь ID
    """
    if re.match(r"^[a-zA-Z0-9_-]{20,}$", url_or_id):
        return url_or_id

    patterns = [
        r"drive\.google\.com/drive/(?:u/\d+/)?folders/([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    raise ValueError(f"Не удалось извлечь folder_id из: {url_or_id}")


def parse_yandex_folder_url(url_or_path: str) -> str:
    """
    Парсит URL папки Яндекс Диск или возвращает путь как есть.
    Декодирует URL-encoded символы.

    Поддерживаемые форматы:
    - https://disk.yandex.ru/client/disk/path/to/folder
    - /path/to/folder (путь)

    Raises:
        ValueError: если не удалось извлечь путь
    """
    if url_or_path.startswith("/"):
        return unquote(url_or_path)

    pattern = r"disk\.yandex\.ru/client/disk(/.*)"
    match = re.search(pattern, url_or_path)

    if match:
        return unquote(match.group(1))

    raise ValueError(f"Не удалось извлечь путь из: {url_or_path}")
