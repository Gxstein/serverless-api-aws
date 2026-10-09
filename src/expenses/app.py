"""Expenses API - single Lambda function behind an API Gateway HTTP API (payload v2).

Routes
  GET    /expenses            list expenses (optional ?category=)
  POST   /expenses            create an expense
  GET    /expenses/summary    totals per category
  GET    /expenses/{id}       get one expense
  DELETE /expenses/{id}       delete one expense
"""

import json
import logging
import os
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import boto3
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CATEGORIES = {"alimentacao", "transporte", "moradia", "lazer", "saude", "educacao", "outros"}
MAX_AMOUNT = Decimal("1000000")

_table = None


def get_table():
    """Created lazily and reused across invocations of the same execution environment."""
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
    return _table


class ValidationError(Exception):
    pass


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def response(status: int, body=None) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": "" if body is None else json.dumps(body, cls=DecimalEncoder, ensure_ascii=False),
    }


# ---------- validation ----------


def parse_body(event: dict) -> dict:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        import base64

        raw = base64.b64decode(raw).decode("utf-8")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("Body must be valid JSON") from exc
    if not isinstance(body, dict):
        raise ValidationError("Body must be a JSON object")
    return body


def validate_expense(body: dict) -> dict:
    description = str(body.get("description", "")).strip()
    if not 1 <= len(description) <= 200:
        raise ValidationError("description must have between 1 and 200 characters")

    try:
        amount = Decimal(str(body.get("amount"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("amount must be a number") from exc
    if not Decimal("0") < amount <= MAX_AMOUNT:
        raise ValidationError("amount must be greater than 0 and at most 1000000")

    category = str(body.get("category", "outros")).strip().lower()
    if category not in CATEGORIES:
        raise ValidationError(f"category must be one of: {', '.join(sorted(CATEGORIES))}")

    spent_on = body.get("date") or date.today().isoformat()
    try:
        date.fromisoformat(spent_on)
    except (TypeError, ValueError) as exc:
        raise ValidationError("date must use the format YYYY-MM-DD") from exc

    return {"description": description, "amount": amount, "category": category, "date": spent_on}


# ---------- handlers ----------


def scan_all(**kwargs) -> list[dict]:
    """Scan with pagination. Fine for a small personal table; a GSI would replace it at scale."""
    table = get_table()
    items, start_key = [], None
    while True:
        if start_key:
            kwargs["ExclusiveStartKey"] = start_key
        page = table.scan(**kwargs)
        items.extend(page.get("Items", []))
        start_key = page.get("LastEvaluatedKey")
        if not start_key:
            return items


def list_expenses(event: dict) -> dict:
    category = (event.get("queryStringParameters") or {}).get("category")
    kwargs = {"FilterExpression": Attr("category").eq(category.lower())} if category else {}
    items = scan_all(**kwargs)
    items.sort(key=lambda item: (item["date"], item["created_at"]), reverse=True)
    return response(200, items)


def create_expense(event: dict) -> dict:
    item = validate_expense(parse_body(event))
    item["id"] = str(uuid.uuid4())
    item["created_at"] = datetime.now(timezone.utc).isoformat()
    get_table().put_item(Item=item)
    logger.info("expense created", extra={"expense_id": item["id"], "category": item["category"]})
    return response(201, item)


def get_expense(expense_id: str) -> dict:
    item = get_table().get_item(Key={"id": expense_id}).get("Item")
    if item is None:
        return response(404, {"message": "Expense not found"})
    return response(200, item)


def delete_expense(expense_id: str) -> dict:
    result = get_table().delete_item(Key={"id": expense_id}, ReturnValues="ALL_OLD")
    if "Attributes" not in result:
        return response(404, {"message": "Expense not found"})
    return response(204)


def summary() -> dict:
    totals: dict[str, Decimal] = {}
    for item in scan_all(ProjectionExpression="category, amount"):
        totals[item["category"]] = totals.get(item["category"], Decimal("0")) + item["amount"]
    return response(
        200,
        {
            "total": sum(totals.values(), Decimal("0")),
            "by_category": dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True)),
        },
    )


ROUTES = {
    "GET /expenses": lambda event: list_expenses(event),
    "POST /expenses": lambda event: create_expense(event),
    "GET /expenses/summary": lambda event: summary(),
    "GET /expenses/{id}": lambda event: get_expense(event["pathParameters"]["id"]),
    "DELETE /expenses/{id}": lambda event: delete_expense(event["pathParameters"]["id"]),
}


def handler(event, context):
    route = event.get("routeKey", "")
    action = ROUTES.get(route)
    if action is None:
        return response(404, {"message": f"Route not found: {route}"})
    try:
        return action(event)
    except ValidationError as exc:
        return response(400, {"message": str(exc)})
    except Exception:  # noqa: BLE001 - never leak internals to the client
        logger.exception("unhandled error", extra={"route": route})
        return response(500, {"message": "Internal server error"})
