"""FastAPI HTTP API and a responsive, static operations dashboard."""
import hmac
import json
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pulseops.aws_clients import queue_url, sqs_client
from pulseops.models import Job, NewJob
from pulseops.settings import settings
from pulseops import store
from pulseops.telemetry import log_event, metric

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(
    title="PulseOps Delivery API",
    description="A simulated social-publishing reliability sandbox; never sends real posts.",
    version="1.0.0",
    docs_url="/docs",
)
app.mount("/assets", StaticFiles(directory=ROOT / "web" / "assets"), name="assets")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    return response


def check_key(x_demo_key: str | None = Header(default=None)) -> None:
    # When a key is configured, writes require it. Use only synthetic demo data.
    if settings.demo_api_key and not hmac.compare_digest(x_demo_key or "", settings.demo_api_key):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Demo-Key")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/healthz", tags=["operations"])
def healthz():
    # Liveness only; readiness would check dependencies separately.
    return {"status": "ok", "service": "pulseops-api"}


@app.post("/api/jobs", response_model=Job, status_code=202, tags=["jobs"])
def submit_job(
    request: NewJob,
    response: Response,
    _: None = Depends(check_key),
    idempotency_key: str | None = Header(default=None, max_length=128),
):
    try:
        job, created = store.create_or_get_job(request, idempotency_key)
    except store.IdempotencyConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    # If enqueue fails, retry POST with the SAME idempotency key; a queued
    # duplicate is safe because DynamoDB lease claims are conditional.
    if job["status"] == "queued":
        try:
            sqs_client().send_message(
                QueueUrl=queue_url(), MessageBody=json.dumps({"job_id": job["id"]})
            )
        except Exception as error:
            log_event("enqueue_failed", job_id=job["id"], error_type=type(error).__name__)
            raise HTTPException(
                status_code=503,
                detail="Queue unavailable; retry using the same Idempotency-Key",
            ) from error
        metric("JobQueued")
    if not created:
        response.headers["X-Idempotent-Replay"] = "true"
    log_event("job_submitted", job_id=job["id"], created=created)
    return job


@app.get("/api/jobs", tags=["jobs"])
def recent_jobs():
    return {"items": store.list_jobs()}


@app.get("/api/jobs/{job_id}", response_model=Job, tags=["jobs"])
def fetch_job(job_id: str):
    if len(job_id) != 24 or any(ch not in "0123456789abcdef" for ch in job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/stats", tags=["operations"])
def stats():
    jobs = store.list_jobs(200)
    counts = {name: sum(job["status"] == name for job in jobs)
              for name in ("queued", "processing", "published", "failed")}
    finished = counts["published"] + counts["failed"]
    return {
        "total": len(jobs), **counts,
        "success_rate": round(100 * counts["published"] / finished, 1) if finished else 100,
        "total_attempts": sum(job["attempts"] for job in jobs),
        "retry_attempts": sum(max(0, job["attempts"] - 1) for job in jobs),
        "scope": "last_200_jobs_from_single_demo_scan",
    }
