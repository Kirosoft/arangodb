# arangod Backend Port Specification (AQL-Excluded, UI-Excluded)

## 1. Purpose

This document specifies the backend implementation and API-layer requirements for porting `arangod` core engine logic to a new language/runtime (candidate: Python), while:

- **excluding AQL implementation details**, planners, optimizers, and execution internals,
- **excluding UI/web frontend concerns**,
- **excluding RocksDB internal reimplementation** (RocksDB is treated as a verbatim engine implementation behind a stable interface).

The target is a production-grade backend service that preserves core database, transaction, replication, cluster, and administrative behavior.

---

## 2. Scope and Non-Scope

## 2.1 In Scope

- Server lifecycle and feature orchestration (`RestServer`, `FeaturePhases`, `GeneralServer` integration).
- Database/catalog management (`VocBase`, `DatabaseFeature`, `SystemDatabaseFeature`).
- Collection/view/index lifecycle management (minus AQL-specific planning logic).
- Document CRUD path and transaction orchestration.
- Authentication/authorization management (`Auth`, request auth enforcement).
- REST API layer and request handler architecture.
- Replication/cluster control planes (`Replication`, `Replication2`, `Cluster`, `Agency` interactions).
- Scheduler, request lanes, async job handling, background services.
- Metrics/statistics, health, startup/shutdown, recovery state handling.

## 2.2 Explicitly Out of Scope

- AQL language parser, optimizer, execution engine internals (`Aql` module internals).
- JS/Foxx/V8-based extension runtime and UI-serving behavior.
- Web UI endpoints that exist solely for browser UI affordances.
- Storage internals of RocksDB (`RocksDBEngine` internals), except interface and integration contracts.

## 2.3 RocksDB Treatment

RocksDBEngine is **ported verbatim where possible**, and this spec defines only:

- required interface shape,
- lifecycle hooks,
- health/recovery/capability exposure,
- API wiring and runtime interactions.

---

## 3. Baseline Decomposition of arangod

## 3.1 Runtime Boot and Feature Graph

The backend process must preserve `arangod`’s staged feature graph semantics:

- Feature phases (agency, communication, cluster, database, final, server, optional V8).
- Ordered startup dependency resolution.
- Config collection, validation, prepare/start, graceful shutdown.

Representative bootstrap evidence:

- `RestServer/arangod.cpp`: process main, feature registration and sequence.
- `FeaturePhases/*`: startup phase ordering.
- `RestServer/ServerFeature.cpp`: operation-mode logic and startup gating.

## 3.2 Core Module Families to Port

- `GeneralServer`: transport acceptors, HTTP/H2 comm tasks, rest dispatch factory.
- `RestHandler`: concrete API handlers.
- `RestServer`: process/bootstrap/server feature controls.
- `VocBase`: database, collection/view metadata and identities.
- `StorageEngine`: engine abstraction and recovery contracts.
- `Transaction`: transaction context/state/methods/manager.
- `Cluster`: topology state, maintenance, heartbeat, agency callbacks.
- `Replication` + `Replication2`: legacy and replicated-log state machines.
- `Agency` / `Zkd`: agency interactions and distributed coordination.
- `Auth`: users/tokens/auth cache and manager.
- `Scheduler`: work queue and threadpool orchestration.
- `Network`: outbound cluster/internal HTTP facilities.
- `Metrics` + `Statistics` + `SystemMonitor`: observability and health.
- `Sharding`, `Indexes`, `Graph`, `GeoIndex`, `IResearch` integration points.

## 3.3 arangod Directory Port Matrix

