# Pluggable Disk Sync Architecture

## 1. Overview

Current state: Hardcoded Google Drive + Yandex Disk implementation in `SyncManager`. Storage clients are instantiated directly in `cli.py`.

Goal: Abstract all storage operations behind interfaces, enabling any backend to be injected via configuration.

---

## 2. Core Abstractions

### 2.1 FileMetadata

```python
@dataclass
class FileMetadata:
    path: str           # Relative path within the storage namespace
    id: str             # Backend-specific file/folder identifier
    modified: datetime  # Last modification time (UTC)
    size: int           # Size in bytes (0 for folders)
    is_folder: bool     # True if this is a folder
```

### 2.2 Authenticator

Handles backend-specific authentication lifecycle.

```python
class Authenticator(Protocol):
    """Authenticates with a storage backend."""

    async def authenticate(self) -> None:
        """Initialize the backend connection. May refresh tokens."""
        ...

    async def is_authenticated(self) -> bool:
        """Check if currently authenticated and token is valid."""
        ...

    async def close(self) -> None:
        """Clean up resources (close sessions, release tokens)."""
        ...
```

**Registered backends**: `GoogleAuthenticator`, `YandexAuthenticator`, `S3Authenticator` (key/secret), `LocalAuthenticator` (no-op).

### 2.3 Lister

Lists files in a folder with pagination support.

```python
class Lister(Protocol):
    """Lists files and folders in a storage location."""

    async def list_folder(self, folder_id: str) -> list[FileMetadata]:
        """
        List all files directly inside a folder.

        Args:
            folder_id: Backend-specific folder identifier or path

        Returns:
            List of FileMetadata for immediate children (non-recursive)
        """
        ...
```

**Registered backends**: `GoogleDriveLister`, `YandexDiskLister`, `S3Lister`, `LocalLister`.

### 2.4 Reader

Downloads file content as a stream.

```python
class Reader(Protocol):
    """Downloads file content from a storage backend."""

    def download_stream(
        self,
        file_id: str,
        file_path: str,
    ) -> AsyncIterator[bytes]:
        """
        Download a file as a streaming byte iterator.

        Args:
            file_id: Backend-specific file identifier
            file_path: For progress reporting or logging

        Yields:
            Bytes chunks of the file content
        """
        ...

    async def get_file_metadata(self, file_id: str) -> FileMetadata:
        """Retrieve metadata for a specific file."""
        ...
```

**Registered backends**: `GoogleDriveReader`, `YandexDiskReader`, `S3Reader`, `LocalReader`.

### 2.5 Writer

Uploads files and creates folder structure.

```python
class Writer(Protocol):
    """Uploads files and creates folder structure."""

    async def ensure_folder_exists(self, folder_path: str) -> None:
        """
        Ensure a folder exists (create if missing).

        Args:
            folder_path: Full path to the folder (may be namespaced)
        """
        ...

    async def ensure_parent_folders(self, file_path: str) -> None:
        """
        Ensure all parent folders exist for a file path.

        Args:
            file_path: Full path whose parents should exist
        """
        ...

    async def upload_stream(
        self,
        source: AsyncIterator[bytes],
        remote_path: str,
        overwrite: bool = False,
    ) -> FileMetadata:
        """
        Upload file content.

        Args:
            source: Byte stream to upload
            remote_path: Destination path
            overwrite: Whether to overwrite existing file

        Returns:
            FileMetadata for the uploaded file
        """
        ...

    async def file_exists(self, remote_path: str) -> bool:
        """Check if a file exists at the given path."""
        ...
```

**Registered backends**: `YandexDiskWriter`, `S3Writer`, `LocalWriter` (note: Google Drive is read-only in current impl).

### 2.6 StorageBackend

Aggregates the above capabilities into a single interface.

```python
@dataclass
class StorageBackend:
    """Complete storage backend with all capabilities."""

    name: str
    authenticator: Authenticator
    lister: Lister
    reader: Reader | None      # None for write-only backends
    writer: Writer | None      # None for read-only backends

    async def close(self) -> None:
        """Close all resources."""
        ...
```

---

## 3. Plugin Registry

### 3.1 BackendRegistry

```python
class BackendRegistry:
    """
    Singleton registry for storage backends.

    Usage:
        registry = BackendRegistry()
        registry.register("yandex", yandex_backend)
        registry.get("yandex")  # returns StorageBackend
    """

    _backends: dict[str, StorageBackend] = {}
    _factories: dict[str, type[BackendFactory]] = {}

    def register(self, name: str, backend: StorageBackend) -> None: ...

    def register_factory(self, name: str, factory: type[BackendFactory]) -> None: ...

    def get(self, name: str) -> StorageBackend | None: ...

    def list_registered(self) -> list[str]: ...

    @classmethod
    def from_config(cls, config: dict) -> StorageBackend: ...
```

### 3.2 BackendFactory

```python
class BackendFactory(Protocol):
    """Creates a StorageBackend from config namespace."""

    @classmethod
    def from_namespace(cls, namespace: dict) -> StorageBackend:
        """
        Build a complete StorageBackend from a config namespace.

        Example namespace for "yandex":
            {
                "token": "abc123",
                "timeout": 30
            }
        """
        ...

    @classmethod
    def required_fields(cls) -> list[str]:
        """Fields that must be present in the config namespace."""
        ...
```

### 3.3 Registration Decorator

```python
def register_backend(name: str):
    """Decorator to register a backend factory."""
    def decorator(cls: type[BackendFactory]) -> type[BackendFactory]:
        BackendRegistry().register_factory(name, cls)
        return cls
    return decorator

# Usage:
@register_backend("yandex")
class YandexBackendFactory:
    ...
```

