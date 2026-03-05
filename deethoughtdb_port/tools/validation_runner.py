from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass


@dataclass(slots=True)
class SuiteSpec:
    name: str
    gate: str
    command: list[str]


@dataclass(slots=True)
class GateDef:
    code: str
    name: str
    blocking: bool


@dataclass(slots=True)
class MatrixSectionItem:
    section: str
    gate: str
    name: str


@dataclass(slots=True)
class ManifestDef:
    file: str
    gate: str
    required: bool


def _default_suites() -> list[SuiteSpec]:
    return [
        SuiteSpec(
            name="unit-core",
            gate="A",
            command=[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        ),
        SuiteSpec(
            name="live-rocksdb",
            gate="B",
            command=[
                sys.executable,
                "-m",
                "unittest",
                "tests.test_live_rocksdb_integration",
                "-v",
            ],
        ),
    ]


def _default_matrix_path() -> pathlib.Path:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    return repo_root / "Documentation" / "Architecture" / "arangod-port-validation-matrix.yml"


def _load_matrix_gates(matrix_path: pathlib.Path) -> dict[str, GateDef]:
    if not matrix_path.exists():
        raise FileNotFoundError(f"matrix file not found: {matrix_path}")

    lines = matrix_path.read_text(encoding="utf-8").splitlines()
    in_gates = False
    current_code: str | None = None
    name_by_code: dict[str, str] = {}
    blocking_by_code: dict[str, bool] = {}

    gate_header = re.compile(r"^\s{2}([A-Z]):\s*$")
    name_line = re.compile(r"^\s{4}name:\s+(.+)$")
    blocking_line = re.compile(r"^\s{4}blocking:\s+(true|false)\s*$")

    for line in lines:
        if not in_gates:
            if line.strip() == "gates:":
                in_gates = True
            continue

        # end gates block when indentation returns to top-level key
        if line and not line.startswith(" "):
            break

        gate_match = gate_header.match(line)
        if gate_match:
            current_code = gate_match.group(1)
            continue

        if current_code is None:
            continue

        name_match = name_line.match(line)
        if name_match:
            name_by_code[current_code] = name_match.group(1).strip()
            continue

        blocking_match = blocking_line.match(line)
        if blocking_match:
            blocking_by_code[current_code] = blocking_match.group(1) == "true"

    gates: dict[str, GateDef] = {}
    for code, gate_name in name_by_code.items():
        gates[code] = GateDef(
            code=code,
            name=gate_name,
            blocking=blocking_by_code.get(code, False),
        )

    if not gates:
        raise ValueError(f"no gates parsed from matrix: {matrix_path}")
    return gates


def _load_matrix_section_items(matrix_path: pathlib.Path, section: str) -> list[MatrixSectionItem]:
    lines = matrix_path.read_text(encoding="utf-8").splitlines()
    in_section = False
    current_name: str | None = None
    items: list[MatrixSectionItem] = []

    section_header = f"{section}:"
    name_line = re.compile(r"^\s{2}-\s+name:\s+(.+)$")
    file_line = re.compile(r"^\s{2}-\s+file:\s+(.+)$")
    gate_line = re.compile(r"^\s{4}gate:\s+([A-Z])\s*$")

    for line in lines:
        if not in_section:
            if line.strip() == section_header:
                in_section = True
            continue

        if line and not line.startswith(" "):
            break

        name_match = name_line.match(line)
        if name_match:
            current_name = name_match.group(1).strip()
            continue

        file_match = file_line.match(line)
        if file_match:
            current_name = file_match.group(1).strip()
            continue

        gate_match = gate_line.match(line)
        if gate_match and current_name:
            items.append(
                MatrixSectionItem(
                    section=section,
                    gate=gate_match.group(1),
                    name=current_name,
                )
            )

    return items


def _matrix_gate_distribution(items: list[MatrixSectionItem], gates: dict[str, GateDef]) -> list[dict]:
    counts: dict[str, int] = {gate: 0 for gate in gates.keys()}
    for item in items:
        if item.gate in counts:
            counts[item.gate] += 1

    return [
        {
            "gate": gate,
            "gateName": gates[gate].name,
            "count": counts[gate],
        }
        for gate in sorted(gates.keys())
    ]


def _load_manifest_defs(matrix_path: pathlib.Path) -> list[ManifestDef]:
    lines = matrix_path.read_text(encoding="utf-8").splitlines()
    in_section = False
    current_file: str | None = None
    current_gate: str | None = None
    current_required: bool | None = None
    manifests: list[ManifestDef] = []

    file_line = re.compile(r"^\s{2}-\s+file:\s+(.+)$")
    gate_line = re.compile(r"^\s{4}gate:\s+([A-Z])\s*$")
    required_line = re.compile(r"^\s{4}required:\s+(true|false)\s*$")

    for line in lines:
        if not in_section:
            if line.strip() == "manifests:":
                in_section = True
            continue

        if line and not line.startswith(" "):
            break

        file_match = file_line.match(line)
        if file_match:
            if current_file and current_gate and current_required is not None:
                manifests.append(
                    ManifestDef(file=current_file, gate=current_gate, required=current_required)
                )
            current_file = file_match.group(1).strip()
            current_gate = None
            current_required = None
            continue

        gate_match = gate_line.match(line)
        if gate_match:
            current_gate = gate_match.group(1)
            continue

        required_match = required_line.match(line)
        if required_match:
            current_required = required_match.group(1) == "true"

    if current_file and current_gate and current_required is not None:
        manifests.append(ManifestDef(file=current_file, gate=current_gate, required=current_required))

    return manifests


def _required_manifests_by_gate(manifests: list[ManifestDef], gates: dict[str, GateDef]) -> list[dict]:
    counts: dict[str, int] = {gate: 0 for gate in gates.keys()}
    for manifest in manifests:
        if manifest.required and manifest.gate in counts:
            counts[manifest.gate] += 1
    return [
        {
            "gate": gate,
            "gateName": gates[gate].name,
            "requiredCount": counts[gate],
        }
        for gate in sorted(gates.keys())
    ]


def _git_metadata(repo_root: pathlib.Path) -> dict:
    def _run(*args: str) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            return "unknown"
        return proc.stdout.strip() or "unknown"

    return {
        "commit": _run("rev-parse", "HEAD"),
        "branch": _run("rev-parse", "--abbrev-ref", "HEAD"),
    }


def run_suite(spec: SuiteSpec, env: dict[str, str]) -> dict:
    started = dt.datetime.now(dt.UTC)
    proc = subprocess.run(
        spec.command,
        cwd=str(pathlib.Path(__file__).resolve().parents[1]),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    ended = dt.datetime.now(dt.UTC)

    return {
        "suite": spec.name,
        "gate": spec.gate,
        "command": spec.command,
        "startedAt": started.isoformat(),
        "endedAt": ended.isoformat(),
        "durationSec": round((ended - started).total_seconds(), 3),
        "exitCode": proc.returncode,
        "status": "pass" if proc.returncode == 0 else "fail",
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def classify_retry_result(attempts: list[dict]) -> dict:
    if not attempts:
        return {"status": "fail", "flaky": False, "attempts": 0}

    final_status = attempts[-1]["status"]
    seen_fail = any(item["status"] == "fail" for item in attempts)
    seen_pass = any(item["status"] == "pass" for item in attempts)
    flaky = final_status == "pass" and seen_fail and seen_pass
    return {
        "status": final_status,
        "flaky": flaky,
        "attempts": len(attempts),
    }


def run_suite_with_retries(spec: SuiteSpec, env: dict[str, str], retries: int) -> dict:
    attempt_results: list[dict] = []
    max_attempts = max(1, retries + 1)

    for _ in range(max_attempts):
        result = run_suite(spec, env)
        attempt_results.append(result)
        if result["status"] == "pass":
            break

    classification = classify_retry_result(attempt_results)
    final = dict(attempt_results[-1])
    final["attemptResults"] = [
        {
            "status": item["status"],
            "exitCode": item["exitCode"],
            "durationSec": item["durationSec"],
            "startedAt": item["startedAt"],
            "endedAt": item["endedAt"],
        }
        for item in attempt_results
    ]
    final["attemptCount"] = classification["attempts"]
    final["flaky"] = classification["flaky"]
    final["status"] = classification["status"]
    final["exitCode"] = 0 if classification["status"] == "pass" else final["exitCode"]
    final["stdoutByAttempt"] = [item["stdout"] for item in attempt_results]
    final["stderrByAttempt"] = [item["stderr"] for item in attempt_results]
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deethoughtdb_port validation suites")
    parser.add_argument(
        "--output-dir",
        default="artifacts/validation/gate-runner",
        help="directory for run artifacts",
    )
    parser.add_argument(
        "--matrix",
        default=str(_default_matrix_path()),
        help="path to arangod-port-validation-matrix.yml",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help="number of retries per suite after initial failure",
    )
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = pathlib.Path(__file__).resolve().parents[1] / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    matrix_path = pathlib.Path(args.matrix)
    if not matrix_path.is_absolute():
        matrix_path = pathlib.Path(__file__).resolve().parents[1] / matrix_path
    gates = _load_matrix_gates(matrix_path)
    manifest_items = _load_matrix_section_items(matrix_path, "manifests")
    manifest_defs = _load_manifest_defs(matrix_path)
    core_ci_items = _load_matrix_section_items(matrix_path, "coreCiGroups")
    repo_root = pathlib.Path(__file__).resolve().parents[2]

    env = os.environ.copy()
    env.setdefault("PYTHONPATH", "src")

    results = []
    suites = _default_suites()
    unknown_gate_suites = [suite.name for suite in suites if suite.gate not in gates]
    if unknown_gate_suites:
        raise ValueError(
            "suite(s) reference undefined gate(s): " + ", ".join(unknown_gate_suites)
        )

    for suite in suites:
        results.append(run_suite_with_retries(suite, env, retries=args.retries))

    blocking_failures = [
        result
        for result in results
        if result["status"] == "fail" and gates[result["gate"]].blocking
    ]

    summary = {
        "generatedOn": dt.datetime.now(dt.UTC).isoformat(),
        "matrixPath": str(matrix_path),
        "git": _git_metadata(repo_root),
        "overall": "pass" if not blocking_failures else "fail",
        "retryPolicy": {
            "retries": max(0, int(args.retries)),
            "maxAttempts": max(1, int(args.retries) + 1),
            "flakeDetection": True,
        },
        "flakes": [r["suite"] for r in results if r.get("flaky")],
        "results": [
            {
                "suite": r["suite"],
                "gate": r["gate"],
                "gateName": gates[r["gate"]].name,
                "gateBlocking": gates[r["gate"]].blocking,
                "status": r["status"],
                "durationSec": r["durationSec"],
                "exitCode": r["exitCode"],
                "attemptCount": r.get("attemptCount", 1),
                "flaky": bool(r.get("flaky", False)),
            }
            for r in results
        ],
        "matrixCoverage": {
            "manifestsByGate": _matrix_gate_distribution(manifest_items, gates),
            "requiredManifestsByGate": _required_manifests_by_gate(manifest_defs, gates),
            "coreCiGroupsByGate": _matrix_gate_distribution(core_ci_items, gates),
        },
    }

    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for result in results:
        safe_name = result["suite"].replace("/", "_")
        (output_dir / f"{safe_name}.stdout.log").write_text(result["stdout"], encoding="utf-8")
        (output_dir / f"{safe_name}.stderr.log").write_text(result["stderr"], encoding="utf-8")
        for attempt_index, content in enumerate(result.get("stdoutByAttempt", []), start=1):
            (output_dir / f"{safe_name}.attempt{attempt_index}.stdout.log").write_text(
                content,
                encoding="utf-8",
            )
        for attempt_index, content in enumerate(result.get("stderrByAttempt", []), start=1):
            (output_dir / f"{safe_name}.attempt{attempt_index}.stderr.log").write_text(
                content,
                encoding="utf-8",
            )

    return 0 if summary["overall"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
