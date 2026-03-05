# RocksDB Ported Directed Structure

This package now treats RocksDB as a first-class subsystem in the new port:

- `src/deethoughtdb_port/storage/contracts/storage_engine.py`
  - canonical storage engine contract surface (recovery, WAL, DB/collection lifecycle, replication applier config)
- `src/deethoughtdb_port/storage/rocksdb/config.py`
  - runtime config and path model
- `src/deethoughtdb_port/storage/rocksdb/bindings.py`
  - python-rocksdb binding adapter (optional availability)
- `src/deethoughtdb_port/storage/rocksdb/catalog.py`
  - RocksDB-backed catalog model for databases/collections
- `src/deethoughtdb_port/storage/rocksdb/wal.py`
  - WAL manager and tick lifecycle
- `src/deethoughtdb_port/storage/rocksdb/engine.py`
  - `RocksDBEnginePort` implementation of full contract

## Runtime wiring

`build_default_server()` now instantiates `RocksDBEnginePort` by default:

- storage root default: `artifacts/rocksdb`
- override: `build_default_server(..., rocksdb_root="<path>")`

Replication applier config endpoints (`/_api/replication/applier-config`) are persisted through the RocksDB engine contract.

## Validation

Dedicated contract tests:

- `tests/test_rocksdb_engine_port.py`

Live integration tests against real arangod+RocksDB engine remain in:

- `tests/test_live_rocksdb_integration.py`
