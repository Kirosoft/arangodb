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

    def test_api_token_endpoint(self) -> None:
        runtime = build_default_server()

        token_request = HttpRequest(
            method="POST",
            path="/_api/token",
            api_version=1,
            body={"username": "root", "password": "deethoughtdb"},
        )
        token_response = runtime.handle_request(token_request)
        self.assertEqual(token_response.status_code, 200)
        self.assertIn("token", token_response.body["result"])
        self.assertIn("jwt", token_response.body["result"])

    def test_api_token_invalid_credentials(self) -> None:
        runtime = build_default_server()

        token_request = HttpRequest(
            method="POST",
            path="/_api/token",
            api_version=1,
            body={"username": "root", "password": "wrong"},
        )
        token_response = runtime.handle_request(token_request)
        self.assertEqual(token_response.status_code, 401)

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

        time_request = HttpRequest(
            method="GET",
            path="/_admin/time",
            api_version=1,
            headers={"authorization": f"Bearer {token}"},
        )
        time_response = runtime.handle_request(time_request)
        self.assertEqual(time_response.status_code, 200)
        self.assertIn("utc", time_response.body["result"])
        self.assertIn("timestamp", time_response.body["result"])

        compact_request = HttpRequest(
            method="PUT",
            path="/_admin/compact",
            api_version=1,
            headers={"authorization": f"Bearer {token}"},
        )
        compact_response = runtime.handle_request(compact_request)
        self.assertEqual(compact_response.status_code, 200)
        self.assertTrue(compact_response.body["result"]["compacted"])

    def test_admin_shutdown_changes_status(self) -> None:
        runtime = build_default_server()

        login_request = HttpRequest(
            method="POST",
            path="/_open/auth",
            api_version=1,
            body={"username": "root", "password": "deethoughtdb"},
        )
        token = runtime.handle_request(login_request).body["result"]["token"]

        shutdown_request = HttpRequest(
            method="POST",
            path="/_admin/shutdown",
            api_version=1,
            headers={"authorization": f"Bearer {token}"},
        )
        shutdown_response = runtime.handle_request(shutdown_request)
        self.assertEqual(shutdown_response.status_code, 200)
        self.assertTrue(shutdown_response.body["result"]["shutdown"])

        status_request = HttpRequest(
            method="GET",
            path="/_admin/status",
            api_version=1,
            headers={"authorization": f"Bearer {token}"},
        )
        status_response = runtime.handle_request(status_request)
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.body["status"], "stopped")

    def test_user_api_admin_lifecycle(self) -> None:
        runtime = build_default_server()

        login_request = HttpRequest(
            method="POST",
            path="/_open/auth",
            api_version=1,
            body={"username": "root", "password": "deethoughtdb"},
        )
        token = runtime.handle_request(login_request).body["result"]["token"]

        create_user = HttpRequest(
            method="POST",
            path="/_api/user",
            api_version=1,
            headers={"authorization": f"Bearer {token}"},
            body={"user": "alice", "passwd": "secret", "isAdmin": False},
        )
        create_response = runtime.handle_request(create_user)
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.body["result"]["user"], "alice")

        list_users = HttpRequest(
            method="GET",
            path="/_api/user",
            api_version=1,
            headers={"authorization": f"Bearer {token}"},
        )
        list_response = runtime.handle_request(list_users)
        self.assertEqual(list_response.status_code, 200)
        users = [entry["user"] for entry in list_response.body["result"]]
        self.assertIn("alice", users)

        delete_user = HttpRequest(
            method="DELETE",
            path="/_api/user/alice",
            api_version=1,
            headers={"authorization": f"Bearer {token}"},
        )
        delete_response = runtime.handle_request(delete_user)
        self.assertEqual(delete_response.status_code, 200)

    def test_user_api_requires_admin(self) -> None:
        runtime = build_default_server()

        root_login = HttpRequest(
            method="POST",
            path="/_open/auth",
            api_version=1,
            body={"username": "root", "password": "deethoughtdb"},
        )
        root_token = runtime.handle_request(root_login).body["result"]["token"]
        runtime.handle_request(
            HttpRequest(
                method="POST",
                path="/_api/user",
                api_version=1,
                headers={"authorization": f"Bearer {root_token}"},
                body={"user": "bob", "passwd": "secret", "isAdmin": False},
            )
        )

        user_login = HttpRequest(
            method="POST",
            path="/_open/auth",
            api_version=1,
            body={"username": "bob", "password": "secret"},
        )
        user_token = runtime.handle_request(user_login).body["result"]["token"]

        denied_request = HttpRequest(
            method="GET",
            path="/_api/user",
            api_version=1,
            headers={"authorization": f"Bearer {user_token}"},
        )
        denied_response = runtime.handle_request(denied_request)
        self.assertEqual(denied_response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
