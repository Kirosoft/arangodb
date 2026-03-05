# DeethoughtDB Port Plan (Local Copy)

This is the working copy of the migration plan for the port package.
Source of truth is currently aligned with `../plan.md`.

## Objective

Port the `arangod` backend core while preserving backend/API behavior in scope:

- Include: backend services, storage integration contracts, transactions, replication, cluster, admin APIs.
- Exclude in this phase: AQL internals, V8/Foxx runtime, UI.
- Treat RocksDB internals as external; port integration contracts and behavior.

## Gates

- **Gate A (Blocking):** Backend core correctness
- **Gate B (Blocking):** Distributed + operational readiness
- **Gate C (Non-Blocking):** Deferred/excluded domains (AQL/V8/UI)

## Phases

1. Program setup and baseline freeze
2. Runtime skeleton and feature lifecycle
3. Transport and REST dispatch core
4. Catalog and storage interfaces
5. Transaction and document data plane
6. Auth, security, and admin plane
7. Cluster/agency/replication paths
8. Observability and operational hardening
9. Ecosystem compatibility and certification

## Current focus

- Continue endpoint-by-endpoint backend parity in `deethoughtdb_port/src/deethoughtdb_port/app.py`
- Keep strict test-first cadence: implement slice -> run tests -> commit -> push
- Keep strict live validation on isolated target (`http://127.0.0.1:8530`)

## Exit criteria

- Gate A and B suites green with no unexplained regressions
- Required validation artifacts generated
- Outstanding parity gaps documented and tracked to closure