| Subdirectory | Port Status | Required Outcome | Notes |
|---|---|---|---|
| `Actions` | Port | Action dispatch and catch-all action handler support | Needed for fallback and legacy action APIs |
| `Agency` | Port | Agency client/server coordination, CAS ops, supervision state updates | Critical for cluster bootstrap and maintenance |
| `Aql` | Exclude internals | Only compatibility stubs/capability flags where needed | No parser/optimizer/executor port in this phase |
| `Auth` | Port | User model, token cache, user manager, auth helpers | Mandatory for secured deployments |
| `Cache` | Port | Cache options/manager integration points used by storage and indexes | Keep behavior-compatible settings |
| `Cluster` | Port | Topology state, heartbeat, maintenance, shard leadership flows | Required for coordinator/DBServer behavior |
| `ClusterEngine` | Port | Cluster storage facade and cluster REST integration | Keep as adapter over selected storage engine |
| `FeaturePhases` | Port | Startup dependency phases and ordering enforcement | Must preserve deterministic boot graph |
| `GeneralServer` | Port | Listener setup, protocol handling, REST dispatch factory | Foundation of all backend APIs |
| `GeoIndex` | Port | Geospatial index abstractions/integration | Keep API and index lifecycle semantics |
| `Graph` | Port | Graph metadata and non-AQL graph REST operations | Traversal query internals remain out if AQL-bound |
| `Indexes` | Port | Index definitions, validation, factories (except RocksDB internals) | Preserve index metadata contracts |
| `InternalRestHandler` | Port | Internal REST services needed for backend runtime | Include only non-UI backend uses |
| `IResearch` | Port (integration) | Analyzer/search view backend hooks and APIs | Keep handler compatibility; no UI dependencies |
| `Metrics` | Port | Metric registry/types/export interfaces | Required for observability and SRE operations |
| `Network` | Port | Internal HTTP client/pooling and cluster request forwarding | Needed by cluster/replication/admin forwarding |
| `Replication` | Port | Legacy replication syncer/applier flows | Required for compatibility and migration |
| `Replication2` | Port | Replicated log/state machine framework and APIs | Feature-gated enablement required |
| `RestHandler` | Port | Endpoint handler implementations in scope | AQL handlers can be disabled/stubbed |
| `RestServer` | Port | Process bootstrap, server mode controls, global features | Owns readiness and startup orchestration |
| `RocksDBEngine` | Interface only | Keep lifecycle/API integration contract only | Internal engine logic treated as verbatim/external |
| `Scheduler` | Port | Thread pool/scheduler/request lane execution model | Must preserve backpressure and fairness semantics |
| `Sharding` | Port | Shard distribution strategy/reporting | Required for cluster correctness |
| `Statistics` | Port | Request/server statistics and worker updates | Align with metrics endpoints |
| `StorageEngine` | Port | Engine abstraction and selector feature | Core seam for RocksDB and future engines |
| `SystemMonitor` | Port | System health probes and host diagnostics | Required by admin/system-report APIs |
| `Transaction` | Port | Transaction manager/state/context/methods | Critical data consistency surface |
| `Utils` | Port (selective) | Shared backend utility primitives | Include only backend-runtime dependencies |
| `V8Server` | Exclude | No JS runtime/Foxx/UI layer in this phase | Keep compile/runtime guards |
| `VocBase` | Port | Database/catalog core entities and lifecycle | Canonical metadata and object model |
| `Zkd` | Port | Agency/ZK-derived coordination utilities | Keep role-based distributed behavior |

---

## 4. Target Architecture for New Runtime

## 4.1 Architectural Style

Adopt a layered modular monolith:

1. **Process & Feature Lifecycle Layer**
2. **Transport/REST Dispatch Layer**
3. **Domain Services Layer** (DB/catalog/transactions/replication)
4. **Storage Abstraction Layer**
5. **Cluster Coordination Layer**
6. **Observability & Admin Layer**

Hard rule: handlers must call domain services, not engine internals directly.

## 4.2 Runtime Model (Python candidate)

Recommended runtime blueprint if Python is selected:

- `asyncio` event loop for IO-bound operations.
- Dedicated worker pool for blocking CPU/storage operations.
- Explicit request-lane scheduler mapping (fast/admin/background/document-heavy).
- Backpressure and queue depth enforcement.
- Graceful cancellation and shutdown barriers for long-running operations.

## 4.3 Process Topology

Single `arangod` process role modes:

- Single-server
- Coordinator
- DBServer
- Agency role interactions

Role-dependent feature enabling/disabling must be retained.

---

## 5. Feature Lifecycle Specification

