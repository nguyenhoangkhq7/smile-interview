"""Unit tests for the standalone code-runner FastAPI sandbox service."""
import importlib.util

import pytest
from fastapi.testclient import TestClient

from server import app


client = TestClient(app)
HAS_FAKEREDIS = importlib.util.find_spec("redis") is not None and importlib.util.find_spec("fakeredis") is not None
HAS_MONGOMOCK = importlib.util.find_spec("pymongo") is not None and importlib.util.find_spec("mongomock") is not None


def test_health_lists_supported_languages_and_shims():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["languages"] == ["python", "javascript", "sql"]
    assert isinstance(body["shims"], list)


def test_execute_python_multi_arg_list_dict_bytes_and_sql():
    py_res = client.post("/execute", json={
        "language": "python",
        "code": "def combine(user_id, data):\n    return f'{user_id}:{data}'\n",
        "entry_point": "combine",
        "cases": [
            {"name": "list_args", "input_data": '["u1", "Alice"]', "expected_output": '"u1:Alice"'},
            {"name": "dict_kwargs", "input_data": '{"user_id": "u2", "data": "Bob"}', "expected_output": '"u2:Bob"'},
        ],
    })
    assert py_res.status_code == 200
    assert py_res.json()["passed"] == 2 and py_res.json()["total"] == 2

    bytes_res = client.post("/execute", json={
        "language": "python",
        "code": "def echo_bytes(val):\n    return val.encode('utf-8')\n",
        "entry_point": "echo_bytes",
        "cases": [{"name": "bytes_ok", "input_data": '"ok"', "expected_output": '"ok"'}],
    })
    assert bytes_res.status_code == 200
    assert bytes_res.json()["passed"] == 1

    sql_res = client.post("/execute", json={
        "language": "sql",
        "setup_sql": "CREATE TABLE items(id INT, qty INT); INSERT INTO items VALUES (1, 10), (2, 0);",
        "code": "SELECT id FROM items WHERE qty > 0;",
        "cases": [{"name": "c1", "input_data": "", "expected_output": "[[1]]"}],
    })
    assert sql_res.status_code == 200
    assert sql_res.json()["passed"] == 1 and sql_res.json()["total"] == 1


def test_single_function_fallback_and_multi_function_error_hint():
    single = client.post("/execute", json={
        "language": "python",
        "code": "def save_and_get_user(user_id, data):\n    return f'{user_id}:{data}'\n",
        "entry_point": "save_and_get",
        "cases": [{"name": "fallback_ok", "input_data": '["u1", "Alice"]', "expected_output": '"u1:Alice"'}],
    })
    assert single.status_code == 200
    assert single.json()["passed"] == 1 and single.json()["total"] == 1

    ambiguous = client.post("/execute", json={
        "language": "python",
        "code": "def helper_a(x): return x\ndef helper_b(x): return x\n",
        "entry_point": "save_and_get",
        "cases": [{"name": "multi", "input_data": "1", "expected_output": "1"}],
    })
    assert ambiguous.status_code == 200
    assert ambiguous.json()["passed"] == 0
    assert "helper_a" in ambiguous.json()["results"][0]["error"]
    assert "helper_b" in ambiguous.json()["results"][0]["error"]


@pytest.mark.skipif(not HAS_FAKEREDIS, reason="redis/fakeredis not installed in host test env")
def test_execute_redis_in_memory_shim_and_isolation():
    code = (
        "import redis\n"
        "r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)\n"
        "def save_and_get_user(user_id, data):\n"
        "    key = f'user:{user_id}'\n"
        "    r.set(key, data, ex=3600)\n"
        "    return {'value': r.get(key), 'has_ttl': r.ttl(key) > 0, 'keys': len(r.keys('user:*'))}\n"
    )
    res = client.post("/execute", json={
        "language": "python",
        "code": code,
        "entry_point": "save_and_get_user",
        "cases": [
            {
                "name": "list_case",
                "input_data": '["101", "Alice"]',
                "expected_output": '{"value": "Alice", "has_ttl": true, "keys": 1}',
            },
            {
                "name": "dict_case_isolated",
                "input_data": '{"user_id": "202", "data": "Bob"}',
                "expected_output": '{"value": "Bob", "has_ttl": true, "keys": 1}',
            },
        ],
    })
    assert res.status_code == 200
    body = res.json()
    assert body["passed"] == 2 and body["total"] == 2, body

    free_res = client.post("/execute", json={
        "language": "python",
        "code": (
            "import redis\n"
            "r = redis.from_url('redis://localhost:6379/0', decode_responses=True)\n"
            "r.set('k', 'v', ex=60)\n"
            "print(r.get('k'))\n"
        ),
    })
    assert free_res.status_code == 200
    assert free_res.json()["compile_error"] == ""
    assert free_res.json()["stdout"].strip() == "v"


@pytest.mark.skipif(not HAS_MONGOMOCK, reason="pymongo/mongomock not installed in host test env")
def test_execute_pymongo_in_memory_shim():
    code = (
        "from pymongo import MongoClient\n"
        "client = MongoClient('mongodb://localhost:27017')\n"
        "def save_doc(name):\n"
        "    col = client['app']['users']\n"
        "    col.insert_one({'name': name})\n"
        "    return col.count_documents({'name': name})\n"
    )
    res = client.post("/execute", json={
        "language": "python",
        "code": code,
        "entry_point": "save_doc",
        "cases": [{"name": "insert_and_count", "input_data": '"Lan"', "expected_output": "1"}],
    })
    assert res.status_code == 200
    body = res.json()
    assert body["passed"] == 1 and body["total"] == 1, body
