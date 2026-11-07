import json


def payload(mode="none"):
    return {"channel": "linkedin", "content": "Ship reliable systems, not hopes.", "failure_mode": mode}


def test_readiness_and_docs(rig):
    response = rig.client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert rig.client.get("/docs").status_code == 200
    assert rig.client.get("/").status_code == 200


def test_write_protected_and_body_validated(rig):
    assert rig.client.post("/api/jobs", json=payload()).status_code == 401
    headers = {"X-Demo-Key": "test-secret"}
    assert rig.client.post("/api/jobs", json={**payload(), "content": ""}, headers=headers).status_code == 422
    assert rig.client.post("/api/jobs", json={**payload(), "channel": "tiktok"}, headers=headers).status_code == 422
    assert rig.client.get("/api/jobs/invalid").status_code == 404


def test_create_read_list_and_stats(rig):
    response = rig.client.post("/api/jobs", json=payload(), headers={"X-Demo-Key": "test-secret"})
    assert response.status_code == 202
    job = response.json()
    assert job["status"] == "queued"
    assert job["attempts"] == 0
    assert len(job["id"]) == 24
    assert json.loads(rig.sqs.messages[0]) == {"job_id": job["id"]}
    assert rig.client.get(f"/api/jobs/{job['id']}").json()["id"] == job["id"]
    assert rig.client.get("/api/jobs").json()["items"][0]["status"] == "queued"
    assert rig.client.get("/api/stats").json()["total"] == 1
    assert rig.client.get("/api/stats").json()["queued"] == 1


def test_idempotent_replay_and_conflicting_payload(rig):
    headers = {"X-Demo-Key": "test-secret", "Idempotency-Key": "operation-123"}
    first = rig.client.post("/api/jobs", json=payload(), headers=headers)
    second = rig.client.post("/api/jobs", json=payload(), headers=headers)
    assert first.json()["id"] == second.json()["id"]
    assert second.headers["x-idempotent-replay"] == "true"
    assert rig.client.get("/api/stats").json()["total"] == 1
    assert rig.client.post("/api/jobs", json={**payload(), "content": "Different"}, headers=headers).status_code == 409


def test_enqueue_failure_safe_to_retry_with_same_key(rig):
    headers = {"X-Demo-Key": "test-secret", "Idempotency-Key": "safe-retry"}
    rig.sqs.fail = True
    response = rig.client.post("/api/jobs", json=payload(), headers=headers)
    assert response.status_code == 503
    assert len(rig.table.items) == 1
    rig.sqs.fail = False
    replay = rig.client.post("/api/jobs", json=payload(), headers=headers)
    assert replay.status_code == 202
    assert len(rig.sqs.messages) == 1
