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
