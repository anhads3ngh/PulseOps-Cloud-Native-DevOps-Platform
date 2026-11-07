"""Structured logs and CloudWatch Embedded Metric Format (EMF)."""
import json
from datetime import datetime, timezone


def log_event(event: str, **fields: object) -> None:
    # Never log a post's content or X-Demo-Key; demo data may still be personal.
    print(json.dumps({"event": event, **fields}, separators=(",", ":")), flush=True)


def metric(name: str, value: float = 1, unit: str = "Count") -> None:
    # Lambda sends stdout to CloudWatch; EMF turns this line into a custom metric.
    payload = {
        "_aws": {
            "Timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": "PulseOps/Delivery",
                    "Dimensions": [[]],
                    "Metrics": [{"Name": name, "Unit": unit}],
                }
            ],
        },
        name: value,
    }
    print(json.dumps(payload, separators=(",", ":")), flush=True)
