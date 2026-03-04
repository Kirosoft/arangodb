import json
import os
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request


class LiveArangoHttpClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.token = self._login()

    def _login(self) -> str:
        payload = {"username": self.username, "password": self.password}
        response = self.request(
            "POST",
            "/_open/auth",
            body=payload,
            include_auth=False,
            expected=(200,),
        )
        return str(response["result"]["token"])

    def request(
        self,
        method: str,
        path: str,
        body: dict | list | None = None,
        include_auth: bool = True,
        expected: tuple[int, ...] = (200, 201, 202),
    ) -> dict:
        url = self.base_url + path
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"content-type": "application/json"}
        if include_auth:
            headers["authorization"] = f"Bearer {self.token}"

        request = urllib.request.Request(url=url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                status = response.getcode()
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            status = exc.code
            payload = exc.read().decode("utf-8") if exc.fp else "{}"

        parsed = json.loads(payload) if payload else {}
        if status not in expected:
            raise AssertionError(
                f"Unexpected HTTP {status} for {method} {path}; payload={parsed}"
            )
        return parsed


class LiveRocksDBIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.getenv("DTH_LIVE_ROCKSDB", "0") != "1":
            raise unittest.SkipTest("Set DTH_LIVE_ROCKSDB=1 to run live RocksDB integration tests")

        base_url = os.getenv("DTH_ARANGO_URL", "http://127.0.0.1:8529")
        username = os.getenv("DTH_ARANGO_USER", "root")
        password = os.getenv("DTH_ARANGO_PASSWORD")
        if not password:
            raise unittest.SkipTest("Set DTH_ARANGO_PASSWORD for live integration tests")

        cls.client = LiveArangoHttpClient(base_url=base_url, username=username, password=password)

        engine = cls.client.request("GET", "/_api/engine", expected=(200,))
        engine_name = str(engine.get("name", "")).lower()
        if engine_name != "rocksdb":
            raise AssertionError(f"Expected RocksDB engine, got '{engine_name}'")

        suffix = int(time.time() * 1000)
        cls.test_db = f"deethoughtdb_live_{suffix}"
        cls.client.request(
            "POST",
            "/_api/database",
            body={
                "name": cls.test_db,
                "options": {
                    "replicationFactor": 1,
                    "sharding": "single",
                },
                "users": [],
            },
            expected=(201, 202),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        if not hasattr(cls, "client") or not hasattr(cls, "test_db"):
            return
        safe_name = urllib.parse.quote(cls.test_db)
        cls.client.request("DELETE", f"/_api/database/{safe_name}", expected=(200, 202, 404))

    def test_create_collection_and_document_roundtrip(self) -> None:
        db = urllib.parse.quote(self.test_db)

        create_collection = self.client.request(
            "POST",
            f"/_db/{db}/_api/collection",
            body={"name": "docs", "waitForSync": False},
            expected=(200, 201, 202),
        )
        self.assertIn("name", create_collection)

        insert = self.client.request(
            "POST",
            f"/_db/{db}/_api/document/docs",
            body={"_key": "k1", "value": 42, "engine": "rocksdb"},
            expected=(200, 201, 202),
        )
        self.assertEqual(insert.get("_key"), "k1")

        read = self.client.request(
            "GET",
            f"/_db/{db}/_api/document/docs/k1",
            expected=(200,),
        )
        self.assertEqual(read.get("value"), 42)
        self.assertEqual(read.get("engine"), "rocksdb")

    def test_transaction_endpoint_live(self) -> None:
        db = urllib.parse.quote(self.test_db)

        begin = self.client.request(
            "POST",
            f"/_db/{db}/_api/transaction/begin",
            body={
                "collections": {"write": ["docs"]},
            },
            expected=(200, 201),
        )
        result = begin.get("result", {})
        txn_id = result.get("id")
        self.assertTrue(txn_id, "Expected transaction id from /_api/transaction/begin")

        self.client.request(
            "PUT",
            f"/_db/{db}/_api/transaction/{txn_id}",
            expected=(200, 202),
        )


if __name__ == "__main__":
    unittest.main()
