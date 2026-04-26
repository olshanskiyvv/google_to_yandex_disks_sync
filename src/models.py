from dataclasses import dataclass


@dataclass
class SyncStats:
    downloaded: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0


@dataclass
class PairStats:
    source_id: str = ""
    target_path: str = ""
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
