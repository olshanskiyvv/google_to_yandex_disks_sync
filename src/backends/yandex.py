from typing import Any, AsyncIterator

from src.factories import BackendFactory, register_backend
from src.protocols import (
    FileMetadata,
    StorageBackend,
)


class YandexAuthenticator:
    def __init__(self, token: str):
        self.token = token
        self._client = None

    async def authenticate(self) -> None:
        from src.yandex_disk import YandexDiskClient

        self._client = YandexDiskClient(token=self.token)
        await self._client.__aenter__()
        await self._client.authenticate()

    async def is_authenticated(self) -> bool:
        if not self._client or not self._client.client:
            return False
        return await self._client.client.check_token()

    async def close(self) -> None:
        if self._client:
            await self._client.__aexit__(None, None, None)


class YandexDiskWriter:
    def __init__(self, authenticator: YandexAuthenticator):
        self._auth = authenticator

    def _get_client(self):
        if not self._auth._client:
            raise RuntimeError("Client not authenticated")
        return self._auth._client.client

    async def ensure_folder_exists(self, folder_path: str) -> None:
        client = self._get_client()
        if not await client.exists(folder_path):
            await client.mkdir(folder_path)

    async def ensure_parent_folders(self, file_path: str) -> None:
        client = self._get_client()
        parts = [p for p in file_path.rstrip("/").split("/")[:-1] if p]
        current_path = ""

        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else f"/{part}"
            if not await client.exists(current_path):
                await client.mkdir(current_path)

    async def upload_stream(
        self,
        source: AsyncIterator[bytes],
        remote_path: str,
        overwrite: bool = False,
    ) -> FileMetadata:
        client = self._get_client()

        async def stream_generator() -> AsyncIterator[bytes]:
            async for chunk in source:
                yield chunk

        await client.upload(stream_generator, remote_path, overwrite=overwrite)

        stat = await client.stat(remote_path)
        return FileMetadata(
            path=remote_path,
            id=remote_path,
            modified=stat.modified,
            size=stat.size or 0,
            is_folder=False,
        )

    async def file_exists(self, remote_path: str) -> bool:
        client = self._get_client()
        return await client.exists(remote_path)


class YandexBackend(StorageBackend):
    """Yandex Disk backend implementation."""

    def __init__(self, authenticator: YandexAuthenticator):
        super().__init__(
            name="yandex",
            authenticator=authenticator,
            reader=None,
            writer=YandexDiskWriter(authenticator),
        )

    async def list_folder(self, folder: str) -> list[FileMetadata]:
        client = self._get_client()
        files: dict[str, Any] = {}
        await self._list_recursive(client, folder, "", files)

        return [
            FileMetadata(
                path=path,
                id=data["full_path"],
                modified=data["modified"],
                size=data["size"],
                is_folder=False,
            )
            for path, data in files.items()
        ]

    def _get_client(self):
        if not isinstance(self.authenticator, YandexAuthenticator):
            raise RuntimeError("Invalid authenticator type")
        if not self.authenticator._client:
            raise RuntimeError("Yandex client not authenticated")
        return self.authenticator._client.client

    async def _list_recursive(
        self, client, folder: str, base_path: str, files: dict[str, Any]
    ) -> None:
        async for item in client.listdir(folder):
            item_name = item.name or ""
            item_path = f"{base_path}/{item_name}" if base_path else item_name

            if item.type == "dir" and item.path:
                await self._list_recursive(client, item.path, item_path, files)
            elif item.type == "file" and item_path:
                files[item_path] = {
                    "name": item_name,
                    "path": item_path,
                    "modified": item.modified,
                    "size": item.size or 0,
                    "full_path": item.path or "",
                }


@register_backend("yandex")
class YandexBackendFactory(BackendFactory):
    """Factory for Yandex Disk backend."""

    @classmethod
    def from_namespace(cls, namespace: dict) -> StorageBackend:
        return YandexBackend(
            authenticator=YandexAuthenticator(
                token=namespace["token"],
            )
        )

    @classmethod
    def required_fields(cls) -> list[str]:
        return ["token"]
