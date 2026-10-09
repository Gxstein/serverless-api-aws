import json
import os

import boto3
import pytest
from moto import mock_aws

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ["TABLE_NAME"] = "expenses-test"

from expenses import app  # noqa: E402


@pytest.fixture
def table():
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        created = resource.create_table(
            TableName="expenses-test",
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        )
        app._table = None  # force the handler to bind to the mocked table
        yield created
        app._table = None


def call(route: str, body=None, path_id=None, query=None):
    event = {"routeKey": route}
    if body is not None:
        event["body"] = json.dumps(body)
    if path_id is not None:
        event["pathParameters"] = {"id": path_id}
    if query is not None:
        event["queryStringParameters"] = query
    result = app.handler(event, None)
    payload = json.loads(result["body"]) if result["body"] else None
    return result["statusCode"], payload


def test_create_expense(table):
    status, body = call(
        "POST /expenses",
        {"description": "Almoço", "amount": 32.9, "category": "alimentacao", "date": "2026-10-05"},
    )
    assert status == 201
    assert body["amount"] == 32.9
    assert body["category"] == "alimentacao"
    assert len(body["id"]) == 36


def test_amount_is_rounded_to_cents(table):
    status, body = call("POST /expenses", {"description": "Café", "amount": "4.555"})
    assert status == 201
    assert body["amount"] == 4.56
    assert body["category"] == "outros"


def test_get_and_delete_expense(table):
    _, created = call("POST /expenses", {"description": "Ônibus", "amount": 5, "category": "transporte"})

    status, body = call("GET /expenses/{id}", path_id=created["id"])
    assert status == 200
    assert body["description"] == "Ônibus"

    status, _ = call("DELETE /expenses/{id}", path_id=created["id"])
    assert status == 204

    status, _ = call("GET /expenses/{id}", path_id=created["id"])
    assert status == 404


def test_delete_missing_expense(table):
    status, _ = call("DELETE /expenses/{id}", path_id="does-not-exist")
    assert status == 404


def test_list_filters_by_category(table):
    call("POST /expenses", {"description": "Mercado", "amount": 100, "category": "alimentacao"})
    call("POST /expenses", {"description": "Uber", "amount": 20, "category": "transporte"})

    status, body = call("GET /expenses")
    assert status == 200
    assert len(body) == 2

    status, body = call("GET /expenses", query={"category": "transporte"})
    assert [item["description"] for item in body] == ["Uber"]


def test_summary_totals(table):
    call("POST /expenses", {"description": "Mercado", "amount": 100.10, "category": "alimentacao"})
    call("POST /expenses", {"description": "Padaria", "amount": 9.90, "category": "alimentacao"})
    call("POST /expenses", {"description": "Cinema", "amount": 40, "category": "lazer"})

    status, body = call("GET /expenses/summary")
    assert status == 200
    assert body["total"] == 150.0
    assert body["by_category"] == {"alimentacao": 110.0, "lazer": 40.0}


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"description": "", "amount": 10}, "description"),
        ({"description": "x", "amount": -1}, "amount"),
        ({"description": "x", "amount": "abc"}, "amount"),
        ({"description": "x", "amount": 10, "category": "viagem"}, "category"),
        ({"description": "x", "amount": 10, "date": "05/10/2026"}, "date"),
    ],
)
def test_validation_errors(table, payload, message):
    status, body = call("POST /expenses", payload)
    assert status == 400
    assert message in body["message"]


def test_invalid_json(table):
    result = app.handler({"routeKey": "POST /expenses", "body": "{not json"}, None)
    assert result["statusCode"] == 400


def test_unknown_route(table):
    status, _ = call("PUT /expenses")
    assert status == 404


def test_unexpected_error_returns_500(table, monkeypatch):
    def boom(**_):
        raise RuntimeError("dynamodb down")

    monkeypatch.setattr(app.get_table(), "scan", boom)
    status, body = call("GET /expenses")
    assert status == 500
    assert body == {"message": "Internal server error"}
