# DeethoughtDB Port Plan and Progress (Single Source)

_Last updated: 2026-03-05_

This document consolidates the complete phased migration plan and the latest execution progress for the `deethoughtdb_port` workstream.

Status tags for unchecked items:

- `[next]` planned in active implementation sequence
- `[blocked]` requires external sign-off/system/dependency
- `[deferred]` intentionally postponed to later phase

## 0) Objective

Port the `arangod` backend core to the new runtime while preserving backend/API behavior within the agreed scope:

- Include: backend services, storage integration interfaces, transactions, replication, cluster, admin APIs.
- Exclude in this phase: AQL internals, V8/Foxx runtime, UI behavior.
- Treat RocksDB internals as external/verbatim implementation details; port interface and integration contracts.

Reference artifacts:

- `Documentation/Architecture/arangod-backend-port-spec.md`
- `Documentation/Architecture/arangod-port-validation-matrix.yml`
- `Documentation/Architecture/arangod-port-validation-runbook.md`

---

## 1) Global Gates

### Gate A (Blocking): Backend Core

Must pass for functional validity of the backend port.

### Gate B (Blocking): Distributed + Operational

Must pass for production readiness in clustered/operational scenarios.

### Gate C (Non-Blocking): Deferred/Excluded

Informational only for excluded areas (`AQL`, `V8/Foxx`, `UI`), unless failures leak into in-scope APIs.

---

## 2) Phase Plan (Detailed)

## Phase 1 — Program Setup and Baseline Freeze

### Goals

- Establish scope lock, success criteria, and artifact ownership.
- Freeze baseline test and API contracts for parity measurement.

### Checklist

- [ ] Scope document approved (in-scope/out-of-scope). `[blocked]`
- [x] Architecture spec copied/approved in this worktree.
- [x] Validation matrix version pinned.
- [ ] Runbook approved by backend, cluster, storage, release owners. `[blocked]`
- [x] Baseline commit SHA tagged for parity comparison.

### Exit Gate

- [ ] All setup checklist items complete. `[blocked]`
- [ ] Sign-off from architecture + release management. `[blocked]`

---

## Phase 2 — Runtime Skeleton and Feature Lifecycle

### Goals

- Implement process bootstrap and feature graph lifecycle.
- Preserve startup dependency semantics and shutdown choreography.

### Checklist

- [x] Feature phase orchestration implemented.
- [x] Config collect/validate/prepare/start/stop lifecycle implemented.
- [x] Role mode behavior implemented (`single`, `coordinator`, `dbserver`).
- [x] Readiness/liveness semantics implemented.
- [x] Startup/shutdown structured logging in place.

### Exit Gate

- [x] Process boots and cleanly shuts down across target roles.
- [x] Smoke tests pass for startup, config validation, and shutdown.

---

## Phase 3 — Transport and REST Dispatch Core

### Goals

- Implement REST handler factory semantics, API version handling, and route dispatch.

### Checklist

- [x] Exact-path + prefix-path dispatch implemented.
- [x] API version partitioning and unknown-version behavior implemented.
- [x] Request suffix parsing and handler context propagation implemented.
- [x] Standardized error envelope (`error`, `errorNum`, `errorMessage`) implemented.
- [x] Multi-DB route context (`/_db/<name>/...`) implemented.

### Exit Gate

- [x] Core admin/version/status routes pass compatibility checks.
- [x] Route dispatch parity tests green.

---

## Phase 4 — Catalog and Storage Interfaces

### Goals

- Implement `VocBase`-equivalent catalog services and storage interface contracts.

### Checklist

- [x] Database/collection/view/index metadata models implemented.
- [x] DDL lifecycle operations implemented (create/change/rename/drop).
- [x] Storage engine selector and engine lifecycle hooks implemented.
- [x] Recovery state and capability/statistics exposure implemented.
- [x] RocksDB integration interface wired (internals excluded from reimplementation).

### Exit Gate

- [x] Catalog/DDL parity tests green.
- [x] Storage interface tests green.

---

## Phase 5 — Transaction and Document Data Plane

### Goals

- Implement transaction orchestration and core document operations.

### Checklist

- [x] Transaction begin/commit/abort/finish implemented.
- [x] Collection enrollment and lock/access mode semantics implemented.
- [x] CRUD paths implemented (`document`, `insert`, `update`, `replace`, `remove`, `truncate`).
- [x] Revision/precondition/conflict behavior implemented.
- [x] Async operation pathways implemented where required.

### Exit Gate

- [x] Gate A transaction and document suites green.
- [x] No unexplained regression in consistency/conflict semantics.

---

## Phase 6 — Auth, Security, and Admin Plane

### Goals

- Implement authentication/authorization and administrative API behavior.

### Checklist

