# arangod Port Validation Runbook

## 1. Purpose

This runbook operationalizes the validation contract in `Documentation/Architecture/arangod-port-validation-matrix.yml`.

Use this document to execute certification runs and determine whether the backend port is valid for release in the current project phase.

---

## 2. Inputs and Source of Truth

- Validation matrix: `Documentation/Architecture/arangod-port-validation-matrix.yml`
- Backend specification: `Documentation/Architecture/arangod-backend-port-spec.md`
- Core suite manifest: `tests/tests.yml`
- External manifests: `tests/*.yml`
- JS harness runner: `scripts/unittest` (Linux/macOS), `scripts/unittest.ps1` (Windows)
- C++ test registration: `tests/CMakeLists.txt`

---

## 3. Certification Outcomes

## 3.1 Valid

Port is **Valid** when:

1. all Gate A (blocking) items pass,
2. all Gate B (blocking) items pass,
3. Gate C failures are only in declared excluded areas (`AQL`, `V8/Foxx`, `UI`),
4. no unexplained regressions in storage, transaction, replication, or admin APIs.

## 3.2 Conditionally Valid

Port is **Conditionally Valid** only when blocking failures have approved waivers with:

- root-cause analysis,
- containment/risk statement,
- owner and due date,
- rollback path.

## 3.3 Invalid

Any unresolved Gate A/B failure, or unexplained non-exclusion regression.

---

## 4. Environment Preconditions

Before any run:

1. Record commit SHA and branch.
2. Build server and test binaries.
3. Ensure runtime topology support for `single`, `cluster`, `mixed` test modes.
4. Ensure report directories are writable.
5. Ensure external dependency environments (driver/kafka/spark/etc.) are reachable for ecosystem manifests.

---

## 5. Ordered Execution Plan

Execute in this order to fail fast on core regressions.

## Phase 1 — Core Binary Tests (Gate A)

Run C++ test binary first:

1. `arangodbtests` default profile (`--gtest_filter=-*_LongRunning` where configured)
2. `arangodbtests` full profile
3. optional partition profiles (`iresearch`, `non-iresearch`) when used by CI

If Phase 1 fails, stop and triage before proceeding.

## Phase 2 — Core CI Groups from `tests/tests.yml`

Run all Gate A group entries from the matrix:

- single-server and mixed backend suites,
- auth/config/permissions/api-path stability suites,
- non-excluded backend suites.

Stop on first reproducible Gate A failure.

## Phase 3 — Distributed/Operational Groups (Gate B)

Run Gate B group entries:

- replication families,
- recovery families,
- resilience/cluster/restart/load-balancing,
- dump/hot-backup/traffic operational coverage.

All Gate B failures are blocking unless waived.

## Phase 4 — Ecosystem Manifests (Gate B)

Run external manifests listed in the matrix:

- `tests/arangojs.yml`, `tests/go.yml`, `tests/java.yml`,
- `tests/py.yml`, `tests/py-async.yml`, `tests/kafka.yml`,
- `tests/spark-ds.yml`, `tests/spring-data.yml`, `tests/tinkerpop.yml`.

## Phase 5 — Informational Scope (Gate C)

Run Gate C where useful for observability:

- AQL-heavy suites,
- V8/Foxx suites,
- UI automation (`tests/ui.yml`).

Gate C results are non-blocking if failures stay within declared exclusions.

---

## 6. Execution Commands (Reference)

## 6.1 JS Harness

Windows:

`./scripts/unittest.ps1 <suite-or-group> --build <build-dir>`

Linux/macOS:

`./scripts/unittest <suite-or-group> --build <build-dir>`

Examples:

- `./scripts/unittest shell_client --build build`
- `./scripts/unittest replication_shell --build build`

## 6.2 C++ gtest Binary

`<build-dir>/bin/arangodbtests --gtest_output=xml`

Example partition:

`<build-dir>/bin/arangodbtests --gtest_output=xml --gtest_filter=IResearch*`

---

## 7. Required Artifacts Per Run

Each run must emit:

- test identifier (group/suite/manifest),
- gate (`A|B|C`),
- deployment mode (`single|cluster|mixed`),
- start/end timestamps,
- pass/fail status,
- failing tests list,
- logs and JUnit/XML references,
- crash dumps (if any),
- retry count and flake annotation.

Recommended output layout:

- `artifacts/validation/<date>/<commit>/gate-A/...`
- `artifacts/validation/<date>/<commit>/gate-B/...`
- `artifacts/validation/<date>/<commit>/gate-C/...`

---

## 8. Failure Triage Protocol

For each failure:

1. Reproduce once in same environment.
2. Classify as deterministic, flaky, or environment-induced.
3. Map to scope class:
   - in-scope backend,
   - declared exclusion (`AQL|V8|UI`),
   - infrastructure issue.
4. Record owner and issue ID.
5. Decide: fix now, quarantine with waiver, or block release.

---

## 9. Waiver Rules (Blocking Gates)

Blocking gate waivers require:

- explicit risk acceptance by release owner,
- mitigation or rollback documented,
- target fix milestone,
- no data-integrity or replication-correctness risk.

Waivers must be captured adjacent to the matrix and referenced in release notes.

---

## 10. Final Sign-Off Checklist

Before declaring validity:

- [ ] Matrix version and commit SHA recorded.
- [ ] All Gate A groups green.
- [ ] All Gate B groups/manifests green or formally waived.
- [ ] Gate C failures limited to declared exclusions.
- [ ] No unresolved unexplained regressions in backend control/data planes.
- [ ] Artifacts archived and linked from release ticket.

---

## 11. Ownership

- Primary owner: backend port lead.
- Required approvers: storage/replication owner, cluster owner, release manager.

Sign-off is invalid without all required approvers.
