"""DynamoDB operations with conditional writes and expiring worker leases."""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr

from pulseops.aws_clients import dynamodb_table
from pulseops.models import NewJob


class IdempotencyConflict(Exception):
    """Same idempotency key submitted with different payloads."""


class LeaseBusy(Exception):
    """Another worker is currently processing this job."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def is_conditional_failure(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def public_job(item: dict) -> dict:
    return {
        field: (int(item.get(field, 0)) if field == "attempts" else item.get(field))
        for field in (
            "id", "channel", "content", "failure_mode", "status", "attempts",
            "created_at", "updated_at", "published_at", "last_error",
        )
    }


def create_or_get_job(request: NewJob, key: str | None) -> tuple[dict, bool]:
    # Clients should supply a unique, secret-free idempotency key per operation.
    stable_key = key or str(uuid.uuid4())
    job_id = hashlib.sha256(f"pulseops:v1:{stable_key}".encode()).hexdigest()[:24]
    fingerprint = hashlib.sha256(
        json.dumps(request.model_dump(), sort_keys=True).encode()
    ).hexdigest()
    created = now_iso()
    item = {
        "pk": f"JOB#{job_id}", "id": job_id,
        **request.model_dump(),
        "fingerprint": fingerprint,
        "status": "queued", "attempts": 0,
        "created_at": created, "updated_at": created,
    }
    table = dynamodb_table()
    try:
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(pk)")
        return public_job(item), True
    except ClientError as error:
        if not is_conditional_failure(error):
            raise
    existing = table.get_item(Key={"pk": f"JOB#{job_id}"}, ConsistentRead=True).get("Item")
    if not existing or existing.get("fingerprint") != fingerprint:
        raise IdempotencyConflict("Idempotency key was already used for a different post")
    return public_job(existing), False


def get_job(job_id: str) -> dict | None:
    item = dynamodb_table().get_item(
        Key={"pk": f"JOB#{job_id}"}, ConsistentRead=True
    ).get("Item")
    return public_job(item) if item else None


def get_raw_job(job_id: str) -> dict | None:
    return dynamodb_table().get_item(
        Key={"pk": f"JOB#{job_id}"}, ConsistentRead=True
    ).get("Item")


def list_jobs(limit: int = 100) -> list[dict]:
    # Small demo only: a Scan is NOT a scalable way to build a production feed.
    response = dynamodb_table().scan(
        FilterExpression=Attr("pk").begins_with("JOB#"), Limit=250
    )
    jobs = [public_job(item) for item in response.get("Items", [])]
    return sorted(jobs, key=lambda item: item["created_at"], reverse=True)[:limit]


def acquire_lease(job_id: str, token: str, epoch: int, iso: str) -> dict:
    try:
        response = dynamodb_table().update_item(
            Key={"pk": f"JOB#{job_id}"},
            UpdateExpression=(
                "SET #s = :processing, lease_until = :lease, lease_token = :token, "
                "updated_at = :iso ADD attempts :one"
            ),
            ConditionExpression=(
                "#s = :queued OR (#s = :processing AND lease_until < :epoch)"
            ),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":processing": "processing", ":queued": "queued",
                ":lease": epoch + 90, ":epoch": epoch,
                ":token": token, ":iso": iso, ":one": 1,
            },
            ReturnValues="ALL_NEW",
        )
        return response["Attributes"]
    except ClientError as error:
        if is_conditional_failure(error):
            raise LeaseBusy from error
        raise


def finish_job(job_id: str, token: str, completed: str) -> None:
    dynamodb_table().update_item(
        Key={"pk": f"JOB#{job_id}"},
        UpdateExpression=(
            "SET #s = :published, updated_at = :now, published_at = :now "
            "REMOVE lease_until, lease_token, last_error"
        ),
        ConditionExpression="#s = :processing AND lease_token = :token",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":published": "published", ":processing": "processing",
            ":token": token, ":now": completed,
        },
    )


def fail_attempt(job_id: str, token: str, error_message: str, terminal: bool) -> None:
    dynamodb_table().update_item(
        Key={"pk": f"JOB#{job_id}"},
        UpdateExpression=(
            "SET #s = :status, updated_at = :now, last_error = :error "
            "REMOVE lease_until, lease_token"
        ),
        ConditionExpression="#s = :processing AND lease_token = :token",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":status": "failed" if terminal else "queued",
            ":processing": "processing", ":token": token,
            ":now": now_iso(), ":error": error_message[:180],
        },
    )
