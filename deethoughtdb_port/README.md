# DeethoughtDB Port Foundation

This package contains the initial implementation for the `plan.md` Phases 2-3:

- feature lifecycle and dependency-aware startup/shutdown
- REST handler factory with API versioning and prefix matching
- standardized backend API error envelope
- domain service interfaces for catalog/storage/transactions

## Quick start

```bash
cd deethoughtdb_port
python -m pip install -e .
python -m unittest discover -s tests -v
```

## Live RocksDB integration tests (no mocks)

These tests validate behavior against a running `arangod` using the real RocksDB engine.

Required environment variables:

- `DTH_LIVE_ROCKSDB=1`
- `DTH_ARANGO_PASSWORD=<root-password>`
- optional: `DTH_ARANGO_URL` (default `http://127.0.0.1:8529`)
- optional: `DTH_ARANGO_USER` (default `root`)

Run:

```bash
cd deethoughtdb_port
python -m unittest tests.test_live_rocksdb_integration -v
```

The suite will:

1. authenticate against `/_open/auth`
2. assert `/_api/engine` reports `rocksdb`
3. create an isolated temporary database
4. create collection/documents and validate roundtrip behavior
5. run a live transaction begin/commit path
6. delete the temporary database during teardown

Example local `arangod` launch (single server):

```bash
arangod --server.endpoint tcp://127.0.0.1:8529 --server.authentication true --database.directory <path>
```
