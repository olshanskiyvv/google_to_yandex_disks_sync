from src.factories import BackendFactory, register_backend
from src.protocols import (
    FileMetadata,
    StorageBackend,
)


class GoogleAuthenticator:
    def __init__(
        self,
        credentials_file: str,
        token_file: str,
        use_auto_oauth: bool = True,
    ):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.use_auto_oauth = use_auto_oauth
        self._client = None

    async def authenticate(self) -> None:
        from src.google_drive import GoogleDriveClient

        self._client = GoogleDriveClient(
            credentials_file=self.credentials_file,
            token_file=self.token_file,
            use_auto_oauth=self.use_auto_oauth,
        )
        await self._client.__aenter__()
        await self._client.authenticate()

    async def is_authenticated(self) -> bool:
        if not self._client or not self._client.access_token:
            return False
        return await self._client._check_token_valid()

    async def close(self) -> None:
        if self._client:
            await self._client.__aexit__(None, None, None)


class GoogleDriveReader:
    def __init__(self, authenticator: GoogleAuthenticator):
        self._auth = authenticator

    def _get_client(self):
        if not self._auth._client:
            raise RuntimeError("Client not authenticated")
        return self._auth._client

    def download_stream(
        self,
        file_id: str,
        file_path: str,
    ):
        client = self._get_client()
        return client.download_stream(file_id, file_path)

    async def get_file_metadata(self, file_id: str) -> FileMetadata:
        raise NotImplementedError("Google reader does not support single file metadata")


class GoogleBackend(StorageBackend):
    """Google Drive backend implementation."""

    def __init__(self, authenticator: GoogleAuthenticator):
        super().__init__(
            name="google",
            authenticator=authenticator,
            reader=GoogleDriveReader(authenticator),
            writer=None,
        )

    async def list_folder(self, folder: str) -> list[FileMetadata]:
        client = self._get_client()
        files = await client.list_files(folder)
        return [
            FileMetadata(
                path=f["path"],
                id=f["id"],
                modified=f["modified"],
                size=f["size"],
                is_folder=False,
            )
            for f in files
        ]

    def _get_client(self):
        if not isinstance(self.authenticator, GoogleAuthenticator):
            raise RuntimeError("Invalid authenticator type")
        if not self.authenticator._client:
            raise RuntimeError("Google client not authenticated")
        return self.authenticator._client


@register_backend("google")
class GoogleBackendFactory(BackendFactory):
    """Factory for Google Drive backend."""

    @classmethod
    def from_namespace(cls, namespace: dict) -> StorageBackend:
        return GoogleBackend(
            authenticator=GoogleAuthenticator(
                credentials_file=namespace.get("credentials_file", "credentials.json"),
                token_file=namespace.get("token_file", "token.json"),
                use_auto_oauth=namespace.get("use_auto_oauth", True),
            )
        )

    @classmethod
    def required_fields(cls) -> list[str]:
        return ["credentials_file", "token_file"]
