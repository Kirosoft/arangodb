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
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = pathlib.Path(__file__).resolve().parents[1] / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    matrix_path = pathlib.Path(args.matrix)
    if not matrix_path.is_absolute():
        matrix_path = pathlib.Path(__file__).resolve().parents[1] / matrix_path
    gates = _load_matrix_gates(matrix_path)

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
        results.append(run_suite(suite, env))

    blocking_failures = [
        result
        for result in results
        if result["status"] == "fail" and gates[result["gate"]].blocking
    ]

    summary = {
        "generatedOn": dt.datetime.now(dt.UTC).isoformat(),
        "matrixPath": str(matrix_path),
        "overall": "pass" if not blocking_failures else "fail",
        "results": [
            {
                "suite": r["suite"],
                "gate": r["gate"],
                "gateName": gates[r["gate"]].name,
                "gateBlocking": gates[r["gate"]].blocking,
                "status": r["status"],
                "durationSec": r["durationSec"],
                "exitCode": r["exitCode"],
            }
            for r in results
        ],
    }

    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for result in results:
        safe_name = result["suite"].replace("/", "_")
        (output_dir / f"{safe_name}.stdout.log").write_text(result["stdout"], encoding="utf-8")
        (output_dir / f"{safe_name}.stderr.log").write_text(result["stderr"], encoding="utf-8")

    return 0 if summary["overall"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