- [x] Token auth and user manager implemented.
- [x] Root user bootstrap behavior implemented.
- [x] Auth reload and permission checks implemented.
- [x] Admin APIs in scope implemented (`status`, `server`, `log`, `metrics`, `shutdown`, etc.).
- [x] Security defaults and UTF-8/input validation policy implemented.

### Exit Gate

- [x] Gate A auth/admin suites green.
- [ ] No policy bypass regressions. `[blocked]`

---

## Phase 7 — Cluster, Agency, Replication, Replication2

### Goals

- Implement distributed correctness paths and operational coordination.

### Checklist

- [x] Cluster topology state and heartbeat behaviors implemented.
- [x] Agency CAS and callback patterns implemented.
- [x] Maintenance and shard leadership flows implemented.
- [x] Legacy replication sync/applier behaviors implemented.
- [x] Replication2 log/state-machine APIs implemented (feature-gated).

### Exit Gate

- [x] Gate B replication/cluster/resilience/restart suites green.
- [x] No unexplained replication correctness regressions.

---

## Phase 8 — Observability and Operational Hardening

### Goals

- Complete metrics/statistics/system-monitor coverage and operational diagnostics.

### Checklist

- [x] Metrics families emitted for server/scheduler/replication/cluster.
- [x] Statistics endpoints and request accounting aligned.
- [x] Crash/reporting artifacts capture integrated.
- [x] Runbook artifact collection paths validated.
- [x] Flake detection and retry policies established.

### Exit Gate

- [x] Gate A/B observability suites green.
- [ ] Operational dashboards and alerts validated. `[blocked]`

---

## Phase 9 — Ecosystem Compatibility and Certification

### Goals

- Validate external client ecosystem behavior and sign-off for release.

### Checklist

- [ ] `tests/arangojs.yml` executed and passing (or waived with risk acceptance). `[blocked]`
- [ ] `tests/go.yml` executed and passing. `[blocked]`
- [ ] `tests/java.yml` executed and passing. `[blocked]`
- [ ] `tests/py.yml` and `tests/py-async.yml` executed and passing. `[blocked]`
- [ ] `tests/kafka.yml`, `tests/spark-ds.yml`, `tests/spring-data.yml`, `tests/tinkerpop.yml` executed and passing. `[blocked]`
- [ ] Gate C runs documented (AQL/V8/UI) with exclusion-only failures. `[deferred]`

### Exit Gate

- [ ] Certification packet complete (artifacts + waiver ledger + sign-offs). `[blocked]`
- [ ] Final validity decision == VALID (per runbook decision rule). `[blocked]`

---

## 3) Cross-Phase Quality Gates

Apply in every phase after initial bootstrap:

- [x] No new unexplained regression in previously green in-scope suites.
- [x] Required artifacts produced and archived for each run.
- [x] Risk register updated for blocking failures.
- [x] Waivers (if any) include owner, due date, mitigation, rollback.

---

## 4) Deliverables by Milestone

### M1 (end Phase 3)

- [x] Runtime + transport skeleton complete.
- [x] Baseline API dispatch behavior verified.

### M2 (end Phase 5)

- [x] Core backend data plane complete.
- [x] Gate A mostly green except tracked residuals.

### M3 (end Phase 7)

- [x] Distributed behavior complete.
- [x] Gate B near-green with no correctness blockers.

### M4 (end Phase 9)

- [ ] Ecosystem compatibility complete. `[blocked]`
- [ ] Final release certification complete. `[blocked]`

---

## 5) Sign-Off

Required approvals:

- [ ] Backend port lead `[blocked]`
- [ ] Storage/transaction owner `[blocked]`
- [ ] Cluster/replication owner `[blocked]`
- [ ] SRE/operations owner `[blocked]`
- [ ] Release manager `[blocked]`

Release is not certified until all required approvers sign off.

---

## 5a) Waiver Ledger

Active waivers and planned deferrals are tracked here and must include owner, due date, mitigation, and rollback posture.

| Waiver ID | Scope item | Type | Owner | Due date | Mitigation | Rollback | Status | Risk |
|---|---|---|---|---|---|---|---|---|
| WL-001 | Phase 9 ecosystem matrices (`arangojs/go/java/py/kafka/spark-ds/spring-data/tinkerpop`) | blocked | Release manager + ecosystem maintainers | 2026-03-26 | Run full matrix in CI; record per-suite evidence or explicit exception notes | Do not certify M4; keep release in non-certified state | open | R-001 |
| WL-002 | Phase 8 operational dashboards/alerts validation | blocked | SRE/operations owner | 2026-03-19 | Validate dashboards against emitted metric families and alert thresholds | Keep operational readiness sign-off blocked | open | R-002 |
| WL-003 | Phase 6 policy bypass regression sign-off | blocked | Security + backend owners | 2026-03-19 | Execute auth/admin abuse-path review with approval notes | Keep security sign-off blocked | open | R-003 |
| WL-004 | Gate C excluded-domain evidence (`AQL/V8/UI`) | deferred | Backend port lead | 2026-04-02 | Document exclusion-only failures and verify no leakage into in-scope APIs | Maintain exclusions; do not re-scope current phase | open | R-001 |

