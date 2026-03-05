from pathlib import Path

from .contracts import RecoveryState, StorageEngineContract, StorageSnapshot
from .rocksdb import RocksDBEnginePort, RocksDBPortConfig


def create_storage_engine(
    engine_name: str = "rocksdb",
    rocksdb_root: str | Path | None = None,
) -> StorageEngineContract:
    normalized = engine_name.strip().lower()
    if normalized != "rocksdb":
        raise ValueError(f"unsupported storage engine '{engine_name}'")
    resolved_root = Path(rocksdb_root) if rocksdb_root is not None else Path("artifacts") / "rocksdb"
    root = RocksDBPortConfig.from_root(resolved_root)
    return RocksDBEnginePort(root)

__all__ = [
    "RecoveryState",
    "StorageEngineContract",
    "StorageSnapshot",
    "RocksDBEnginePort",
    "RocksDBPortConfig",
    "create_storage_engine",
]