Each feature component must implement:

- `collect_options(config_registry)`
- `validate_options(config)`
- `prepare(runtime_context)`
- `start()`
- `begin_shutdown()`
- `stop()/unprepare()`

Constraints:

- Startup order is deterministic.
- Feature dependencies are declarative.
- Fatal option mismatch blocks startup.
- Recovery/upgrade mode may disable regular endpoints.

---

## 6. API Layer Specification

## 6.1 API Dispatch and Versioning

Maintain factory semantics analogous to `RestHandlerFactory`:

- Exact path handlers and prefix handlers.
- API version partition (`v0`, `v1`, experimental).
- Longest-prefix route matching.
- Request suffix extraction for path args.

Error behavior:

- Unknown API version -> `404` with explicit version/path message.
- Unknown endpoint -> catch-all handler path.

## 6.2 Core Endpoint Families (Backend)

The port must support backend APIs represented by current handler classes, grouped as:

### Data Plane

- `/_api/database`
- `/_api/collection`
- `/_api/document`
- `/_api/edges`
- `/_api/index`
- `/_api/import`
- `/_api/view`
- `/_api/transaction`

### Control Plane

- `/_api/engine`
- `/_api/replication`
- `/_api/wal`
- `/_api/job`
- `/_api/tasks` (if scripting/runtime support retained)
- `/_api/token`
- `/_api/user`

### Cluster/Distributed Plane

- `/_api/agency`
- `/_api/agency_priv`
- `/_admin/cluster`
- cluster callback endpoints
- replication2 log/document-state APIs when feature-enabled

### Admin/Operations

- `/_api/version`, `/_admin/version`, `/_admin/status`
- `/_admin/server`, `/_admin/statistics`, `/_admin/metrics`
- `/_admin/log`, `/_admin/system-report`
- `/_admin/shutdown`, `/_admin/time`, `/_admin/compact`
- `/_admin/options*` and policy-gated endpoints

## 6.3 AQL Endpoint Policy

Because AQL is out-of-scope:

- `/_api/aql`, `/_api/query`, `/_api/cursor`, `/_api/explain`, query caches, and AQL-function routes are **not required for functional parity in this port**.
- Provide one of:
  - hard-disabled endpoint registration, or
  - registered endpoints returning `501 Not Implemented` with machine-readable capability codes.

Required behavior: server capability metadata must announce AQL disabled state.

## 6.4 Multi-Database Routing

Maintain `/_db/<database>/...` routing behavior:

- request context includes resolved database object,
- authorization checks are database-scoped,
- cross-database operations forbidden unless explicitly defined.

## 6.5 Uniform Response/Error Contract

All handlers must return:

- HTTP code,
- JSON body with `error`, `errorNum`, `errorMessage` for failures,
- optional metadata headers (`etag`, `location`, async job IDs, etc.) where applicable.

---

## 7. Domain Model and Metadata Services

## 7.1 Database Model (`VocBase` equivalent)

Required entities:

- `Database` (id, name, options, state)
- `Collection` (id, name, type, sharding/index settings, status)
- `View` (id, name, type, properties)
- `Index` (id, type, fields, options, selectivity metadata)

Metadata service responsibilities:

- create/open/drop database,
- create/rename/change/drop collection,
- create/change/drop view,
- index registration and metadata validation,
- schema and key-generator policy enforcement.

## 7.2 Identity and Tick Semantics

Preserve monotonic identifiers and tick semantics for:

- database/collection/index IDs,
- transaction IDs,
- replication ticks and WAL cursoring.

---

## 8. Storage Engine Interface Contract (RocksDB Internals Excluded)

Implement an engine abstraction equivalent to `StorageEngine` with grouped contract sets:

## 8.1 Engine Lifecycle

- health check,
- startup/recovery state,
- shutdown synchronization,
- capabilities/statistics exposure.

## 8.2 Catalog/Inventory APIs

- enumerate databases,
- enumerate collections/indexes/views,
- read collection metadata,
- engine version file/path handling.

## 8.3 Database/Collection/View DDL

- open/create/drop database,
- create/change/rename/drop collection,
- create/change/drop view,
- compact database.

