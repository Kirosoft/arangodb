import unittest

from deethoughtdb_port.app import build_default_server
from deethoughtdb_port.transport.http_models import HttpRequest


class ReplicationAndClusterTests(unittest.TestCase):
    def _token(self, runtime) -> str:
        login_request = HttpRequest(
            method="POST",
            path="/_open/auth",
            api_version=1,
            body={"username": "root", "password": "deethoughtdb"},
        )
        login_response = runtime.handle_request(login_request)
        return login_response.body["result"]["token"]

    def test_replication_state_and_config_update(self) -> None:
        runtime = build_default_server(cluster_enabled=True)
        token = self._token(runtime)
        headers = {"authorization": f"Bearer {token}"}

        state_request = HttpRequest(
            method="GET",
            path="/_api/replication/state",
            api_version=1,
            headers=headers,
        )
        state_response = runtime.handle_request(state_request)
        self.assertEqual(state_response.status_code, 200)
        self.assertEqual(state_response.body["result"]["mode"], "cluster")

        update_request = HttpRequest(
            method="PUT",
            path="/_api/replication/applier-config",
            api_version=1,
            headers=headers,
            body={"endpoint": "tcp://127.0.0.1:8529", "username": "root"},
        )
        update_response = runtime.handle_request(update_request)
        self.assertEqual(update_response.status_code, 200)

        config_request = HttpRequest(
            method="GET",
            path="/_api/replication/applier-config",
            api_version=1,
            headers=headers,
        )
        config_response = runtime.handle_request(config_request)
        self.assertEqual(config_response.status_code, 200)
        self.assertEqual(config_response.body["result"]["endpoint"], "tcp://127.0.0.1:8529")

    def test_cluster_health_requires_cluster_enabled(self) -> None:
        runtime = build_default_server(cluster_enabled=False)
        token = self._token(runtime)
        headers = {"authorization": f"Bearer {token}"}

        request = HttpRequest(
            method="GET",
            path="/_admin/cluster/health",
            api_version=1,
            headers=headers,
        )
        response = runtime.handle_request(request)
        self.assertEqual(response.status_code, 400)

    def test_cluster_health_and_role(self) -> None:
        runtime = build_default_server(cluster_enabled=True)
        token = self._token(runtime)
        headers = {"authorization": f"Bearer {token}"}

        health_request = HttpRequest(
            method="GET",
            path="/_admin/cluster/health",
            api_version=1,
            headers=headers,
        )
        health_response = runtime.handle_request(health_request)
        self.assertEqual(health_response.status_code, 200)
        self.assertTrue(health_response.body["result"]["enabled"])

        role_request = HttpRequest(
            method="GET",
            path="/_admin/cluster/role",
            api_version=1,
            headers=headers,
        )
        role_response = runtime.handle_request(role_request)
        self.assertEqual(role_response.status_code, 200)
        self.assertEqual(role_response.body["result"]["role"], "coordinator")


if __name__ == "__main__":
    unittest.main()
