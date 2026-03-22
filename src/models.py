from dataclasses import dataclass


@dataclass
class SyncConfig:
    google_credentials_file: str
    google_token_file: str
    google_use_auto_oauth: bool
    yandex_token: str


@dataclass
class PairStats:
    google_id: str = ""
    yandex_path: str = ""
    downloaded: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    status: str = "pending"

    @property
    def success(self) -> bool:
        return self.status == "success"


@dataclass
class SyncResult:
    pair_stats: PairStats
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and self.pair_stats.success