## 8.4 Transaction Integration

- create transaction manager,
- create transaction state,
- support snapshot/tick release and read visibility contracts.

## 8.5 Replication/WAL Integration

- replication applier configuration read/write/remove,
- logger state/tick ranges,
- WAL access adapter,
- replication context cleanup.

## 8.6 Required Non-Functional Guarantees

- DDL operations are crash-safe and rollback/cleanup aware on failure.
- Drop operations may stage logical deletion before physical deletion.
- Recovery state is externally queryable and monotonic.

---

## 9. Transaction Subsystem Specification

Implement a transaction subsystem equivalent to `transaction::Methods`, `Manager`, `Context`, and `TransactionState`.

## 9.1 Functional Coverage

- begin/commit/abort/finish (async-first API surface),
- collection enrollment and lock acquisition by access mode,
- document operations: `document`, `insert`, `update`, `replace`, `remove`, `truncate`, `count`, `all/any` patterns,
- status callbacks and operation-origin tracking.

## 9.2 Isolation and Consistency

- Preserve Arango-style transaction options semantics (single-op fast path, intermediate commit semantics where relevant, wait-for-sync semantics).
- Enforce write-write conflict detection and revision precondition checks.
- Ensure visibility rules are stable under concurrent operations.

## 9.3 Context Types

Support logical context specializations:

- standalone/local context,
- cluster context,
- replicated context (where replication2 requires).

---

## 10. Cluster and Replication Specification

## 10.1 Cluster Coordination (`Cluster`)

Port these capabilities:

- server role/state tracking,
- cluster info cache,
- agency callback registry,
- heartbeat and maintenance loops,
- collection/database/index DDL coordination across roles,
- shard leadership takeover/resign/synchronize operations.

## 10.2 Agency Interaction (`Agency`)

Required behavior:

- compare-and-swap value updates,
- bootstrap race handling,
- supervision-related key updates,
- robust retry/backoff in transient failure conditions.

## 10.3 Replication (legacy + replication2)

Implement backend contracts for:

- initial sync,
- tailing sync,
- applier state/configuration management,
- replicated log APIs and status polling,
- document-state APIs (if replication2 enabled).

Feature flags must permit disabling replication2 surfaces.

---

## 11. Networking, Scheduling, and Concurrency

## 11.1 Networking

- HTTP/1.1 and HTTP/2 request handling parity where practical.
- TLS endpoint support with runtime validation.
- Internal outbound connection pooling for cluster/agency forwarding.

## 11.2 Scheduling and Request Lanes

- Classify requests into lanes (fast/admin/slow/background).
- Ensure startup-early handlers run on fast lanes.
- Queue overflow policy and per-lane metrics required.

## 11.3 Async Jobs

- API-compatible async job manager behavior for job creation/list/get/delete.

---

## 12. Authentication, Authorization, and Security

## 12.1 Authentication

- Token-based auth support.
- User manager with root-user bootstrap behavior.
- Auth reload endpoint support.

## 12.2 Authorization

- DB/collection-level permission checks per request.
- Admin endpoint access gating.
- Role-sensitive restricted operations.

## 12.3 Security Controls

- strict input validation and UTF-8 policy option,
- redaction-safe error responses,
- secure defaults for TLS and auth-required deployments.

---

## 13. Observability and Operability

## 13.1 Metrics and Statistics

- Preserve metric families for server, scheduler, replication, agency/cluster health, and request stats.
- Provide admin metrics endpoint compatible with existing scraping expectations.

## 13.2 Logging

- Structured logging with topic/severity parity.
- Startup/shutdown and failure-path logs must remain diagnostic.

## 13.3 Health and Readiness

- Distinguish liveness from readiness.
- Readiness blocked until bootstrap/recovery dependencies are satisfied.

---

## 14. Recovery, Upgrade, and Shutdown

## 14.1 Recovery States

- Expose `before`, `in_progress`, `done` style recovery states.
- Startup behavior changes according to recovery/upgrade mode.

## 14.2 Upgrade/Bootstrap

