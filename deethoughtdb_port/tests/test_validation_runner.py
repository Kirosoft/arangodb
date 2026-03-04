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
            }
            path = output_dir / "summary.json"
            path.write_text(json.dumps(sample), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["overall"], "pass")
            self.assertEqual(loaded["results"][0]["gate"], "A")
            self.assertTrue(loaded["results"][0]["gateBlocking"])


if __name__ == "__main__":
    unittest.main()
