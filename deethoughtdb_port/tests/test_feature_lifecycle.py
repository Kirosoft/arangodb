import unittest

from deethoughtdb_port.runtime.feature import FeatureState
from deethoughtdb_port.runtime.server import ApplicationServer
from deethoughtdb_port.app import build_default_server


class FeatureLifecycleTests(unittest.TestCase):
    def test_boot_orders_dependencies(self) -> None:
        runtime = build_default_server()
        runtime.app_server.boot()
        self.assertEqual(runtime.app_server.startup_order, ["Config", "Network", "Rest"])

    def test_shutdown_reverses_startup_order(self) -> None:
        runtime = build_default_server()
        runtime.app_server.boot()
        runtime.app_server.shutdown()

        self.assertEqual(runtime.app_server.feature("Config").state, FeatureState.STOPPED)
        self.assertEqual(runtime.app_server.feature("Network").state, FeatureState.STOPPED)
        self.assertEqual(runtime.app_server.feature("Rest").state, FeatureState.STOPPED)


if __name__ == "__main__":
    unittest.main()
