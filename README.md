# Disks Sync

Синхронизация файлов с Google Drive на Яндекс Диск.

## Установка

Требуется Python 3.10+ и [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Настройка

### 1. Google Drive API

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com)
2. Создайте новый проект или выберите существующий
3. Включите **Google Drive API**:
   - Меню → APIs & Services → Library
   - Найдите "Google Drive API" → Enable
4. Создайте credentials:
   - APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: Desktop app
   - Скачайте JSON-файл и сохраните как `credentials.json` в папке проекта
5. Получите ID папки с видео:
   - Откройте папку на Google Drive
   - URL имеет вид `https://drive.google.com/drive/folders/FOLDER_ID`
   - Скопируйте `FOLDER_ID`
   - Если папка чужая — нажмите "Добавить на Мой диск"

### 2. Яндекс Диск

Получите OAuth токен:

1. Перейдите по ссылке:
   ```
   https://oauth.yandex.ru/authorize?response_type=token&client_id=1a6990aa636648ffb9edcd2d15f140c5
   ```
2. Разрешите доступ
3. Скопируйте токен из URL после `access_token=`

### 3. Конфигурация

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Заполните параметры:

```env
# Google Drive
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json

# Google folder (URL или ID папки)
GOOGLE_FOLDER=1ABC123xyz...

# Яндекс Диск
YANDEX_TOKEN=AQAAA...

# Яндекс folder (URL или путь к папке)
YANDEX_FOLDER=/backup/videos

# Логирование
LOG_FILE=sync.log
LOG_LEVEL=INFO
```

### 4. Указание папок для синхронизации

#### Google Drive

Параметр `GOOGLE_FOLDER` принимает:

1. **ID папки**:
   ```env
   GOOGLE_FOLDER=1ABC123xyz...
   ```
   ID можно найти в URL папки: `https://drive.google.com/drive/folders/1ABC123xyz...`

2. **Ссылку на папку**:
   ```env
   GOOGLE_FOLDER=https://drive.google.com/drive/folders/1ABC123xyz...
   ```
   Поддерживаемые форматы ссылок:
   - `https://drive.google.com/drive/folders/{id}`
   - `https://drive.google.com/drive/u/0/folders/{id}` (с номером аккаунта)
   - `https://drive.google.com/open?id={id}`

#### Яндекс Диск

Параметр `YANDEX_FOLDER` принимает:

1. **Путь к папке**:
   ```env
   YANDEX_FOLDER=/backup/videos
   ```
   Путь указывается с обычными пробелами (без URL-кодирования).

2. **Ссылку на папку**:
   ```env
   YANDEX_FOLDER=https://disk.yandex.ru/client/disk/backup/videos
   ```
   Ссылка должна быть персональной (открывается при переходе к папке в браузере).

## Запуск

```bash
# Автоматическая авторизация (по умолчанию)
uv run python main.py

# Ручной ввод кода авторизации Google
uv run python main.py --manual-oauth
```

При первом запуске автоматически откроется браузер для авторизации в Google. После успешной авторизации браузер покажет страницу с сообщением об успехе, а токен сохранится в `token.json`.

### CLI аргументы

| Аргумент | Описание |
|----------|----------|
| `--manual-oauth` | Использовать ручной ввод кода авторизации Google вместо автоматического открытия браузера |

## Как работает скрипт

1. Получает список файлов из указанной папки Google Drive (рекурсивно, включая вложенные папки)
2. Получает список файлов из папки на Яндекс Диск
3. Для каждого файла:
   - Если файла нет на Яндекс Диск → скачивает и загружает
   - Если файл есть и версия на Google новее → перезаписывает
   - Если файл актуален → пропускает
4. Загружает до 5 файлов параллельно
5. Выводит отчёт о синхронизации

## Логи

Логи записываются в файл `sync.log` и выводятся в консоль.

Уровень логирования настраивается через `LOG_LEVEL`:
- `DEBUG` — подробная информация
- `INFO` — основной процесс
- `WARNING` — предупреждения
- `ERROR` — ошибки

## Автоматизация

### Cron (Linux/macOS)

Запуск каждое воскресенье в 10:00:

```bash
crontab -e
```

```
0 10 * * 0 cd /path/to/disks_sync && /path/to/uv run python main.py
```

### Windows Task Scheduler

1. Откройте Task Scheduler
2. Create Basic Task
3. Trigger: Weekly
4. Action: Start program
   - Program: `path\to\uv.exe`
   - Arguments: `run python main.py`
   - Start in: `path\to\disks_sync`

## Структура проекта

```
disks_sync/
├── main.py                   # Точка входа
├── config.py                 # Загрузка настроек
├── sync.py                   # Логика синхронизации
├── google_drive.py           # Google Drive API клиент
├── yandex_disk.py            # Яндекс Диск API клиент
├── oauth_callback_server.py  # OAuth callback сервер
├── url_parser.py             # Парсинг ссылок
├── logger.py                 # Настройка логирования
├── pyproject.toml            # Зависимости
├── .env                      # Настройки (не коммитить)
├── .env.example              # Пример настроек
├── credentials.json          # Google credentials (не коммитить)
├── token.json                # Google токен (не коммитить)
└── sync.log                  # Логи (не коммитить)
```
