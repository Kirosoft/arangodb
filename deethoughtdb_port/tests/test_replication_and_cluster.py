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

        start_request = HttpRequest(
            method="PUT",
            path="/_api/replication/applier-start",
            api_version=1,
            headers=headers,
        )
        start_response = runtime.handle_request(start_request)
        self.assertEqual(start_response.status_code, 200)
        self.assertTrue(start_response.body["result"]["running"])

        logger_request = HttpRequest(
            method="GET",
            path="/_api/replication/logger-state",
            api_version=1,
            headers=headers,
        )
        logger_response = runtime.handle_request(logger_request)
        self.assertEqual(logger_response.status_code, 200)
        self.assertIn("lastCommittedLogTick", logger_response.body["result"])

        applier_state_request = HttpRequest(
            method="GET",
            path="/_api/replication/applier-state",
            api_version=1,
            headers=headers,
        )
        applier_state_response = runtime.handle_request(applier_state_request)
        self.assertEqual(applier_state_response.status_code, 200)
        self.assertTrue(applier_state_response.body["result"]["running"])
        self.assertIn("serverId", applier_state_response.body["result"])

        server_id_request = HttpRequest(
            method="GET",
            path="/_api/replication/server-id",
            api_version=1,
            headers=headers,
        )
        server_id_response = runtime.handle_request(server_id_request)
        self.assertEqual(server_id_response.status_code, 200)
        self.assertIn("serverId", server_id_response.body)

        sync_request = HttpRequest(
            method="POST",
            path="/_api/replication/sync",
            api_version=1,
            headers=headers,
            body={},
        )
        sync_response = runtime.handle_request(sync_request)
        self.assertEqual(sync_response.status_code, 200)
        self.assertIn("lastLogTick", sync_response.body["result"])

        stop_request = HttpRequest(
            method="PUT",
            path="/_api/replication/applier-stop",
            api_version=1,
            headers=headers,
        )
        stop_response = runtime.handle_request(stop_request)
        self.assertEqual(stop_response.status_code, 200)
        self.assertFalse(stop_response.body["result"]["running"])

        delete_request = HttpRequest(
            method="DELETE",
            path="/_api/replication/applier-config",
            api_version=1,
            headers=headers,
        )
        delete_response = runtime.handle_request(delete_request)
        self.assertEqual(delete_response.status_code, 200)

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

        number_request = HttpRequest(
            method="GET",
            path="/_admin/cluster/numberOfServers",
            api_version=1,
            headers=headers,
        )
        number_response = runtime.handle_request(number_request)
        self.assertEqual(number_response.status_code, 200)
        self.assertGreaterEqual(number_response.body["result"]["total"], 1)

        maintenance_get = HttpRequest(
            method="GET",
            path="/_admin/cluster/maintenance",
            api_version=1,
            headers=headers,
        )
        maintenance_get_response = runtime.handle_request(maintenance_get)
        self.assertEqual(maintenance_get_response.status_code, 200)
        self.assertFalse(maintenance_get_response.body["result"]["enabled"])

        maintenance_put = HttpRequest(
            method="PUT",
            path="/_admin/cluster/maintenance",
            api_version=1,
            headers=headers,
            body={"enabled": True},
        )
        maintenance_put_response = runtime.handle_request(maintenance_put)
        self.assertEqual(maintenance_put_response.status_code, 200)
        self.assertTrue(maintenance_put_response.body["result"]["enabled"])

        endpoints_request = HttpRequest(
            method="GET",
            path="/_admin/cluster/endpoints",
            api_version=1,
            headers=headers,
        )
        endpoints_response = runtime.handle_request(endpoints_request)
        self.assertEqual(endpoints_response.status_code, 200)
        self.assertIn("coordinators", endpoints_response.body["result"])
        self.assertIn("dbservers", endpoints_response.body["result"])

        heartbeat_request = HttpRequest(
            method="POST",
            path="/_admin/cluster/heartbeat",
            api_version=1,
            headers=headers,
            body={"serverId": "PRMR-2", "status": "GOOD"},
        )
        heartbeat_response = runtime.handle_request(heartbeat_request)
        self.assertEqual(heartbeat_response.status_code, 200)
        self.assertEqual(heartbeat_response.body["result"]["serverId"], "PRMR-2")

        maintenance_delete = HttpRequest(
            method="DELETE",
            path="/_admin/cluster/maintenance",
            api_version=1,
            headers=headers,
        )
        maintenance_delete_response = runtime.handle_request(maintenance_delete)
        self.assertEqual(maintenance_delete_response.status_code, 200)
        self.assertFalse(maintenance_delete_response.body["result"]["enabled"])


if __name__ == "__main__":
    unittest.main()
