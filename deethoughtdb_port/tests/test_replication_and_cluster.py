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

    def test_replication2_requires_feature_flag(self) -> None:
        runtime = build_default_server(cluster_enabled=True, replication2_enabled=False)
        token = self._token(runtime)
        headers = {"authorization": f"Bearer {token}"}

        state_request = HttpRequest(
            method="GET",
            path="/_api/replication2/state",
            api_version=1,
            headers=headers,
        )
        state_response = runtime.handle_request(state_request)
        self.assertEqual(state_response.status_code, 400)

    def test_replication2_state_and_append_entries(self) -> None:
        runtime = build_default_server(cluster_enabled=True, replication2_enabled=True)
        token = self._token(runtime)
        headers = {"authorization": f"Bearer {token}"}

        state_request = HttpRequest(
            method="GET",
            path="/_api/replication2/state",
            api_version=1,
            headers=headers,
        )
        state_response = runtime.handle_request(state_request)
        self.assertEqual(state_response.status_code, 200)
        self.assertEqual(state_response.body["result"]["role"], "leader")

        logger_request = HttpRequest(
            method="GET",
            path="/_api/replication2/logger-state",
            api_version=1,
            headers=headers,
        )
        logger_response = runtime.handle_request(logger_request)
        self.assertEqual(logger_response.status_code, 200)
        self.assertEqual(logger_response.body["result"]["commitIndex"], 0)

        append_request = HttpRequest(
            method="POST",
            path="/_api/replication2/append-entries",
            api_version=1,
            headers=headers,
            body={"entries": [{"index": 1}, {"index": 2}]},
        )
        append_response = runtime.handle_request(append_request)
        self.assertEqual(append_response.status_code, 200)
        self.assertEqual(append_response.body["result"]["applied"], 2)
        self.assertEqual(append_response.body["result"]["commitIndex"], 2)

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

        agency_request = HttpRequest(
            method="POST",
            path="/_api/agency/read",
            api_version=1,
            headers=headers,
            body={"keys": ["/Plan/Version"]},
        )
        agency_response = runtime.handle_request(agency_request)
        self.assertEqual(agency_response.status_code, 400)

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

        shard_assign = HttpRequest(
            method="POST",
            path="/_admin/cluster/shard-leadership",
            api_version=1,
            headers=headers,
            body={"shard": "s100", "leader": "PRMR-2"},
        )
        shard_assign_response = runtime.handle_request(shard_assign)
        self.assertEqual(shard_assign_response.status_code, 200)
        self.assertEqual(shard_assign_response.body["result"]["shard"], "s100")

        shard_list = HttpRequest(
            method="GET",
            path="/_admin/cluster/shard-leadership",
            api_version=1,
            headers=headers,
        )
        shard_list_response = runtime.handle_request(shard_list)
        self.assertEqual(shard_list_response.status_code, 200)
        self.assertEqual(shard_list_response.body["result"]["s100"], "PRMR-2")

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

        shard_assign_without_maintenance = HttpRequest(
            method="POST",
            path="/_admin/cluster/shard-leadership",
            api_version=1,
            headers=headers,
            body={"shard": "s101", "leader": "PRMR-1"},
        )
        shard_assign_without_maintenance_response = runtime.handle_request(shard_assign_without_maintenance)
        self.assertEqual(shard_assign_without_maintenance_response.status_code, 400)

        shard_release_force = HttpRequest(
            method="DELETE",
            path="/_admin/cluster/shard-leadership/s100",
            api_version=1,
            headers=headers,
            body={"force": True},
        )
        shard_release_force_response = runtime.handle_request(shard_release_force)
        self.assertEqual(shard_release_force_response.status_code, 200)
        self.assertTrue(shard_release_force_response.body["result"]["released"])

        move_without_maintenance = HttpRequest(
            method="POST",
            path="/_admin/cluster/move-shard",
            api_version=1,
            headers=headers,
            body={"shard": "s200", "fromServer": "PRMR-1", "toServer": "PRMR-2"},
        )
        move_without_maintenance_response = runtime.handle_request(move_without_maintenance)
        self.assertEqual(move_without_maintenance_response.status_code, 400)

        maintenance_enable = HttpRequest(
            method="PUT",
            path="/_admin/cluster/maintenance",
            api_version=1,
            headers=headers,
            body={"enabled": True},
        )
        maintenance_enable_response = runtime.handle_request(maintenance_enable)
        self.assertEqual(maintenance_enable_response.status_code, 200)
        self.assertTrue(maintenance_enable_response.body["result"]["enabled"])

        assign_for_move = HttpRequest(
            method="POST",
            path="/_admin/cluster/shard-leadership",
            api_version=1,
            headers=headers,
            body={"shard": "s200", "leader": "PRMR-1"},
        )
        assign_for_move_response = runtime.handle_request(assign_for_move)
        self.assertEqual(assign_for_move_response.status_code, 200)

        move_with_maintenance = HttpRequest(
            method="POST",
            path="/_admin/cluster/move-shard",
            api_version=1,
            headers=headers,
            body={"shard": "s200", "fromServer": "PRMR-1", "toServer": "PRMR-2"},
        )
        move_with_maintenance_response = runtime.handle_request(move_with_maintenance)
        self.assertEqual(move_with_maintenance_response.status_code, 200)
        self.assertTrue(move_with_maintenance_response.body["result"]["moved"])

        rebalance_request = HttpRequest(
            method="POST",
            path="/_admin/cluster/rebalance",
            api_version=1,
            headers=headers,
            body={},
        )
        rebalance_response = runtime.handle_request(rebalance_request)
        self.assertEqual(rebalance_response.status_code, 200)
        self.assertTrue(rebalance_response.body["result"]["rebalanced"])

    def test_agency_read_write_and_cas(self) -> None:
        runtime = build_default_server(cluster_enabled=True)
        token = self._token(runtime)
        headers = {"authorization": f"Bearer {token}"}

        write_request = HttpRequest(
            method="POST",
            path="/_api/agency/write",
            api_version=1,
            headers=headers,
            body={"entries": {"/Plan/Version": 1, "/Target/Health": "GOOD"}},
        )
        write_response = runtime.handle_request(write_request)
        self.assertEqual(write_response.status_code, 200)
        self.assertIn("index", write_response.body["result"])

        read_request = HttpRequest(
            method="POST",
            path="/_api/agency/read",
            api_version=1,
            headers=headers,
            body={"keys": ["/Plan/Version", "/Target/Health", "/Missing"]},
        )
        read_response = runtime.handle_request(read_request)
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.body["result"]["/Plan/Version"], 1)
        self.assertEqual(read_response.body["result"]["/Target/Health"], "GOOD")
        self.assertNotIn("/Missing", read_response.body["result"])

        cas_success = HttpRequest(
            method="POST",
            path="/_api/agency/cas",
            api_version=1,
            headers=headers,
            body={"key": "/Plan/Version", "old": 1, "new": 2},
        )
        cas_success_response = runtime.handle_request(cas_success)
        self.assertEqual(cas_success_response.status_code, 200)
        self.assertTrue(cas_success_response.body["result"]["applied"])

        cas_fail = HttpRequest(
            method="POST",
            path="/_api/agency/cas",
            api_version=1,
            headers=headers,
            body={"key": "/Plan/Version", "old": 1, "new": 3},
        )
        cas_fail_response = runtime.handle_request(cas_fail)
        self.assertEqual(cas_fail_response.status_code, 200)
        self.assertFalse(cas_fail_response.body["result"]["applied"])


if __name__ == "__main__":
    unittest.main()
