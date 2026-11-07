"""Fast, offline doubles for DynamoDB and SQS; no AWS account required."""
from copy import deepcopy
from types import SimpleNamespace

from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
import pytest

from pulseops import api, store, worker


def conditional_failure():
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Conditional check failed"}},
        "UpdateItem",
    )


class FakeDynamoTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item, ConditionExpression):
        assert ConditionExpression == "attribute_not_exists(pk)"
        if Item["pk"] in self.items:
            raise conditional_failure()
        self.items[Item["pk"]] = deepcopy(Item)
        return {}

    def get_item(self, Key, **_kwargs):
        item = self.items.get(Key["pk"])
        return {"Item": deepcopy(item)} if item else {}

    def scan(self, **_kwargs):
        return {"Items": [deepcopy(item) for item in self.items.values()]}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues, **_kwargs):
        item = self.items.get(Key["pk"])
        if item is None:
            raise conditional_failure()
        vals = ExpressionAttributeValues
        if ":one" in vals:  # acquire
            eligible = item["status"] == "queued" or (
                item["status"] == "processing" and item.get("lease_until", 0) < vals[":epoch"]
            )
            if not eligible:
                raise conditional_failure()
            item.update(status="processing", lease_until=vals[":lease"],
                        lease_token=vals[":token"], updated_at=vals[":iso"])
            item["attempts"] += vals[":one"]
            return {"Attributes": deepcopy(item)}
        if item.get("status") != "processing" or item.get("lease_token") != vals[":token"]:
            raise conditional_failure()
        if ":published" in vals:
            item.update(status="published", updated_at=vals[":now"], published_at=vals[":now"])
            item.pop("last_error", None)
        elif ":status" in vals:
            item.update(status=vals[":status"], updated_at=vals[":now"], last_error=vals[":error"])
        else:
            raise AssertionError("Unrecognized update expression")
        item.pop("lease_until", None)
        item.pop("lease_token", None)
        return {}


class FakeSQS:
    def __init__(self):
        self.messages = []
        self.fail = False

    def send_message(self, QueueUrl, MessageBody):
        if self.fail:
            raise ConnectionError("Simulated unavailable SQS")
        self.messages.append(MessageBody)
        return {"MessageId": str(len(self.messages))}


@pytest.fixture
def rig(monkeypatch):
    table = FakeDynamoTable()
    sqs = FakeSQS()
    monkeypatch.setattr(store, "dynamodb_table", lambda: table)
    monkeypatch.setattr(api, "sqs_client", lambda: sqs)
    monkeypatch.setattr(api, "queue_url", lambda: "https://fake-sqs.example/jobs")
    monkeypatch.setattr(api, "settings", SimpleNamespace(demo_api_key="test-secret"))
    monkeypatch.setattr(worker, "settings", SimpleNamespace(max_attempts=4))
    return SimpleNamespace(table=table, sqs=sqs, client=TestClient(api.app))
