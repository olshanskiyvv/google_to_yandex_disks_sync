import os
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from src.factories import BackendFactory, register_backend
from src.protocols import (
    FileMetadata,
    StorageBackend,
)


class LocalAuthenticator:
    """No-op authenticator for local filesystem."""

    def __init__(self, root: str):
        self.root = root

    async def authenticate(self) -> None:
        pass

    async def is_authenticated(self) -> bool:
        return Path(self.root).exists()

    async def close(self) -> None:
        pass


class LocalReader:
    def __init__(self, authenticator: LocalAuthenticator):
        self._auth = authenticator

    def _get_root(self) -> Path:
        return Path(self._auth.root)

    def download_stream(self, file_id: str, file_path: str) -> AsyncIterator[bytes]:
        full_path = self._get_root() / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {full_path}")

        async def stream():
            with open(full_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

        return stream()

    async def get_file_metadata(self, file_id: str) -> FileMetadata:
        path = Path(file_id)
        stat = path.stat()
        return FileMetadata(
            path=str(path),
            id=str(path),
            modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            size=stat.st_size,
            is_folder=path.is_dir(),
        )


class LocalWriter:
    def __init__(self, authenticator: LocalAuthenticator):
        self._auth = authenticator

    def _get_root(self) -> Path:
        return Path(self._auth.root)

    async def ensure_folder_exists(self, folder_path: str) -> None:
        full_path = self._get_root() / folder_path.lstrip("/")
        full_path.mkdir(parents=True, exist_ok=True)

    async def ensure_parent_folders(self, file_path: str) -> None:
        full_path = self._get_root() / file_path.lstrip("/")
        full_path.parent.mkdir(parents=True, exist_ok=True)

    async def upload_stream(
        self,
        source: AsyncIterator[bytes],
        remote_path: str,
        overwrite: bool = False,
    ) -> FileMetadata:
        full_path = self._get_root() / remote_path.lstrip("/")

        if full_path.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {full_path}")

        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, "wb") as f:
            async for chunk in source:
                f.write(chunk)

        stat = full_path.stat()
        return FileMetadata(
            path=remote_path,
            id=str(full_path),
            modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            size=stat.st_size,
            is_folder=False,
        )

    async def file_exists(self, remote_path: str) -> bool:
        full_path = self._get_root() / remote_path.lstrip("/")
        return full_path.exists()


class LocalBackend(StorageBackend):
    """Local filesystem backend implementation."""

    def __init__(self, authenticator: LocalAuthenticator):
        super().__init__(
            name="local",
            authenticator=authenticator,
            reader=LocalReader(authenticator),
            writer=LocalWriter(authenticator),
        )

    async def list_folder(self, folder: str) -> list[FileMetadata]:
        root = self._get_root()
        full_path = root / folder.lstrip("/")

        if not full_path.exists():
            return []

        files = []
        for entry in os.scandir(full_path):
            stat = entry.stat()
            is_folder = entry.is_dir()
            files.append(
                FileMetadata(
                    path=entry.name,
                    id=str(Path(folder) / entry.name),
                    modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                    size=0 if is_folder else stat.st_size,
                    is_folder=is_folder,
                )
            )

        return files

    def _get_root(self) -> Path:
        if not isinstance(self.authenticator, LocalAuthenticator):
            raise RuntimeError("Invalid authenticator type")
        return Path(self.authenticator.root)


@register_backend("local")
class LocalBackendFactory(BackendFactory):
    """Factory for local filesystem backend."""

    @classmethod
    def from_namespace(cls, namespace: dict) -> StorageBackend:
        return LocalBackend(
            authenticator=LocalAuthenticator(
                root=namespace["root"],
            )
        )

    @classmethod
    def required_fields(cls) -> list[str]:
        return ["root"]