- Support cluster bootstrap race handling and system DB bootstrap operations.
- Persist version/bootstrap markers to avoid repeated upgrade work.

## 14.3 Graceful Shutdown

- Stop accepting new requests,
- drain in-flight operations with timeout policy,
- flush logs/metrics,
- close network and engine resources in dependency-safe order.

---

## 15. Compatibility Requirements

## 15.1 API Compatibility Tiers

- **Tier 1 (must match):** core document/collection/database/admin/transaction/replication endpoints in scope.
- **Tier 2 (may differ with flag):** optional/experimental or enterprise-specific endpoints.
- **Tier 3 (explicitly unsupported):** AQL-related endpoints in this project phase.

## 15.2 Behavior Compatibility

- HTTP status code compatibility for successful and common failure cases.
- Error payload shape compatibility.
- Transactional and replication observable semantics compatibility.

---

## 16. Implementation Blueprint (Suggested)

## 16.1 Package Structure (Language-Agnostic)

- `core.lifecycle`
- `core.config`
- `transport.http`
- `api.handlers`
- `domain.catalog`
- `domain.documents`
- `domain.transactions`
- `domain.replication`
- `domain.cluster`
- `storage.engine`
- `storage.rocksdb_adapter`
- `security.auth`
- `scheduler`
- `observability.metrics`

## 16.2 Porting Order

1. Feature framework + process boot + config.
2. REST factory + request context + error contract.
3. VocBase/catalog services + storage interface.
4. Document/collection/index endpoints.
5. Transaction manager and document operations.
6. Auth/user/token management.
7. Cluster+agency baseline.
8. Replication (legacy), then replication2 features.
9. Metrics/statistics/admin hardening.

## 16.3 AQL Exclusion Handling

- Build-time flag: `AQL_ENABLED=false`.
- Route registration guard around AQL handlers.
- Capability endpoint must advertise disabled AQL features.

---

## 17. Validation and Acceptance Criteria

## 17.1 Functional Acceptance

- CRUD/document APIs pass compatibility suite.
- Collection/database/view/index lifecycle APIs pass.
- Transaction begin/commit/abort and conflict semantics pass.
- Replication and cluster control paths pass role-specific tests.

## 17.2 Non-Functional Acceptance

- Startup/shutdown reliability under fault injection.
- Throughput/latency SLOs within agreed envelope.
- Recovery correctness after crash simulation.
- Metrics/logging completeness for operational triage.

## 17.3 Backward-Compatibility Acceptance

- Existing clients using in-scope endpoints require no request/response schema changes.
- Unsupported endpoints fail explicitly and consistently.

## 17.4 Full Existing Test Suite Scope (`/tests`) and Port Validation Profile

This section defines the **authoritative validation scope** for the port based on the current repository test assets.

### 17.4.1 Authoritative Test Sources

The complete test universe is defined by:

- C++/gtest build and registration in `tests/CMakeLists.txt`.
- JS/integration test harness entrypoint in `scripts/unittest` and `scripts/unittest.ps1`, which execute `js/client/modules/@arangodb/testutils/unittest.js`.
- Main CI suite manifest `tests/tests.yml`.
- Additional ecosystem manifests under `tests/*.yml` (except `tests.yml`).

### 17.4.2 Repository Snapshot Metrics (Current Baseline)

Measured from current repository state:

- `tests_cpp_h = 609` files (`tests/**` with `.cpp`/`.h`).
- `gtest_cpp_files = 375` (`tests/**/**Test.cpp`).
- `tests_js = 1398` files (`tests/js/**/*.js`).
- `tests_yml = 11` files (`tests/*.yml`, including `tests.yml`).
- JS testsuite registry modules (`js/client/modules/@arangodb/testsuites/*.js`): `42`.

These counts are baseline observability metrics and should be refreshed at each release branch cut.

### 17.4.3 Complete Top-Level `/tests` Scope

The current `/tests` module buckets that define backend quality scope are:

