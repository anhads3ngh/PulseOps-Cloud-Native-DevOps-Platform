import json

from pulseops.worker import handler


def enqueue(rig, mode="none", key="job-1"):
    response = rig.client.post(
        "/api/jobs", json={"channel": "x", "content": "Reliable demo", "failure_mode": mode},
        headers={"X-Demo-Key": "test-secret", "Idempotency-Key": key},
    )
    assert response.status_code == 202
    job = response.json()
    return job["id"], {"messageId": "message-1", "body": json.dumps({"job_id": job["id"]})}


def test_successful_delivery_and_duplicate_message_ack(rig):
    job_id, record = enqueue(rig)
    assert handler({"Records": [record]}, None) == {"batchItemFailures": []}
    item = rig.client.get(f"/api/jobs/{job_id}").json()
    assert item["status"] == "published"
    assert item["attempts"] == 1
    assert item["published_at"]
    assert handler({"Records": [record]}, None) == {"batchItemFailures": []}
    assert rig.client.get(f"/api/jobs/{job_id}").json()["attempts"] == 1


def test_transient_outage_retries_and_then_recovers(rig):
    job_id, record = enqueue(rig, "transient")
    for attempt in (1, 2):
        result = handler({"Records": [record]}, None)
        assert result == {"batchItemFailures": [{"itemIdentifier": "message-1"}]}
        item = rig.client.get(f"/api/jobs/{job_id}").json()
        assert item["status"] == "queued"
        assert item["attempts"] == attempt
    assert handler({"Records": [record]}, None) == {"batchItemFailures": []}
    assert rig.client.get(f"/api/jobs/{job_id}").json()["status"] == "published"
    assert rig.client.get(f"/api/jobs/{job_id}").json()["attempts"] == 3


def test_permanent_failure_becomes_terminal_and_dlq_eligible(rig):
    job_id, record = enqueue(rig, "permanent")
    for i in range(4):
        assert handler({"Records": [record]}, None)["batchItemFailures"] == [
            {"itemIdentifier": "message-1"}
        ]
        current = rig.client.get(f"/api/jobs/{job_id}").json()
        assert current["attempts"] == i + 1
    assert current["status"] == "failed"
    assert "rejected" in current["last_error"]
    # SQS maxReceiveCount=4 moves the rejected message to the real DLQ.
    assert handler({"Records": [record]}, None) == {"batchItemFailures": []}


def test_batch_partial_failure_acknowledges_only_good_messages(rig):
    _, good = enqueue(rig, "none", "good")
    _, bad = enqueue(rig, "permanent", "bad")
    good["messageId"] = "good-id"
    bad["messageId"] = "bad-id"
    assert handler({"Records": [good, bad]}, None) == {
        "batchItemFailures": [{"itemIdentifier": "bad-id"}]
    }


def test_missing_job_is_poison_message(rig):
    record = {"messageId": "poison", "body": json.dumps({"job_id": "f" * 24})}
    assert handler({"Records": [record]}, None) == {
        "batchItemFailures": [{"itemIdentifier": "poison"}]
    }
