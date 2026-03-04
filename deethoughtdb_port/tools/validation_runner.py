from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
from dataclasses import dataclass


@dataclass(slots=True)
class SuiteSpec:
    name: str
    gate: str
    command: list[str]


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
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = pathlib.Path(__file__).resolve().parents[1] / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.setdefault("PYTHONPATH", "src")

    results = []
    for suite in _default_suites():
        results.append(run_suite(suite, env))

    summary = {
        "generatedOn": dt.datetime.now(dt.UTC).isoformat(),
        "overall": "pass" if all(r["status"] == "pass" for r in results) else "fail",
        "results": [
            {
                "suite": r["suite"],
                "gate": r["gate"],
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
