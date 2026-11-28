"""Unit tests for the standalone code-runner FastAPI sandbox service."""
import importlib.util
import shutil

import pytest
from fastapi.testclient import TestClient

from server import app


client = TestClient(app)
HAS_FAKEREDIS = importlib.util.find_spec("redis") is not None and importlib.util.find_spec("fakeredis") is not None
HAS_MONGOMOCK = importlib.util.find_spec("pymongo") is not None and importlib.util.find_spec("mongomock") is not None
HAS_NODE = shutil.which("node") is not None


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


@pytest.mark.skipif(not HAS_NODE, reason="node runtime not installed in host test env")
def test_execute_javascript_kwargs_default_params_and_async():
    kwargs_and_defaults = client.post("/execute", json={
        "language": "javascript",
        "code": "function formatOrder(userId, prefix = 'ORD') { return `${prefix}:${userId}`; }",
        "entry_point": "formatOrder",
        "cases": [
            {"name": "dict_full", "input_data": '{"userId": "42", "prefix": "VIP"}', "expected_output": '"VIP:42"'},
            {"name": "dict_default", "input_data": '{"userId": "42"}', "expected_output": '"ORD:42"'},
            {"name": "array_args", "input_data": '["7", "PRO"]', "expected_output": '"PRO:7"'},
            {"name": "single_scalar", "input_data": '"9"', "expected_output": '"ORD:9"'},
        ],
    })
    assert kwargs_and_defaults.status_code == 200
    body = kwargs_and_defaults.json()
    assert body["passed"] == 4 and body["total"] == 4, body

    async_res = client.post("/execute", json={
        "language": "javascript",
        "code": "async function sumAsync(a, b = 10) { return Promise.resolve(a + b); }",
        "entry_point": "sumAsync",
        "cases": [
            {"name": "async_array", "input_data": "[5, 3]", "expected_output": "8"},
            {"name": "async_kwargs_default", "input_data": '{"a": 5}', "expected_output": "15"},
        ],
    })
    assert async_res.status_code == 200
    async_body = async_res.json()
    assert async_body["passed"] == 2 and async_body["total"] == 2, async_body

    destructured = client.post("/execute", json={
        "language": "javascript",
        "code": "function sumObj({ a, b }) { return a + b; }",
        "entry_point": "sumObj",
        "cases": [{"name": "destructured", "input_data": '{"a": 2, "b": 3}', "expected_output": "5"}],
    })
    assert destructured.status_code == 200
    assert destructured.json()["passed"] == 1

    single_obj = client.post("/execute", json={
        "language": "javascript",
        "code": "function countKeys(obj) { return Object.keys(obj).length; }",
        "entry_point": "countKeys",
        "cases": [{"name": "single_obj", "input_data": '{"obj": 1, "extra": 2}', "expected_output": "2"}],
    })
    assert single_obj.status_code == 200
    assert single_obj.json()["passed"] == 1


def test_execute_python_async_entry_point():
    res = client.post("/execute", json={
        "language": "python",
        "code": (
            "import asyncio\n"
            "async def fetch_sum(a, b=10):\n"
            "    await asyncio.sleep(0)\n"
            "    return a + b\n"
        ),
        "entry_point": "fetch_sum",
        "cases": [
            {"name": "async_list", "input_data": "[3, 4]", "expected_output": "7"},
            {"name": "async_kwargs_default", "input_data": '{"a": 5}', "expected_output": "15"},
        ],
    })
    assert res.status_code == 200
    body = res.json()
    assert body["compile_error"] == ""
    assert body["passed"] == 2 and body["total"] == 2, body


def test_sql_multi_statement_unordered_rows_float_tolerance_and_deterministic_set():
    # Multi-statement SQL (CREATE INDEX + SELECT + trailing comment) and unordered rows without ORDER BY
    sql_multi = client.post("/execute", json={
        "language": "sql",
        "setup_sql": "CREATE TABLE items(id INT, grp TEXT, val REAL); INSERT INTO items VALUES (1,'a',0.1),(2,'b',0.2),(3,'a',0.2);",
        "code": "CREATE INDEX idx_grp ON items(grp); SELECT grp, SUM(val) FROM items GROUP BY grp; -- trailing comment",
        "cases": [{"name": "unordered_and_float", "input_data": "", "expected_output": '[["b", 0.2], ["a", 0.3]]'}],
    })
    assert sql_multi.status_code == 200
    assert sql_multi.json()["passed"] == 1, sql_multi.json()

    # SQL WITH ORDER BY must still enforce exact row order
    sql_ordered = client.post("/execute", json={
        "language": "sql",
        "setup_sql": "CREATE TABLE nums(n INT); INSERT INTO nums VALUES (2),(1);",
        "code": "SELECT n FROM nums ORDER BY n ASC;",
        "cases": [{"name": "wrong_order_fails", "input_data": "", "expected_output": "[[2], [1]]"}],
    })
    assert sql_ordered.status_code == 200
    assert sql_ordered.json()["passed"] == 0

    # Float tolerance and deterministic set output in Python (while keeping True != 1 strict)
    py_float_set = client.post("/execute", json={
        "language": "python",
        "code": "def calc(a, b):\n    return {'sum': a + b, 'tags': {'b', 'a'}, 'flag': True}\n",
        "entry_point": "calc",
        "cases": [
            {"name": "float_and_set", "input_data": "[0.1, 0.2]", "expected_output": '{"sum": 0.3, "tags": ["a", "b"], "flag": true}'},
            {"name": "bool_not_int", "input_data": "[0.1, 0.2]", "expected_output": '{"sum": 0.3, "tags": ["a", "b"], "flag": 1}'},
        ],
    })
    assert py_float_set.status_code == 200
    body = py_float_set.json()
    assert body["results"][0]["passed"] is True, body
    assert body["results"][1]["passed"] is False, body


@pytest.mark.skipif(not HAS_NODE, reason="node runtime not installed in host test env")
def test_execute_javascript_supports_es_module_export_syntax():
    snippets = [
        ("export function add(a, b) { return a + b; }", "add"),
        ("export const add = (a, b) => a + b;", "add"),
        ("export default async function add(a, b) { return a + b; }", "add"),
        ("export default (a, b) => a + b;", "add"),
        ("function sumImpl(a, b) { return a + b; }\nexport { sumImpl as add };", "add"),
        ("export function customAdd(a, b) { return a + b; }", "add"),
    ]
    for code, entry_point in snippets:
        res = client.post("/execute", json={
            "language": "javascript",
            "code": code,
            "entry_point": entry_point,
            "cases": [{"name": "esm", "input_data": "[4, 6]", "expected_output": "10"}],
        })
        assert res.status_code == 200, code
        body = res.json()
        assert body["compile_error"] == "", (code, body)
        assert body["passed"] == 1 and body["total"] == 1, (code, body)
