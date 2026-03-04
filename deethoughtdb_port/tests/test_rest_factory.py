import unittest

from deethoughtdb_port.api.errors import unknown_api_version
from deethoughtdb_port.app import build_default_server
from deethoughtdb_port.transport.http_models import HttpRequest


class RestFactoryTests(unittest.TestCase):
    def test_direct_route(self) -> None:
        runtime = build_default_server()
        request = HttpRequest(method="GET", path="/_api/version", api_version=1)
        handler = runtime.handler_factory.create_handler(request)
        response = runtime.handler_factory.invoke(handler, request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body["server"], "deethoughtdb")

    def test_catch_all_prefix(self) -> None:
        runtime = build_default_server()
        request = HttpRequest(method="GET", path="/unknown/path", api_version=1)
        handler = runtime.handler_factory.create_handler(request)
        response = runtime.handler_factory.invoke(handler, request)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.body["prefix"], "/")

    def test_unknown_api_version_error(self) -> None:
        runtime = build_default_server()
        request = HttpRequest(method="GET", path="/_api/version", api_version=99)

        with self.assertRaises(type(unknown_api_version(99, request.path))):
            runtime.handler_factory.create_handler(request)


if __name__ == "__main__":
    unittest.main()
