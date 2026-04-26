# Disks Sync

Синхронизация файлов между хранилищами: Google Drive, Яндекс Диск, локальная файловая система.

## Установка

Требуется Python 3.10+ и [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Быстрый старт

```bash
# 1. Создайте config.yaml (见 пример ниже)
# 2. Создайте auth.yaml с токенами или экспортируйте ENV переменные
# 3. Запустите синхронизацию
uv run python cli.py
```

## Настройка

### config.yaml

Основной файл конфигурации:

```yaml
backends:
  google:
    credentials_file: "credentials.json"
    token_file: "token.json"
    use_auto_oauth: true

  yandex:
    timeout: 30

  local:
    root: "/mnt/backup"

folders:
  photos_google:
    backend: google
    path: "Backups/Photos"

  photos_yandex:
    backend: yandex
    path: "MyBackup/Photos"

  docs_local:
    backend: local
    path: "/documents"

sync_pairs:
  - source: photos_google
    target: photos_yandex

logging:
  file: "sync.log"
  level: "INFO"
```

### Авторизация

#### Вариант 1: auth.yaml (приоритетнее)

Создайте `auth.yaml` для секретных данных:

```yaml
yandex:
  token: "y0_xxxxx"

google:
  credentials_file: "/path/to/credentials.json"
  token_file: "/path/to/token.json"
```

#### Вариант 2: ENV переменные

Экспортируйте переменные перед запуском:

```bash
export YANDEX_TOKEN="y0_xxxxx"
export GOOGLE_CREDENTIALS="/path/to/credentials.json"
export GOOGLE_TOKEN="/path/to/token.json"
```

#### Вариант 3: ${ENV_VAR} в config.yaml

```yaml
yandex:
  token: ${YANDEX_TOKEN}
```

### Получение токенов

#### Google Drive API

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com)
2. Создайте новый проект или выберите существующий
3. Включите **Google Drive API**
4. Создайте credentials:
   - APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: Desktop app
   - Скачайте JSON-файл и сохраните как `credentials.json`

#### Яндекс Диск

1. Перейдите по ссылке:
   ```
   https://oauth.yandex.ru/authorize?response_type=token&client_id=1a6990aa636648ffb9edcd2d15f140c5
   ```
2. Разрешите доступ
3. Скопируйте токен из URL после `access_token=`

## Запуск

```bash
# Запустить все sync_pairs из config.yaml
uv run python cli.py

# Использовать альтернативный config
uv run python cli.py --config production.yaml

# Запустить только первую пару
uv run python cli.py --pair 0

# Запустить несколько пар
uv run python cli.py --pair 0 --pair 2
```

При первом запуске Google автоматически откроется браузер для авторизации.

## CLI аргументы

| Аргумент | Описание |
|----------|----------|
| `-c`, `--config` | Путь к config.yaml (по умолчанию: config.yaml) |
| `-p`, `--pair` | Индекс пары для синхронизации (можно указать несколько) |

## Как работает

1. Для каждой sync_pair:
   - Получает список файлов из source папки
   - Получает список файлов из target папки
   - Для каждого файла:
     - Если файла нет в target → скачивает и загружает
     - Если файл есть и версия новее → перезаписывает
     - Если файл актуален → пропускает
2. Загружает до 3 файлов параллельно
3. Выводит отчёт о синхронизации

## Логи

Логи записываются в файл `sync.log` и выводятся в консоль.

Уровень логирования настраивается через `logging.level` в config.yaml:
- `DEBUG` — подробная информация
- `INFO` — основной процесс
- `WARNING` — предупреждения
- `ERROR` — ошибки

## Добавление нового хранилища

1. Создайте `src/backends/<name>.py` с классами:
   - `Authenticator` — авторизация
   - `Reader` (опционально) — скачивание файлов
   - `Writer` (опционально) — загрузка файлов
   - `<Name>Backend` — объединяет всё в `StorageBackend`
   - `<Name>BackendFactory` — фабрика с `@register_backend("name")`

2. Зарегистрируйте в `src/backends/__init__.py`

3. Добавьте в config.yaml:

```yaml
backends:
  mybackend:
    api_key: ${MY_API_KEY}

folders:
  my_data:
    backend: mybackend
    path: "/data"

sync_pairs:
  - source: my_data
    target: photos_yandex
```

## Структура проекта

```
disks_sync/
├── config.yaml              # Конфигурация хранилищ и синхронизации
├── auth.yaml                # Секреты (не коммитить)
├── cli.py                   # Точка входа
├── pyproject.toml           # Зависимости
│
└── src/
    ├── __init__.py          # Экспорт основных классов
    ├── protocols.py         # Интерфейсы: Authenticator, Reader, Writer, StorageBackend
    ├── factories.py         # BackendRegistry, @register_backend
    ├── sync.py              # SyncManager — логика синхронизации
    ├── models.py            # SyncStats, PairStats, SyncResult
    ├── logger.py            # Логирование
    │
    ├── google_drive.py      # Google Drive API клиент
    ├── yandex_disk.py      # Яндекс Диск API клиент
    ├── oauth_callback_server.py  # OAuth callback сервер
    │
    └── backends/
        ├── __init__.py      # Экспорт фабрик
        ├── google.py        # Google Drive backend
        ├── yandex.py        # Yandex Disk backend
        └── local.py         # Local filesystem backend
```

## Cron

```bash
crontab -e
```

```
0 10 * * * cd /path/to/disks_sync && /path/to/uv run python cli.py
```
