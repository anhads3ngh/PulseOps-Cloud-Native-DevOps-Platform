"""Small environment-based configuration shared by API and workers."""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    aws_region: str = os.getenv("AWS_REGION", "ca-central-1")
    endpoint_url: str | None = os.getenv("AWS_ENDPOINT_URL") or None
    table_name: str = os.getenv("DYNAMO_TABLE", "pulseops-jobs")
    queue_name: str = os.getenv("SQS_QUEUE_NAME", "pulseops-jobs")
    queue_url: str | None = os.getenv("SQS_QUEUE_URL") or None
    demo_api_key: str | None = os.getenv("DEMO_API_KEY") or None
    max_attempts: int = int(os.getenv("MAX_ATTEMPTS", "4"))


settings = Settings()
