"""At-least-once SQS worker; DynamoDB conditional leases guard duplicate work."""
import json
import time
import uuid
from datetime import datetime, timezone

from pulseops import store
from pulseops.settings import settings
from pulseops.telemetry import log_event, metric


class SimulatedDeliveryFailure(Exception):
    pass


def process_record(record: dict) -> None:
    payload = json.loads(record["body"])
    job_id = payload["job_id"]
    if not isinstance(job_id, str) or len(job_id) != 24:
        raise ValueError("Malformed job ID")

    existing = store.get_raw_job(job_id)
    if existing is None:
        # A poison message must fail and eventually land in the DLQ.
        raise ValueError("Message referenced a missing job")
    if existing["status"] in ("published", "failed"):
        log_event("duplicate_skipped", job_id=job_id, status=existing["status"])
        return

    token = str(uuid.uuid4())
    epoch = int(time.time())
    started = time.monotonic()
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    try:
        claimed = store.acquire_lease(job_id, token, epoch, now)
    except store.LeaseBusy:
        # Another worker may still own this message. Retry rather than ack it.
        current = store.get_raw_job(job_id)
        if current and current.get("status") in ("published", "failed"):
            return
        raise

    attempt = int(claimed["attempts"])
    mode = claimed.get("failure_mode", "none")
    try:
        if mode == "permanent":
            raise SimulatedDeliveryFailure("Simulated downstream service rejected request")
        if mode == "transient" and attempt <= 2:
            raise SimulatedDeliveryFailure("Simulated HTTP 503 from downstream service")
        # Simulated external delivery; real integrations require a provider's
        # idempotency mechanism for end-to-end exactly-once effects.
        store.finish_job(job_id, token, store.now_iso())
        metric("JobPublished")
        metric("ProcessingLatencyMs", (time.monotonic() - started) * 1000, "Milliseconds")
        log_event("job_published", job_id=job_id, attempt=attempt)
    except Exception as error:
        terminal = attempt >= settings.max_attempts
        store.fail_attempt(job_id, token, str(error), terminal)
        metric("JobFailed" if terminal else "JobRetried")
        log_event(
            "job_failed" if terminal else "job_retry",
            job_id=job_id, attempt=attempt,
            error_type=type(error).__name__, terminal=terminal,
        )
        # Returning this message ID in batchItemFailures makes SQS redrive it.
        # This includes the final failed attempt, allowing the DLQ to capture it.
        raise


def handler(event: dict, _context) -> dict:
    failures = []
    for record in event.get("Records", []):
        try:
            process_record({"body": record["body"]})
        except Exception as error:
            log_event("record_error", message_id=record.get("messageId", "unknown"),
                      error_type=type(error).__name__)
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
