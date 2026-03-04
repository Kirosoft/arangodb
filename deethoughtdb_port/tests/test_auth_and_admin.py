import unittest

from deethoughtdb_port.app import build_default_server
from deethoughtdb_port.transport.http_models import HttpRequest


class AuthAndAdminTests(unittest.TestCase):
    def test_protected_endpoint_requires_auth(self) -> None:
        runtime = build_default_server()
        request = HttpRequest(method="GET", path="/_api/database", api_version=1)
        response = runtime.handle_request(request)
        self.assertEqual(response.status_code, 401)

    def test_auth_then_access_database(self) -> None:
        runtime = build_default_server()

        login_request = HttpRequest(
            method="POST",
            path="/_open/auth",
            api_version=1,
            body={"username": "root", "password": "deethoughtdb"},
        )
        login_response = runtime.handle_request(login_request)
        self.assertEqual(login_response.status_code, 200)
        token = login_response.body["result"]["token"]

        db_request = HttpRequest(
            method="GET",
            path="/_api/database",
            api_version=1,
            headers={"authorization": f"Bearer {token}"},
        )
        db_response = runtime.handle_request(db_request)
        self.assertEqual(db_response.status_code, 200)

    def test_admin_status_and_metrics(self) -> None:
        runtime = build_default_server()

        login_request = HttpRequest(
            method="POST",
            path="/_open/auth",
            api_version=1,
            body={"username": "root", "password": "deethoughtdb"},
        )
        token = runtime.handle_request(login_request).body["result"]["token"]

        status_request = HttpRequest(
            method="GET",
            path="/_admin/status",
            api_version=1,
            headers={"authorization": f"Bearer {token}"},
        )
        status_response = runtime.handle_request(status_request)
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.body["status"], "running")

        metrics_request = HttpRequest(
            method="GET",
            path="/_admin/metrics",
            api_version=1,
            headers={"authorization": f"Bearer {token}"},
        )
        metrics_response = runtime.handle_request(metrics_request)
        self.assertEqual(metrics_response.status_code, 200)
        self.assertGreaterEqual(metrics_response.body["result"]["requestsTotal"], 1)


if __name__ == "__main__":
    unittest.main()
