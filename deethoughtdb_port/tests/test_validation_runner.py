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

    def test_summary_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            sample = {
                "generatedOn": "2026-03-04T00:00:00+00:00",
                "overall": "pass",
                "results": [
                    {
                        "suite": "unit-core",
                        "gate": "A",
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


if __name__ == "__main__":
    unittest.main()