- `Activities`, `Actor`, `Agency`, `Aql`, `Assertions`, `Async`, `AsyncAgencyComm`,
- `Auth`, `Basics`, `BuildId`, `Cache`, `Cluster`, `Containers`, `CrashHandler`,
- `Errors`, `Fuerte`, `Futures`, `Geo`, `Graph`, `Inspection`, `InternalRestHandler`,
- `IResearch`, `Logger`, `Maintenance`, `Metrics`, `Mocks`, `Network`,
- `ProgramOptions`, `Replication`, `Replication2`, `Rest`, `RestHandler`,
- `Restore`, `RestServer`, `RocksDBEngine`, `Scheduler`, `sepp`, `Sharding`,
- `SimpleHttpClient`, `StorageEngine`, `SystemMonitor`, `Transaction`, `Utils`,
- `V8Server`, `VocBase`, `Zkd`, plus `tests/js` (`client`, `common`, `server`, `transform`).

#### 17.4.3.1 Current Per-Directory Test File Baseline

Snapshot count of `*.cpp`, `*.js`, `*.py`, `*.yml` under each top-level `tests/<dir>`:

| Directory | File Count |
|---|---:|
| Activities | 4 |
| Actor | 6 |
| Agency | 14 |
| Aql | 89 |
| Assertions | 1 |
| Async | 3 |
| AsyncAgencyComm | 1 |
| Auth | 2 |
| Basics | 41 |
| BuildId | 1 |
| Cache | 17 |
| Cluster | 11 |
| Containers | 8 |
| CrashHandler | 1 |
| Errors | 2 |
| Fuerte | 6 |
| Futures | 4 |
| Geo | 5 |
| Graph | 18 |
| Inspection | 6 |
| InternalRestHandler | 1 |
| IResearch | 76 |
| js | 1404 |
| Logger | 2 |
| Maintenance | 3 |
| Metrics | 3 |
| Mocks | 11 |
| Network | 3 |
| ProgramOptions | 2 |
| Replication | 1 |
| Replication2 | 66 |
| Rest | 3 |
| RestHandler | 4 |
| Restore | 1 |
| RestServer | 2 |
| RocksDBEngine | 9 |
| Scheduler | 2 |
| sepp | 13 |
| Sharding | 1 |
| SimpleHttpClient | 2 |
| StorageEngine | 1 |
| SystemMonitor | 4 |
| Transaction | 4 |
| Utils | 4 |
| V8Server | 3 |
| VocBase | 17 |
| Zkd | 3 |

### 17.4.4 JS Testsuite Registry Scope (Harness-Registered)

Registered testsuite modules currently include:

- `agency`, `agency-restart`, `aql`, `arangobench`, `arangosh`, `audit`,
- `authentication`, `backup`, `chaos`, `communication`, `config`, `drivers`,
- `dump`, `endpoints`, `export`, `fail`, `foxxmanager`, `fuerte`, `fuzzer`,
- `go`, `gtest`, `hotbackup`, `importing`, `java`, `js`, `loadBalancing`,
- `paths_server`, `permissions_client`, `php`, `python-arango`,
- `queryCacheAuthorization`, `readOnly`, `recovery`, `recovery_server`,
- `replication`, `replication2`, `resilience`, `restart`, `rta_makedata`,
- `server_permissions`, `version`, `wal`.

### 17.4.5 YAML Manifest Scope (All `/tests/*.yml`)

All manifests that participate in CI/integration scope:

- Core backend suite orchestration: `tests/tests.yml`.
- Ecosystem/driver/platform suites:
  - `tests/arangojs.yml`
  - `tests/go.yml`
  - `tests/java.yml`
  - `tests/kafka.yml`
  - `tests/py.yml`
  - `tests/py-async.yml`
  - `tests/spark-ds.yml`
  - `tests/spring-data.yml`
  - `tests/tinkerpop.yml`
  - `tests/ui.yml`

### 17.4.6 Port-Validation Gating Model (Normative)

To declare the backend port valid, execute the full scope with explicit gate classes:

#### Gate A — **Required Pass (Backend Core)**

Must pass for release acceptance in this project phase:

