import json
import tempfile
import unittest
from pathlib import Path

from tools import validation_runner


class ValidationRunnerTests(unittest.TestCase):
    def test_default_suites_defined(self) -> None:
        suites = validation_runner._default_suites()
        names = [suite.name for suite in suites]
        self.assertIn("unit-core", names)
        self.assertIn("live-rocksdb", names)

    def test_matrix_gates_are_loaded(self) -> None:
        matrix_path = validation_runner._default_matrix_path()
        gates = validation_runner._load_matrix_gates(matrix_path)
        self.assertIn("A", gates)
        self.assertIn("B", gates)
        self.assertTrue(gates["A"].blocking)

    def test_matrix_sections_are_loaded(self) -> None:
        matrix_path = validation_runner._default_matrix_path()
        manifests = validation_runner._load_matrix_section_items(matrix_path, "manifests")
        core_groups = validation_runner._load_matrix_section_items(matrix_path, "coreCiGroups")
        self.assertGreater(len(manifests), 0)
        self.assertGreater(len(core_groups), 0)
        self.assertTrue(any(item.gate == "A" for item in manifests))

    def test_matrix_gate_distribution(self) -> None:
        matrix_path = validation_runner._default_matrix_path()
        gates = validation_runner._load_matrix_gates(matrix_path)
        manifests = validation_runner._load_matrix_section_items(matrix_path, "manifests")
        distribution = validation_runner._matrix_gate_distribution(manifests, gates)
        gate_codes = {entry["gate"] for entry in distribution}
        self.assertIn("A", gate_codes)
        self.assertIn("B", gate_codes)

    def test_summary_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            sample = {
                "generatedOn": "2026-03-04T00:00:00+00:00",
                "matrixPath": "matrix.yml",
                "overall": "pass",
                "results": [
                    {
                        "suite": "unit-core",
                        "gate": "A",
                        "gateName": "backend-core",
                        "gateBlocking": True,
                        "status": "pass",
                        "durationSec": 1.2,
                        "exitCode": 0,
                    }
                ],
                "matrixCoverage": {
                    "manifestsByGate": [{"gate": "A", "gateName": "backend-core", "count": 1}],
                    "coreCiGroupsByGate": [{"gate": "A", "gateName": "backend-core", "count": 1}],
                },
            }
            path = output_dir / "summary.json"
            path.write_text(json.dumps(sample), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["overall"], "pass")
            self.assertEqual(loaded["results"][0]["gate"], "A")
            self.assertTrue(loaded["results"][0]["gateBlocking"])
            self.assertIn("matrixCoverage", loaded)


if __name__ == "__main__":
    unittest.main()