---

## 4. Configuration Structure

### 4.1 JSON Config File

```json
{
  "backends": {
    "google": {
      "credentials_file": "credentials.json",
      "token_file": "token.json",
      "use_auto_oauth": true
    },
    "yandex": {
      "token": "y0_xxxxx",
      "timeout": 30
    },
    "s3": {
      "endpoint": "https://s3.example.com",
      "bucket": "my-backups",
      "access_key": "AKIA...",
      "secret_key": "...",
      "region": "us-east-1"
    },
    "local": {
      "root": "/mnt/backup"
    }
  },
  "sync": {
    "source": "google",
    "destination": "yandex",
    "semaphore_limit": 3
  },
  "logging": {
    "file": "sync.log",
    "level": "INFO"
  }
}
```

### 4.2 Config Class

```python
@dataclass
class AppConfig:
    backends: dict[str, dict]
    sync: dict
    logging: dict

    @classmethod
    def from_file(cls, path: str) -> AppConfig: ...

    @classmethod
    def from_env(cls) -> AppConfig: ...

    def get_backend(self, name: str) -> StorageBackend: ...

    def validate(self) -> list[str]: ...
```

---

## 5. Refactored SyncManager

```python
class SyncManager:
    """Syncs files between two storage backends."""

    def __init__(
        self,
        source: StorageBackend,
        destination: StorageBackend,
        semaphore_limit: int = 3,
    ):
        self.source = source
        self.destination = destination
        self.semaphore = asyncio.Semaphore(semaphore_limit)
        self.stats_lock = asyncio.Lock()

    async def sync(self, source_folder: str, dest_folder: str) -> SyncResult:
        """Sync files from source folder to destination folder."""
        # Validation
        if self.source.lister is None:
            raise ValueError(f"Source backend '{self.source.name}' cannot list files")
        if self.destination.writer is None:
            raise ValueError(f"Destination backend '{self.destination.name}' cannot write files")

        # List files
        source_files = await self.source.lister.list_folder(source_folder)
        dest_files = await self.destination.lister.list_folder(dest_folder) \
            if self.destination.lister else {}

        # Sync logic...
```

---

## 6. CLI Integration

```python
async def _async_main(config: AppConfig) -> None:
    source_backend = config.get_backend(config.sync["source"])
    dest_backend = config.get_backend(config.sync["destination"])

    async with source_backend, dest_backend:
        await source_backend.authenticator.authenticate()
        await dest_backend.authenticator.authenticate()

        sync_manager = SyncManager(
            source=source_backend,
            destination=dest_backend,
            semaphore_limit=config.sync.get("semaphore_limit", 3),
        )
        await sync_manager.sync(
            source_folder=config.sync.get("source_folder", ""),
            dest_folder=config.sync.get("dest_folder", ""),
        )
```

---

## 7. Affected Files

| File | Changes |
|------|---------|
| `src/protocols.py` | Expand with `Authenticator`, `Lister`, `Reader`, `Writer` protocols; rename existing to `FileMetadata`; add `StorageBackend` dataclass |
| `src/sync.py` | Replace `SyncManager.__init__` to accept `StorageBackend` instead of concrete clients |
| `src/models.py` | Remove `SyncConfig` (moved to config.py), keep stats models |
| `config.py` | Replace `@dataclass Config` with `AppConfig` supporting JSON and env, backend registry integration |
| `cli.py` | Replace client instantiation with `AppConfig.from_file()` / `from_env()` + `config.get_backend()` |
| `src/backends/` | New directory for backend implementations (`google.py`, `yandex.py`, `s3.py`, `local.py`) |
| `src/factories.py` | Backend factory classes and registration decorators |

---

## 8. New Directory Structure

```
src/
  __init__.py
  protocols.py          # All interface definitions
  models.py             # SyncStats, PairStats, SyncResult, FileMetadata
  sync.py               # SyncManager
  backends/
    __init__.py
    base.py             # BackendFactory base class
    google.py           # GoogleDrive implementation
    yandex.py           # YandexDisk implementation
    s3.py               # S3 implementation
    local.py            # Local filesystem implementation
  factories.py          # Registry and decorators
config.py               # AppConfig with JSON/env support
cli.py                  # CLI entry point
```

---

## 9. Backends to Implement

| Backend | Reader | Writer | Auth |Lister |
|---------|--------|--------|------|-------|
| Google Drive | Yes | No | OAuth2 | Yes |
| Yandex Disk | No | Yes | Token | Yes |
| S3 | Yes | Yes | Key/Secret | Yes |
| Local | Yes | Yes | No-op | Yes |

---

## 10. Adding a New Backend

1. Create `src/backends/<name>.py` implementing `Authenticator`, `Lister`, `Reader`, `Writer` protocols
2. Create a factory class:

```python
@register_backend("mybackend")
class MyBackendFactory:
    @classmethod
    def from_namespace(cls, namespace: dict) -> StorageBackend:
        return StorageBackend(
            name="mybackend",
            authenticator=MyAuthenticator(namespace["api_key"]),
            lister=MyLister(...),
            reader=MyReader(...),
            writer=MyWriter(...),
        )

    @classmethod
    def required_fields(cls) -> list[str]:
        return ["api_key", "endpoint"]
```

3. Add to JSON config:

```json
{
  "backends": {
    "mybackend": {
      "api_key": "...",
      "endpoint": "https://api.example.com"
    }
  }
}
```