- C++ unit/integration coverage equivalent for backend modules:
  - `Agency`, `Auth`, `Cache`, `Cluster`, `Graph` (non-AQL-bound behaviors),
  - `Maintenance`, `Metrics`, `Network`, `Replication`, `Replication2`,
  - `Rest`, `RestHandler`, `RestServer`, `RocksDBEngine` interface-level tests,
  - `Scheduler`, `Sharding`, `StorageEngine`, `SystemMonitor`, `Transaction`,
  - `Utils`, `VocBase`, `Zkd`, plus foundational `Basics/Containers/Errors/Assertions`.
- JS/integration suites from `tests/tests.yml` that validate backend APIs and cluster behavior excluding explicit AQL/UI/V8 exclusions.

#### Gate B — **Required Pass (Distributed + Operational)**

Must pass before cluster-production readiness sign-off:

- `replication_*`, `cluster_resilience`, `restart`, `load_balancing`,
- recovery families (`recovery`, `recovery_server`, `recovery_cluster`),
- admin/auth/endpoints/import/export/agency suites,
- dump/restore and hot-backup suites that do not depend on excluded components.

#### Gate C — **Informational / Deferred in This Phase**

Run and report, but non-blocking for this phase because out-of-scope features are intentionally excluded:

- AQL-focused suites and AQL-heavy tests (`tests/Aql`, `shell_client_aql*`, query/cursor/explain coverage).
- `V8Server` and Foxx/JS runtime-dependent suites.
- UI automation in `tests/ui.yml`.

Driver/ecosystem manifests (`arangojs`, `go`, `java`, `py`, `py-async`, `kafka`, `spark-ds`, `spring-data`, `tinkerpop`) are:

- **recommended release gates** once API compatibility stabilizes,
- **mandatory** for declaring client-ecosystem compatibility parity.

### 17.4.7 Execution Matrix for Port Certification

Certification requires recorded results for:

1. `arangodbtests` (default and full mode), including split runs where used (`iresearch`, `non-iresearch`).
2. `scripts/unittest` suites defined in `tests/tests.yml` across single/mixed/cluster configurations.
3. All external manifest suites in `tests/*.yml` (or explicit waiver with rationale).

For each suite run, capture:

- commit SHA,
- runtime profile (single/cluster/mixed),
- pass/fail,
- known exclusions category (AQL/V8/UI),
- flakiness/timeout notes,
- artifact links (logs, junit/xml, crash dumps).

### 17.4.8 Validity Decision Rule

A port build is **valid for backend phase acceptance** when:

- Gate A and Gate B suites are green,
- Gate C failures are only in documented excluded capability areas,
- no unexplained regressions in replication, transaction, storage, or admin API families,
- and ecosystem/driver suites are either green or have approved temporary waivers.

---

## 18. Risks and Mitigations

## 18.1 Concurrency Mismatch Risk (if Python)

Mitigation:

- strict async boundaries,
- worker pools for blocking work,
- explicit lock ownership and transaction serialization where required.

## 18.2 Behavioral Drift Risk

Mitigation:

- golden-response tests against current `arangod`,
- differential fuzzing for document/transaction APIs,
- API contract tests per endpoint family.

## 18.3 Cluster/Replication Complexity Risk

Mitigation:

- phase rollout (single-server first),
- shadow-mode replication validation,
- aggressive instrumentation in leadership and heartbeat paths.

---

## 19. Deliverables for This Project Phase

1. Backend architecture document (this file).
2. Machine-readable validation matrix: `Documentation/Architecture/arangod-port-validation-matrix.yml`.
3. Validation execution runbook: `Documentation/Architecture/arangod-port-validation-runbook.md`.
4. Engine interface contract spec package.
5. REST API compatibility matrix (in-scope vs excluded).
6. Conformance test plan and baseline fixtures.
7. Migration execution plan with milestones and rollback strategy.

---

## 20. Final Boundary Statement

This specification defines the full backend implementation and API layers for `arangod` porting, with a strict boundary:

- **Yes:** core backend engine orchestration, storage integration interface, transactions, cluster/replication, and admin APIs.
- **No:** AQL internals, UI/web frontend behavior, and RocksDB internal algorithmic reimplementation.
