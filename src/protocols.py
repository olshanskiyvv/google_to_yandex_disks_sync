from typing import AsyncIterator, Protocol, runtime_checkable
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FileMetadata:
    """Metadata for a file or folder in storage."""

    path: str
    id: str
    modified: datetime
    size: int
    is_folder: bool


@runtime_checkable
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


@runtime_checkable
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


@runtime_checkable
class Writer(Protocol):
    """Uploads files and creates folder structure."""

    async def ensure_folder_exists(self, folder_path: str) -> None:
        """Ensure a folder exists (create if missing)."""
        ...

    async def ensure_parent_folders(self, file_path: str) -> None:
        """Ensure all parent folders exist for a file path."""
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


@dataclass
class StorageBackend:
    """
    Complete storage backend with all capabilities.

    Attributes:
        name: Unique identifier for this backend (e.g., "yandex", "google")
        authenticator: Handles authentication lifecycle
        reader: Downloads files (None for write-only backends)
        writer: Uploads files (None for read-only backends)
    """

    name: str
    authenticator: Authenticator
    reader: Reader | None = None
    writer: Writer | None = None

    async def list_folder(self, folder: str) -> list[FileMetadata]:
        """
        List files in a folder.

        Args:
            folder: Folder path or ID within this storage

        Returns:
            List of FileMetadata for files in the folder
        """
        raise NotImplementedError(f"Backend '{self.name}' does not support listing")

    async def __aenter__(self) -> "StorageBackend":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        """Close all resources."""
        await self.authenticator.close()
