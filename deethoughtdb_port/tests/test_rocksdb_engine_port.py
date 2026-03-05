import tempfile
import unittest

from deethoughtdb_port.storage import RocksDBEnginePort, RocksDBPortConfig
from deethoughtdb_port.storage.contracts import RecoveryState


class RocksDBEnginePortTests(unittest.TestCase):
    def test_engine_contract_basics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = RocksDBEnginePort(RocksDBPortConfig.from_root(tmp))

            self.assertEqual(engine.type_name(), "rocksdb")
            self.assertEqual(engine.recovery_state(), RecoveryState.DONE)

            health = engine.health_check()
            self.assertEqual(health["engine"], "rocksdb")

            capabilities = engine.get_capabilities()
            self.assertTrue(capabilities["wal"])

    def test_database_collection_and_wal_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = RocksDBEnginePort(RocksDBPortConfig.from_root(tmp))

            db = engine.create_database("testdb")
            self.assertEqual(db["name"], "testdb")

            col = engine.create_collection("testdb", "docs")
            self.assertEqual(col["name"], "docs")

            flush = engine.flush_wal()
            self.assertTrue(flush["flushed"])
            self.assertGreater(engine.current_tick(), 0)
            self.assertGreaterEqual(len(engine.current_wal_files()), 1)

    def test_replication_applier_config_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = RocksDBEnginePort(RocksDBPortConfig.from_root(tmp))

            written = engine.create_replication_applier_config(
                {"endpoint": "tcp://127.0.0.1:8529", "username": "root"}
            )
            self.assertEqual(written["endpoint"], "tcp://127.0.0.1:8529")

            read_back = engine.get_replication_applier_config()
            self.assertEqual(read_back["username"], "root")

            engine.remove_replication_applier_config()
            self.assertEqual(engine.get_replication_applier_config(), {})


if __name__ == "__main__":
    unittest.main()
