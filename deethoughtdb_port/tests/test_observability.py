import tempfile
import unittest
from pathlib import Path

from deethoughtdb_port.app import build_default_server
from deethoughtdb_port.transport.http_models import HttpRequest


class ObservabilityTests(unittest.TestCase):
    def _login(self, runtime) -> str:
        request = HttpRequest(
            method="POST",
            path="/_open/auth",
            api_version=1,
            body={"username": "root", "password": "deethoughtdb"},
        )
        response = runtime.handle_request(request)
        return response.body["result"]["token"]

    def test_metrics_by_path_and_system_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = build_default_server(cluster_enabled=True, artifact_dir=tmp)
            token = self._login(runtime)
            headers = {"authorization": f"Bearer {token}"}

            for _ in range(2):
                runtime.handle_request(
                    HttpRequest(method="GET", path="/_api/database", api_version=1, headers=headers)
                )

            report_request = HttpRequest(
                method="GET",
                path="/_admin/system-report",
                api_version=1,
                headers=headers,
            )
            report_response = runtime.handle_request(report_request)

            self.assertEqual(report_response.status_code, 200)
            metrics = report_response.body["result"]["metrics"]
            self.assertGreaterEqual(metrics["requestsByPath"]["/_api/database"], 2)
            self.assertIn("/_api/database", metrics["latencyByPathMs"])

    def test_runtime_artifact_file_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = build_default_server(cluster_enabled=False, artifact_dir=tmp)
            runtime.handle_request(HttpRequest(method="GET", path="/_api/version", api_version=1))

            events_path = Path(tmp) / "runtime-events.jsonl"
            self.assertTrue(events_path.exists())
            lines = events_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
