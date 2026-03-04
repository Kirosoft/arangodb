import unittest

from deethoughtdb_port.app import build_default_server
from deethoughtdb_port.transport.http_models import HttpRequest


class ApiHandlerTests(unittest.TestCase):
    def test_version_reports_capability_metadata(self) -> None:
        runtime = build_default_server()

        request = HttpRequest(method="GET", path="/_api/version", api_version=1)
        handler = runtime.handler_factory.create_handler(request)
        response = runtime.handler_factory.invoke(handler, request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body["details"]["engine"], "rocksdb")
        self.assertFalse(response.body["details"]["aql"])

    def test_aql_endpoints_are_explicitly_disabled(self) -> None:
        runtime = build_default_server()

        for path in ["/_api/aql", "/_api/query", "/_api/cursor", "/_api/explain"]:
            request = HttpRequest(method="POST", path=path, api_version=1, body={})
            handler = runtime.handler_factory.create_handler(request)
            response = runtime.handler_factory.invoke(handler, request)
            self.assertEqual(response.status_code, 501)
            self.assertEqual(response.body["capability"], "aql-disabled")

    def test_engine_endpoint_reports_rocksdb(self) -> None:
        runtime = build_default_server()

        engine_request = HttpRequest(method="GET", path="/_api/engine", api_version=1)
        engine_handler = runtime.handler_factory.create_handler(engine_request)
        engine_response = runtime.handler_factory.invoke(engine_handler, engine_request)

        self.assertEqual(engine_response.status_code, 200)
        self.assertEqual(engine_response.body["name"], "rocksdb")
        self.assertTrue(engine_response.body["supports"]["databases"])

    def test_engine_stats_endpoint(self) -> None:
        runtime = build_default_server()

        request = HttpRequest(method="GET", path="/_api/engine/stats", api_version=1)
        handler = runtime.handler_factory.create_handler(request)
        response = runtime.handler_factory.invoke(handler, request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body["result"]["engine"], "rocksdb")
        self.assertIn("currentTick", response.body["result"])

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

    def test_transaction_begin_and_put_commit(self) -> None:
        runtime = build_default_server()

        begin_request = HttpRequest(method="POST", path="/_api/transaction/begin", api_version=1)
        begin_handler = runtime.handler_factory.create_handler(begin_request)
        begin_response = runtime.handler_factory.invoke(begin_handler, begin_request)
        self.assertEqual(begin_response.status_code, 201)
        transaction_id = begin_response.body["result"]["id"]

        put_commit = HttpRequest(
            method="PUT",
            path=f"/_api/transaction/{transaction_id}",
            api_version=1,
        )
        put_handler = runtime.handler_factory.create_handler(put_commit)
        put_response = runtime.handler_factory.invoke(put_handler, put_commit)
        self.assertEqual(put_response.status_code, 200)
        self.assertEqual(put_response.body["result"]["status"], "commit")

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

    def test_collection_detail_and_count(self) -> None:
        runtime = build_default_server()

        create_collection = HttpRequest(
            method="POST",
            path="/_api/collection",
            api_version=1,
            body={"name": "countable"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        for value in [1, 2]:
            insert_doc = HttpRequest(
                method="POST",
                path="/_api/document/countable",
                api_version=1,
                body={"value": value},
            )
            insert_handler = runtime.handler_factory.create_handler(insert_doc)
            insert_response = runtime.handler_factory.invoke(insert_handler, insert_doc)
            self.assertEqual(insert_response.status_code, 201)

        detail_request = HttpRequest(method="GET", path="/_api/collection/countable", api_version=1)
        detail_handler = runtime.handler_factory.create_handler(detail_request)
        detail_response = runtime.handler_factory.invoke(detail_handler, detail_request)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.body["result"]["name"], "countable")

        count_request = HttpRequest(method="GET", path="/_api/collection/countable/count", api_version=1)
        count_handler = runtime.handler_factory.create_handler(count_request)
        count_response = runtime.handler_factory.invoke(count_handler, count_request)
        self.assertEqual(count_response.status_code, 200)
        self.assertEqual(count_response.body["result"]["count"], 2)

    def test_document_put_and_patch(self) -> None:
        runtime = build_default_server()

        create_collection = HttpRequest(
            method="POST",
            path="/_api/collection",
            api_version=1,
            body={"name": "users_mut"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        insert_doc = HttpRequest(
            method="POST",
            path="/_api/document/users_mut",
            api_version=1,
            body={"name": "alice", "age": 30},
        )
        insert_handler = runtime.handler_factory.create_handler(insert_doc)
        insert_response = runtime.handler_factory.invoke(insert_handler, insert_doc)
        self.assertEqual(insert_response.status_code, 201)
        key = insert_response.body["result"]["_key"]
        original_rev = insert_response.body["result"]["_rev"]
        self.assertIn("_id", insert_response.body["result"])

        replace_doc = HttpRequest(
            method="PUT",
            path=f"/_api/document/users_mut/{key}",
            api_version=1,
            body={"name": "alice2", "city": "berlin"},
        )
        replace_handler = runtime.handler_factory.create_handler(replace_doc)
        replace_response = runtime.handler_factory.invoke(replace_handler, replace_doc)
        self.assertEqual(replace_response.status_code, 200)
        self.assertEqual(replace_response.body["result"]["name"], "alice2")
        self.assertNotIn("age", replace_response.body["result"])
        self.assertNotEqual(replace_response.body["result"]["_rev"], original_rev)
        replaced_rev = replace_response.body["result"]["_rev"]

        patch_doc = HttpRequest(
            method="PATCH",
            path=f"/_api/document/users_mut/{key}",
            api_version=1,
            body={"city": "hamburg", "active": True},
        )
        patch_handler = runtime.handler_factory.create_handler(patch_doc)
        patch_response = runtime.handler_factory.invoke(patch_handler, patch_doc)
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.body["result"]["city"], "hamburg")
        self.assertTrue(patch_response.body["result"]["active"])
        self.assertNotEqual(patch_response.body["result"]["_rev"], replaced_rev)

    def test_document_patch_with_if_match_revision(self) -> None:
        runtime = build_default_server()

        create_collection = HttpRequest(
            method="POST",
            path="/_api/collection",
            api_version=1,
            body={"name": "users_rev"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        insert_doc = HttpRequest(
            method="POST",
            path="/_api/document/users_rev",
            api_version=1,
            body={"name": "alice"},
        )
        insert_handler = runtime.handler_factory.create_handler(insert_doc)
        insert_response = runtime.handler_factory.invoke(insert_handler, insert_doc)
        self.assertEqual(insert_response.status_code, 201)
        key = insert_response.body["result"]["_key"]
        rev = insert_response.body["result"]["_rev"]

        patch_doc = HttpRequest(
            method="PATCH",
            path=f"/_api/document/users_rev/{key}",
            api_version=1,
            headers={"if-match": rev},
            body={"flag": True},
        )
        patch_handler = runtime.handler_factory.create_handler(patch_doc)
        patch_response = runtime.handler_factory.invoke(patch_handler, patch_doc)
        self.assertEqual(patch_response.status_code, 200)
        self.assertIn("etag", patch_response.headers)

    def test_document_patch_revision_mismatch_returns_412(self) -> None:
        runtime = build_default_server()

        create_collection = HttpRequest(
            method="POST",
            path="/_api/collection",
            api_version=1,
            body={"name": "users_rev_mismatch"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        insert_doc = HttpRequest(
            method="POST",
            path="/_api/document/users_rev_mismatch",
            api_version=1,
            body={"name": "alice"},
        )
        insert_handler = runtime.handler_factory.create_handler(insert_doc)
        insert_response = runtime.handler_factory.invoke(insert_handler, insert_doc)
        self.assertEqual(insert_response.status_code, 201)
        key = insert_response.body["result"]["_key"]

        patch_doc = HttpRequest(
            method="PATCH",
            path=f"/_api/document/users_rev_mismatch/{key}",
            api_version=1,
            body={"_rev": "wrong-rev", "flag": False},
        )
        patch_handler = runtime.handler_factory.create_handler(patch_doc)
        patch_response = runtime.handler_factory.invoke(patch_handler, patch_doc)
        self.assertEqual(patch_response.status_code, 412)

    def test_document_get_returns_etag(self) -> None:
        runtime = build_default_server()

        create_collection = HttpRequest(
            method="POST",
            path="/_api/collection",
            api_version=1,
            body={"name": "users_etag"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        insert_doc = HttpRequest(
            method="POST",
            path="/_api/document/users_etag",
            api_version=1,
            body={"name": "alice"},
        )
        insert_handler = runtime.handler_factory.create_handler(insert_doc)
        insert_response = runtime.handler_factory.invoke(insert_handler, insert_doc)
        self.assertEqual(insert_response.status_code, 201)
        key = insert_response.body["result"]["_key"]
        self.assertIn("etag", insert_response.headers)

        get_doc = HttpRequest(
            method="GET",
            path=f"/_api/document/users_etag/{key}",
            api_version=1,
        )
        get_handler = runtime.handler_factory.create_handler(get_doc)
        get_response = runtime.handler_factory.invoke(get_handler, get_doc)
        self.assertEqual(get_response.status_code, 200)
        self.assertIn("etag", get_response.headers)
        self.assertEqual(get_response.headers["etag"], get_response.body["result"]["_rev"])

    def test_document_delete_with_if_match(self) -> None:
        runtime = build_default_server()

        create_collection = HttpRequest(
            method="POST",
            path="/_api/collection",
            api_version=1,
            body={"name": "users_delete_rev"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        insert_doc = HttpRequest(
            method="POST",
            path="/_api/document/users_delete_rev",
            api_version=1,
            body={"name": "alice"},
        )
        insert_handler = runtime.handler_factory.create_handler(insert_doc)
        insert_response = runtime.handler_factory.invoke(insert_handler, insert_doc)
        self.assertEqual(insert_response.status_code, 201)
        key = insert_response.body["result"]["_key"]
        rev = insert_response.body["result"]["_rev"]

        bad_delete = HttpRequest(
            method="DELETE",
            path=f"/_api/document/users_delete_rev/{key}",
            api_version=1,
            headers={"if-match": "bad-rev"},
        )
        bad_handler = runtime.handler_factory.create_handler(bad_delete)
        bad_response = runtime.handler_factory.invoke(bad_handler, bad_delete)
        self.assertEqual(bad_response.status_code, 412)

        good_delete = HttpRequest(
            method="DELETE",
            path=f"/_api/document/users_delete_rev/{key}",
            api_version=1,
            headers={"if-match": rev},
        )
        good_handler = runtime.handler_factory.create_handler(good_delete)
        good_response = runtime.handler_factory.invoke(good_handler, good_delete)
        self.assertEqual(good_response.status_code, 200)

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

        count_request = HttpRequest(
            method="GET",
            path="/_db/tenant1/_api/collection/events/count",
            api_version=1,
        )
        count_handler = runtime.handler_factory.create_handler(count_request)
        count_response = runtime.handler_factory.invoke(count_handler, count_request)
        self.assertEqual(count_response.status_code, 200)
        self.assertEqual(count_response.body["result"]["count"], 1)

    def test_db_prefixed_document_patch(self) -> None:
        runtime = build_default_server()

        create_db = HttpRequest(
            method="POST",
            path="/_api/database",
            api_version=1,
            body={"name": "tenant_patch"},
        )
        db_handler = runtime.handler_factory.create_handler(create_db)
        db_response = runtime.handler_factory.invoke(db_handler, create_db)
        self.assertEqual(db_response.status_code, 201)

        create_collection = HttpRequest(
            method="POST",
            path="/_db/tenant_patch/_api/collection",
            api_version=1,
            body={"name": "events"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        insert_doc = HttpRequest(
            method="POST",
            path="/_db/tenant_patch/_api/document/events",
            api_version=1,
            body={"kind": "login", "count": 1},
        )
        insert_handler = runtime.handler_factory.create_handler(insert_doc)
        insert_response = runtime.handler_factory.invoke(insert_handler, insert_doc)
        self.assertEqual(insert_response.status_code, 201)
        key = insert_response.body["result"]["_key"]

        patch_doc = HttpRequest(
            method="PATCH",
            path=f"/_db/tenant_patch/_api/document/events/{key}",
            api_version=1,
            body={"count": 2},
        )
        patch_handler = runtime.handler_factory.create_handler(patch_doc)
        patch_response = runtime.handler_factory.invoke(patch_handler, patch_doc)
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.body["result"]["count"], 2)

    def test_db_prefixed_document_revision_precondition(self) -> None:
        runtime = build_default_server()

        create_db = HttpRequest(
            method="POST",
            path="/_api/database",
            api_version=1,
            body={"name": "tenant_rev"},
        )
        db_handler = runtime.handler_factory.create_handler(create_db)
        db_response = runtime.handler_factory.invoke(db_handler, create_db)
        self.assertEqual(db_response.status_code, 201)

        create_collection = HttpRequest(
            method="POST",
            path="/_db/tenant_rev/_api/collection",
            api_version=1,
            body={"name": "events"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        insert_doc = HttpRequest(
            method="POST",
            path="/_db/tenant_rev/_api/document/events",
            api_version=1,
            body={"kind": "login"},
        )
        insert_handler = runtime.handler_factory.create_handler(insert_doc)
        insert_response = runtime.handler_factory.invoke(insert_handler, insert_doc)
        self.assertEqual(insert_response.status_code, 201)
        key = insert_response.body["result"]["_key"]

        patch_doc = HttpRequest(
            method="PATCH",
            path=f"/_db/tenant_rev/_api/document/events/{key}",
            api_version=1,
            headers={"if-match": "bad-rev"},
            body={"kind": "logout"},
        )
        patch_handler = runtime.handler_factory.create_handler(patch_doc)
        patch_response = runtime.handler_factory.invoke(patch_handler, patch_doc)
        self.assertEqual(patch_response.status_code, 412)

    def test_db_prefixed_transaction_put_commit(self) -> None:
        runtime = build_default_server()

        begin = HttpRequest(
            method="POST",
            path="/_db/_system/_api/transaction/begin",
            api_version=1,
        )
        begin_handler = runtime.handler_factory.create_handler(begin)
        begin_response = runtime.handler_factory.invoke(begin_handler, begin)
        self.assertEqual(begin_response.status_code, 201)
        transaction_id = begin_response.body["result"]["id"]

        put_commit = HttpRequest(
            method="PUT",
            path=f"/_db/_system/_api/transaction/{transaction_id}",
            api_version=1,
        )
        put_handler = runtime.handler_factory.create_handler(put_commit)
        put_response = runtime.handler_factory.invoke(put_handler, put_commit)
        self.assertEqual(put_response.status_code, 200)
        self.assertEqual(put_response.body["result"]["status"], "commit")

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

    def test_view_lifecycle_direct_routes(self) -> None:
        runtime = build_default_server()

        create_view = HttpRequest(
            method="POST",
            path="/_api/view",
            api_version=1,
            body={"name": "v_users", "type": "search", "properties": {"cleanupIntervalStep": 2}},
        )
        create_handler = runtime.handler_factory.create_handler(create_view)
        create_response = runtime.handler_factory.invoke(create_handler, create_view)
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.body["result"]["name"], "v_users")

        list_views = HttpRequest(method="GET", path="/_api/view", api_version=1)
        list_handler = runtime.handler_factory.create_handler(list_views)
        list_response = runtime.handler_factory.invoke(list_handler, list_views)
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(any(view["name"] == "v_users" for view in list_response.body["result"]))

        get_view = HttpRequest(method="GET", path="/_api/view/v_users", api_version=1)
        get_handler = runtime.handler_factory.create_handler(get_view)
        get_response = runtime.handler_factory.invoke(get_handler, get_view)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.body["result"]["type"], "search")

        drop_view = HttpRequest(method="DELETE", path="/_api/view/v_users", api_version=1)
        drop_handler = runtime.handler_factory.create_handler(drop_view)
        drop_response = runtime.handler_factory.invoke(drop_handler, drop_view)
        self.assertEqual(drop_response.status_code, 200)

    def test_view_lifecycle_db_prefixed_routes(self) -> None:
        runtime = build_default_server()

        create_db = HttpRequest(
            method="POST",
            path="/_api/database",
            api_version=1,
            body={"name": "tenant_views"},
        )
        db_handler = runtime.handler_factory.create_handler(create_db)
        db_response = runtime.handler_factory.invoke(db_handler, create_db)
        self.assertEqual(db_response.status_code, 201)

        create_view = HttpRequest(
            method="POST",
            path="/_db/tenant_views/_api/view",
            api_version=1,
            body={"name": "v_events", "type": "search"},
        )
        create_handler = runtime.handler_factory.create_handler(create_view)
        create_response = runtime.handler_factory.invoke(create_handler, create_view)
        self.assertEqual(create_response.status_code, 201)

        get_view = HttpRequest(
            method="GET",
            path="/_db/tenant_views/_api/view/v_events",
            api_version=1,
        )
        get_handler = runtime.handler_factory.create_handler(get_view)
        get_response = runtime.handler_factory.invoke(get_handler, get_view)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.body["result"]["database"], "tenant_views")

    def test_wal_properties_and_flush(self) -> None:
        runtime = build_default_server()

        wal_props = HttpRequest(method="GET", path="/_api/wal/properties", api_version=1)
        props_handler = runtime.handler_factory.create_handler(wal_props)
        props_response = runtime.handler_factory.invoke(props_handler, wal_props)
        self.assertEqual(props_response.status_code, 200)
        self.assertIn("currentTick", props_response.body["result"])
        self.assertIn("recoveryState", props_response.body["result"])

        wal_flush = HttpRequest(method="PUT", path="/_api/wal/flush", api_version=1)
        flush_handler = runtime.handler_factory.create_handler(wal_flush)
        flush_response = runtime.handler_factory.invoke(flush_handler, wal_flush)
        self.assertEqual(flush_response.status_code, 200)
        self.assertIn("tick", flush_response.body["result"])

    def test_job_api_lifecycle(self) -> None:
        runtime = build_default_server()

        create_job = HttpRequest(
            method="POST",
            path="/_api/job",
            api_version=1,
            body={"name": "sample"},
        )
        create_handler = runtime.handler_factory.create_handler(create_job)
        create_response = runtime.handler_factory.invoke(create_handler, create_job)
        self.assertEqual(create_response.status_code, 202)
        job_id = create_response.body["result"]["id"]

        list_jobs = HttpRequest(method="GET", path="/_api/job", api_version=1)
        list_handler = runtime.handler_factory.create_handler(list_jobs)
        list_response = runtime.handler_factory.invoke(list_handler, list_jobs)
        self.assertEqual(list_response.status_code, 200)
        self.assertIn(job_id, list_response.body["result"])

        get_job = HttpRequest(method="GET", path=f"/_api/job/{job_id}", api_version=1)
        get_handler = runtime.handler_factory.create_handler(get_job)
        get_response = runtime.handler_factory.invoke(get_handler, get_job)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.body["result"]["payload"]["name"], "sample")

        done_jobs = HttpRequest(method="GET", path="/_api/job/done", api_version=1)
        done_handler = runtime.handler_factory.create_handler(done_jobs)
        done_response = runtime.handler_factory.invoke(done_handler, done_jobs)
        self.assertEqual(done_response.status_code, 200)
        self.assertIn(job_id, done_response.body["result"])

        delete_job = HttpRequest(method="DELETE", path=f"/_api/job/{job_id}", api_version=1)
        delete_handler = runtime.handler_factory.create_handler(delete_job)
        delete_response = runtime.handler_factory.invoke(delete_handler, delete_job)
        self.assertEqual(delete_response.status_code, 200)

    def test_tasks_api_lifecycle(self) -> None:
        runtime = build_default_server()

        create_task = HttpRequest(
            method="POST",
            path="/_api/tasks",
            api_version=1,
            body={"name": "cleanup", "command": "cleanup::run", "params": {"limit": 10}},
        )
        create_handler = runtime.handler_factory.create_handler(create_task)
        create_response = runtime.handler_factory.invoke(create_handler, create_task)
        self.assertEqual(create_response.status_code, 201)
        task_id = create_response.body["result"]["id"]

        list_tasks = HttpRequest(method="GET", path="/_api/tasks", api_version=1)
        list_handler = runtime.handler_factory.create_handler(list_tasks)
        list_response = runtime.handler_factory.invoke(list_handler, list_tasks)
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(any(task["id"] == task_id for task in list_response.body["result"]))

        get_task = HttpRequest(method="GET", path=f"/_api/tasks/{task_id}", api_version=1)
        get_handler = runtime.handler_factory.create_handler(get_task)
        get_response = runtime.handler_factory.invoke(get_handler, get_task)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.body["result"]["name"], "cleanup")

        delete_task = HttpRequest(method="DELETE", path=f"/_api/tasks/{task_id}", api_version=1)
        delete_handler = runtime.handler_factory.create_handler(delete_task)
        delete_response = runtime.handler_factory.invoke(delete_handler, delete_task)
        self.assertEqual(delete_response.status_code, 200)

    def test_edges_insert_and_get(self) -> None:
        runtime = build_default_server()

        create_collection = HttpRequest(
            method="POST",
            path="/_api/collection",
            api_version=1,
            body={"name": "relations"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        insert_edge = HttpRequest(
            method="POST",
            path="/_api/edges/relations",
            api_version=1,
            body={"_from": "users/alice", "_to": "users/bob", "kind": "knows"},
        )
        insert_handler = runtime.handler_factory.create_handler(insert_edge)
        insert_response = runtime.handler_factory.invoke(insert_handler, insert_edge)
        self.assertEqual(insert_response.status_code, 201)
        key = insert_response.body["result"]["_key"]

        get_edge = HttpRequest(
            method="GET",
            path=f"/_api/edges/relations/{key}",
            api_version=1,
        )
        get_handler = runtime.handler_factory.create_handler(get_edge)
        get_response = runtime.handler_factory.invoke(get_handler, get_edge)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.body["result"]["kind"], "knows")

    def test_edges_requires_from_to(self) -> None:
        runtime = build_default_server()

        create_collection = HttpRequest(
            method="POST",
            path="/_api/collection",
            api_version=1,
            body={"name": "relations2"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        insert_edge = HttpRequest(
            method="POST",
            path="/_api/edges/relations2",
            api_version=1,
            body={"kind": "invalid"},
        )
        insert_handler = runtime.handler_factory.create_handler(insert_edge)
        insert_response = runtime.handler_factory.invoke(insert_handler, insert_edge)
        self.assertEqual(insert_response.status_code, 400)

    def test_db_prefixed_edges_routes(self) -> None:
        runtime = build_default_server()

        create_db = HttpRequest(
            method="POST",
            path="/_api/database",
            api_version=1,
            body={"name": "tenant_edges"},
        )
        db_handler = runtime.handler_factory.create_handler(create_db)
        db_response = runtime.handler_factory.invoke(db_handler, create_db)
        self.assertEqual(db_response.status_code, 201)

        create_collection = HttpRequest(
            method="POST",
            path="/_db/tenant_edges/_api/collection",
            api_version=1,
            body={"name": "relations"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        insert_edge = HttpRequest(
            method="POST",
            path="/_db/tenant_edges/_api/edges/relations",
            api_version=1,
            body={"_from": "users/a", "_to": "users/b"},
        )
        insert_handler = runtime.handler_factory.create_handler(insert_edge)
        insert_response = runtime.handler_factory.invoke(insert_handler, insert_edge)
        self.assertEqual(insert_response.status_code, 201)

    def test_import_bulk_documents(self) -> None:
        runtime = build_default_server()

        create_collection = HttpRequest(
            method="POST",
            path="/_api/collection",
            api_version=1,
            body={"name": "bulk_docs"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        import_request = HttpRequest(
            method="POST",
            path="/_api/import/bulk_docs",
            api_version=1,
            body=[{"value": 1}, {"value": 2}, {"value": 3}],
        )
        import_handler = runtime.handler_factory.create_handler(import_request)
        import_response = runtime.handler_factory.invoke(import_handler, import_request)
        self.assertEqual(import_response.status_code, 201)
        self.assertEqual(import_response.body["result"]["created"], 3)
        self.assertEqual(import_response.body["result"]["errors"], 0)

    def test_db_prefixed_import_with_collection_in_body(self) -> None:
        runtime = build_default_server()

        create_db = HttpRequest(
            method="POST",
            path="/_api/database",
            api_version=1,
            body={"name": "tenant_import"},
        )
        db_handler = runtime.handler_factory.create_handler(create_db)
        db_response = runtime.handler_factory.invoke(db_handler, create_db)
        self.assertEqual(db_response.status_code, 201)

        create_collection = HttpRequest(
            method="POST",
            path="/_db/tenant_import/_api/collection",
            api_version=1,
            body={"name": "events"},
        )
        collection_handler = runtime.handler_factory.create_handler(create_collection)
        collection_response = runtime.handler_factory.invoke(collection_handler, create_collection)
        self.assertEqual(collection_response.status_code, 201)

        import_request = HttpRequest(
            method="POST",
            path="/_db/tenant_import/_api/import",
            api_version=1,
            body={
                "collection": "events",
                "documents": [{"kind": "a"}, {"kind": "b"}],
            },
        )
        import_handler = runtime.handler_factory.create_handler(import_request)
        import_response = runtime.handler_factory.invoke(import_handler, import_request)
        self.assertEqual(import_response.status_code, 201)
        self.assertEqual(import_response.body["result"]["created"], 2)

    def test_import_requires_document_list(self) -> None:
        runtime = build_default_server()

        bad_import = HttpRequest(
            method="POST",
            path="/_api/import/missing_docs",
            api_version=1,
            body={"collection": "missing_docs"},
        )
        handler = runtime.handler_factory.create_handler(bad_import)
        response = runtime.handler_factory.invoke(handler, bad_import)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
