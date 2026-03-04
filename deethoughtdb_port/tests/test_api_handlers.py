import unittest

from deethoughtdb_port.app import build_default_server
from deethoughtdb_port.transport.http_models import HttpRequest


class ApiHandlerTests(unittest.TestCase):
    def test_engine_endpoint_reports_rocksdb(self) -> None:
        runtime = build_default_server()

        engine_request = HttpRequest(method="GET", path="/_api/engine", api_version=1)
        engine_handler = runtime.handler_factory.create_handler(engine_request)
        engine_response = runtime.handler_factory.invoke(engine_handler, engine_request)

        self.assertEqual(engine_response.status_code, 200)
        self.assertEqual(engine_response.body["name"], "rocksdb")
        self.assertTrue(engine_response.body["supports"]["databases"])

    def test_database_create_and_list(self) -> None:
        runtime = build_default_server()

        create_request = HttpRequest(
            method="POST", path="/_api/database", api_version=1, body={"name": "testdb"}
        )
        create_handler = runtime.handler_factory.create_handler(create_request)
        create_response = runtime.handler_factory.invoke(create_handler, create_request)
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.body["result"]["name"], "testdb")

        list_request = HttpRequest(method="GET", path="/_api/database", api_version=1)
        list_handler = runtime.handler_factory.create_handler(list_request)
        list_response = runtime.handler_factory.invoke(list_handler, list_request)

        self.assertEqual(list_response.status_code, 200)
        names = [entry["name"] for entry in list_response.body["result"]]
        self.assertIn("_system", names)
        self.assertIn("testdb", names)

    def test_transaction_begin_and_commit(self) -> None:
        runtime = build_default_server()

        begin_request = HttpRequest(method="POST", path="/_api/transaction/begin", api_version=1)
        begin_handler = runtime.handler_factory.create_handler(begin_request)
        begin_response = runtime.handler_factory.invoke(begin_handler, begin_request)

        self.assertEqual(begin_response.status_code, 201)
        transaction_id = begin_response.body["result"]["id"]

        commit_path = f"/_api/transaction/{transaction_id}/commit"
        commit_request = HttpRequest(method="POST", path=commit_path, api_version=1)
        commit_handler = runtime.handler_factory.create_handler(commit_request)
        commit_response = runtime.handler_factory.invoke(commit_handler, commit_request)

        self.assertEqual(commit_response.status_code, 200)
        self.assertEqual(commit_response.body["result"]["status"], "commit")

    def test_collection_and_document_crud(self) -> None:
        runtime = build_default_server()

        create_collection = HttpRequest(
            method="POST",
            path="/_api/collection",
            api_version=1,
            body={"name": "users"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        insert_doc = HttpRequest(
            method="POST",
            path="/_api/document/users",
            api_version=1,
            body={"name": "alice"},
        )
        insert_handler = runtime.handler_factory.create_handler(insert_doc)
        insert_response = runtime.handler_factory.invoke(insert_handler, insert_doc)
        self.assertEqual(insert_response.status_code, 201)
        key = insert_response.body["result"]["_key"]

        get_doc = HttpRequest(
            method="GET",
            path=f"/_api/document/users/{key}",
            api_version=1,
        )
        get_handler = runtime.handler_factory.create_handler(get_doc)
        get_response = runtime.handler_factory.invoke(get_handler, get_doc)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.body["result"]["name"], "alice")

    def test_db_prefixed_routes_use_target_database(self) -> None:
        runtime = build_default_server()

        create_db = HttpRequest(
            method="POST",
            path="/_api/database",
            api_version=1,
            body={"name": "tenant1"},
        )
        db_handler = runtime.handler_factory.create_handler(create_db)
        db_response = runtime.handler_factory.invoke(db_handler, create_db)
        self.assertEqual(db_response.status_code, 201)

        create_collection = HttpRequest(
            method="POST",
            path="/_db/tenant1/_api/collection",
            api_version=1,
            body={"name": "events"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        insert_doc = HttpRequest(
            method="POST",
            path="/_db/tenant1/_api/document/events",
            api_version=1,
            body={"kind": "login"},
        )
        insert_handler = runtime.handler_factory.create_handler(insert_doc)
        insert_response = runtime.handler_factory.invoke(insert_handler, insert_doc)
        self.assertEqual(insert_response.status_code, 201)
        key = insert_response.body["result"]["_key"]

        get_doc = HttpRequest(
            method="GET",
            path=f"/_db/tenant1/_api/document/events/{key}",
            api_version=1,
        )
        get_handler = runtime.handler_factory.create_handler(get_doc)
        get_response = runtime.handler_factory.invoke(get_handler, get_doc)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.body["result"]["kind"], "login")

    def test_insert_document_without_collection_returns_api_error(self) -> None:
        runtime = build_default_server()

        login_request = HttpRequest(
            method="POST",
            path="/_open/auth",
            api_version=1,
            body={"username": "root", "password": "deethoughtdb"},
        )
        token = runtime.handle_request(login_request).body["result"]["token"]

        bad_insert = HttpRequest(
            method="POST",
            path="/_api/document/missing_collection",
            api_version=1,
            headers={"authorization": f"Bearer {token}"},
            body={"value": 1},
        )
        response = runtime.handle_request(bad_insert)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.body["error"])

    def test_index_create_and_list(self) -> None:
        runtime = build_default_server()

        create_collection = HttpRequest(
            method="POST",
            path="/_api/collection",
            api_version=1,
            body={"name": "users"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        create_index = HttpRequest(
            method="POST",
            path="/_api/index",
            api_version=1,
            body={"collection": "users", "type": "hash", "fields": ["email"]},
        )
        index_handler = runtime.handler_factory.create_handler(create_index)
        index_response = runtime.handler_factory.invoke(index_handler, create_index)
        self.assertEqual(index_response.status_code, 201)
        self.assertEqual(index_response.body["result"]["type"], "hash")

        list_index = HttpRequest(method="GET", path="/_api/index/users", api_version=1)
        list_handler = runtime.handler_factory.create_handler(list_index)
        list_response = runtime.handler_factory.invoke(list_handler, list_index)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.body["result"]), 1)
        self.assertEqual(list_response.body["result"][0]["fields"], ["email"])

    def test_db_prefixed_index_routes(self) -> None:
        runtime = build_default_server()

        create_db = HttpRequest(
            method="POST",
            path="/_api/database",
            api_version=1,
            body={"name": "tenant_index"},
        )
        db_handler = runtime.handler_factory.create_handler(create_db)
        db_response = runtime.handler_factory.invoke(db_handler, create_db)
        self.assertEqual(db_response.status_code, 201)

        create_collection = HttpRequest(
            method="POST",
            path="/_db/tenant_index/_api/collection",
            api_version=1,
            body={"name": "events"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        create_index = HttpRequest(
            method="POST",
            path="/_db/tenant_index/_api/index",
            api_version=1,
            body={"collection": "events", "type": "hash", "fields": ["kind"]},
        )
        index_handler = runtime.handler_factory.create_handler(create_index)
        index_response = runtime.handler_factory.invoke(index_handler, create_index)
        self.assertEqual(index_response.status_code, 201)

        list_index = HttpRequest(
            method="GET",
            path="/_db/tenant_index/_api/index/events",
            api_version=1,
        )
        list_handler = runtime.handler_factory.create_handler(list_index)
        list_response = runtime.handler_factory.invoke(list_handler, list_index)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.body["result"]), 1)


if __name__ == "__main__":
    unittest.main()
