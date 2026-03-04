# DeethoughtDB Port Plan (Phased, Gate-Driven)

## 0) Objective

Port the `arangod` backend core to the new runtime while preserving backend and API behavior within the agreed scope:

- Include: backend services, storage integration interfaces, transactions, replication, cluster, admin APIs.
- Exclude in this phase: AQL internals, V8/Foxx runtime, UI behavior.
- Treat `RocksDBEngine` internals as verbatim/external; port interface and integration contracts.

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

## 2) Phase Plan

## Phase 1 — Program Setup and Baseline Freeze

### Goals

- Establish scope lock, success criteria, and artifact ownership.
- Freeze baseline test and API contracts for parity measurement.

### Checklist

- [ ] Scope document approved (in-scope/out-of-scope).
- [ ] Architecture spec copied/approved in this worktree.
- [ ] Validation matrix version pinned.
- [ ] Runbook approved by backend, cluster, storage, release owners.
- [ ] Baseline commit SHA tagged for parity comparison.

### Exit Gate

- [ ] All setup checklist items complete.
- [ ] Sign-off from architecture + release management.

---

## Phase 2 — Runtime Skeleton and Feature Lifecycle

### Goals

- Implement process bootstrap and feature graph lifecycle.
- Preserve startup dependency semantics and shutdown choreography.

### Checklist

- [ ] Feature phase orchestration implemented.
- [ ] Config collect/validate/prepare/start/stop lifecycle implemented.
- [ ] Role mode behavior implemented (`single`, `coordinator`, `dbserver`).
- [ ] Readiness/liveness semantics implemented.
- [ ] Startup/shutdown structured logging in place.

### Exit Gate

- [ ] Process boots and cleanly shuts down across target roles.
- [ ] Smoke tests pass for startup, config validation, and shutdown.

---

## Phase 3 — Transport and REST Dispatch Core

### Goals

- Implement REST handler factory semantics, API version handling, and route dispatch.

### Checklist

- [ ] Exact-path + prefix-path dispatch implemented.
- [ ] API version partitioning and unknown-version behavior implemented.
- [ ] Request suffix parsing and handler context propagation implemented.
- [ ] Standardized error envelope (`error`, `errorNum`, `errorMessage`) implemented.
- [ ] Multi-DB route context (`/_db/<name>/...`) implemented.

### Exit Gate

- [ ] Core admin/version/status routes pass compatibility checks.
- [ ] Route dispatch parity tests green.

---

## Phase 4 — Catalog and Storage Interfaces

### Goals

- Implement `VocBase`-equivalent catalog services and storage interface contracts.

### Checklist

- [ ] Database/collection/view/index metadata models implemented.
- [ ] DDL lifecycle operations implemented (create/change/rename/drop).
- [ ] Storage engine selector and engine lifecycle hooks implemented.
- [ ] Recovery state and capability/statistics exposure implemented.
- [ ] RocksDB integration interface wired (internals excluded from reimplementation).

### Exit Gate

- [ ] Catalog/DDL parity tests green.
- [ ] Storage interface tests green.

---

## Phase 5 — Transaction and Document Data Plane

### Goals

- Implement transaction orchestration and core document operations.

### Checklist

- [ ] Transaction begin/commit/abort/finish implemented.
- [ ] Collection enrollment and lock/access mode semantics implemented.
- [ ] CRUD paths implemented (`document`, `insert`, `update`, `replace`, `remove`, `truncate`).
- [ ] Revision/precondition/conflict behavior implemented.
- [ ] Async operation pathways implemented where required.

### Exit Gate

- [ ] Gate A transaction and document suites green.
- [ ] No unexplained regression in consistency/conflict semantics.

---

## Phase 6 — Auth, Security, and Admin Plane

### Goals

- Implement authentication/authorization and administrative API behavior.

### Checklist

- [ ] Token auth and user manager implemented.
- [ ] Root user bootstrap behavior implemented.
- [ ] Auth reload and permission checks implemented.
- [ ] Admin APIs in scope implemented (`status`, `server`, `log`, `metrics`, `shutdown`, etc.).
- [ ] Security defaults and UTF-8/input validation policy implemented.

### Exit Gate

- [ ] Gate A auth/admin suites green.
- [ ] No policy bypass regressions.

---

## Phase 7 — Cluster, Agency, Replication, Replication2

### Goals

- Implement distributed correctness paths and operational coordination.

### Checklist

- [ ] Cluster topology state and heartbeat behaviors implemented.
- [ ] Agency CAS and callback patterns implemented.
- [ ] Maintenance and shard leadership flows implemented.
- [ ] Legacy replication sync/applier behaviors implemented.
- [ ] Replication2 log/state-machine APIs implemented (feature-gated).

### Exit Gate

- [ ] Gate B replication/cluster/resilience/restart suites green.
- [ ] No unexplained replication correctness regressions.

---

## Phase 8 — Observability and Operational Hardening

### Goals

- Complete metrics/statistics/system-monitor coverage and operational diagnostics.

### Checklist

- [ ] Metrics families emitted for server/scheduler/replication/cluster.
- [ ] Statistics endpoints and request accounting aligned.
- [ ] Crash/reporting artifacts capture integrated.
- [ ] Runbook artifact collection paths validated.
- [ ] Flake detection and retry policies established.

### Exit Gate

- [ ] Gate A/B observability suites green.
- [ ] Operational dashboards and alerts validated.

---

## Phase 9 — Ecosystem Compatibility and Certification

### Goals

- Validate external client ecosystem behavior and sign-off for release.

### Checklist

- [ ] `tests/arangojs.yml` executed and passing (or waived with risk acceptance).
- [ ] `tests/go.yml` executed and passing.
- [ ] `tests/java.yml` executed and passing.
- [ ] `tests/py.yml` and `tests/py-async.yml` executed and passing.
- [ ] `tests/kafka.yml`, `tests/spark-ds.yml`, `tests/spring-data.yml`, `tests/tinkerpop.yml` executed and passing.
- [ ] Gate C runs documented (AQL/V8/UI) with exclusion-only failures.

### Exit Gate

- [ ] Certification packet complete (artifacts + waiver ledger + sign-offs).
- [ ] Final validity decision == VALID (per runbook decision rule).

---

## 3) Cross-Phase Quality Gates

These apply in every phase after initial bootstrap:

- [ ] No new unexplained regression in previously green in-scope suites.
- [ ] Required artifacts produced and archived for each run.
- [ ] Risk register updated for blocking failures.
- [ ] Waivers (if any) include owner, due date, mitigation, rollback.

---

## 4) Deliverables by Milestone

### M1 (end Phase 3)

- [ ] Runtime + transport skeleton complete.
- [ ] Baseline API dispatch behavior verified.

### M2 (end Phase 5)

- [ ] Core backend data plane complete.
- [ ] Gate A mostly green except tracked residuals.

### M3 (end Phase 7)

- [ ] Distributed behavior complete.
- [ ] Gate B near-green with no correctness blockers.

### M4 (end Phase 9)

- [ ] Ecosystem compatibility complete.
- [ ] Final release certification complete.

---

## 5) Sign-Off

Required approvals:

- [ ] Backend port lead
- [ ] Storage/transaction owner
- [ ] Cluster/replication owner
- [ ] SRE/operations owner
- [ ] Release manager

Release is not certified until all required approvers sign off.