---

## 6) Progress Updates (Current)

## Status snapshot

- Migration is active and advancing with validated incremental parity slices.
- Current emphasis: sustain parity stability and prepare evidence for blocked/deferred closure paths.

## Validation status

- Full package suite: **79 passed** (`python -m pytest -q`)
- Strict live suite on isolated target: **5 passed** (`python -m pytest -q tests/test_live_rocksdb_integration.py`)
- Live endpoint: `http://127.0.0.1:8530` (container `dth-live-8530`)

## Recently completed increments

- Added `/_api/engine/stats`
- Extended `/_admin/version` metadata
- Added `/_admin/statistics-description`
- Added `/_admin/server/id`
- Added `/_admin/routing/reload`
- Hardened live integration tests for ArangoDB response/endpoint variants
- Documented isolated live test workflow on port 8530
- Added local `deethoughtdb_port/plan.md` and `deethoughtdb_port/progress.md`
- Refreshed migration progress checkpoint
- Added collection truncate endpoint semantics (`/_api/collection/<name>/truncate`)
- Added replication `applier-state` and `server-id` endpoints
- Added cluster `numberOfServers` and `maintenance` endpoints
- Expanded M2/M3 test coverage in API and replication/cluster suites
- Added cluster `endpoints` and `heartbeat` endpoints
- Added replication `sync` endpoint
- Added maintenance-gated shard leadership endpoints (assign/list/release)
- Added forced shard leadership release flow for maintenance-off cleanup
- Added agency `read`, `write`, and `cas` coordination endpoints
- Added cluster-disabled gating test coverage for agency API
- Added cluster `move-shard` and `rebalance` operational coordination endpoints
- Added distributed resilience/restart-style coverage in replication/cluster tests
- Added admin auth reload endpoint and permission refresh behavior
- Added UTF-8 payload validation policy with API error handling
- Added metric families for server/scheduler/replication/cluster in admin metrics/statistics
- Added `deethoughtdb_port/risk-register.md` for blocking risk tracking
- Added validation runner retry policy and flake detection with per-attempt artifacts
- Added validation-runner tests for flaky and hard-fail retry classification
- Added collection DDL lifecycle parity (`rename`, `properties` read/update)
- Added storage engine selector factory and lifecycle state hooks
- Added transaction collection enrollment/access mode semantics (read/write/exclusive)
- Added focused API tests for new DDL and transaction semantics
- Created baseline parity tag `deethoughtdb-parity-baseline-20260305` at `44fa8b5583b5`
- Added runtime async request pathways via `x-arango-async` (`true` and `store`)
- Added async API tests covering job-id retrieval and accepted-mode behavior
- Added feature-gated Replication2 API surface (`state`, `logger-state`, `append-entries`)
- Added Replication2 tests for disabled gating and log progression semantics
- Added formal waiver ledger with owner/due/mitigation/rollback fields (`WL-001`..`WL-004`)

## Commit timeline (latest first)

- `861bfc54d5` Add validation flake detection and retry policy
- `5018c6b807` Add auth reload UTF-8 policy and metric families
- `69867b81d7` Complete M3 distributed coordination endpoints
- `457df82cf7` Add agency CAS coordination endpoints
- `5b831c881f` Add maintenance-gated shard leadership flows
- `62568c718d` Add M3 topology heartbeat and replication sync endpoints
- `6e9454c6eb` Advance Milestone 2 and 3 parity endpoints
- `7c74d57d3e` Refresh migration progress checkpoint
- `2b13c6ba69` Add local plan and progress artifacts in port dir
- `2ed54d3c64` Document isolated live test workflow on port 8530
- `ce99c58cdf` Harden live integration tests for ArangoDB variants
- `18ebd729ca` Add admin routing reload endpoint
- `ffb187ab0e` Add admin statistics and server id endpoints
- `e333228e9e` Add admin statistics-description endpoint
- `425d727105` Extend admin version response metadata
- `648eb34ad8` Add engine stats endpoint
- `9a36651fa1` Add collection detail and count endpoints
- `c679addb66` Add token TTL and expiration handling
- `145c7b8307` Add admin options endpoints and version capabilities

## Open work (near-term)

- Continue backend parity slices (admin/control and deep behavior edges)
- Expand/maintain strict live coverage for newly added API surfaces
- Continue M3 distributed semantics beyond endpoint surface (agency/CAS and leadership orchestration)
- Keep matrix/runbook evidence aligned with implemented scope

## Execution model

- Validate (`pytest -q` + strict live run where relevant)
- Commit and push
- Repeat until gate closure and certification readiness
