"""Unit tests for the standalone code-runner FastAPI sandbox service."""
from fastapi.testclient import TestClient

from server import app


client = TestClient(app)


def test_health_lists_supported_languages():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "languages": ["python", "javascript", "sql"]}


def test_execute_python_and_sql_cases():
    py_res = client.post("/execute", json={
        "language": "python",
        "code": "def square(x):\n    return x * x\n",
        "entry_point": "square",
        "cases": [{"name": "c1", "input_data": "5", "expected_output": "25"}],
    })
    assert py_res.status_code == 200
    assert py_res.json()["passed"] == 1 and py_res.json()["total"] == 1

    sql_res = client.post("/execute", json={
        "language": "sql",
        "setup_sql": "CREATE TABLE items(id INT, qty INT); INSERT INTO items VALUES (1, 10), (2, 0);",
        "code": "SELECT id FROM items WHERE qty > 0;",
        "cases": [{"name": "c1", "input_data": "", "expected_output": "[[1]]"}],
    })
    assert sql_res.status_code == 200
    assert sql_res.json()["passed"] == 1 and sql_res.json()["total"] == 1
