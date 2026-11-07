"""Local equivalent of Lambda's SQS polling and partial-batch handling."""
import signal
import time

from pulseops.aws_clients import queue_url, sqs_client
from pulseops.telemetry import log_event
from pulseops.worker import handler

running = True


def stop(_signum, _frame):
    global running
    running = False


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    sqs = sqs_client()
    url = queue_url()
    log_event("worker_started")
    while running:
        try:
            response = sqs.receive_message(
                QueueUrl=url, WaitTimeSeconds=2,
                MaxNumberOfMessages=5, AttributeNames=["ApproximateReceiveCount"],
            )
            messages = response.get("Messages", [])
            if not messages:
                continue
            records = [{"body": m["Body"], "messageId": m["MessageId"]} for m in messages]
            failures = handler({"Records": records}, None)["batchItemFailures"]
            failed = {entry["itemIdentifier"] for entry in failures}
            for message in messages:
                if message["MessageId"] not in failed:
                    sqs.delete_message(QueueUrl=url, ReceiptHandle=message["ReceiptHandle"])
        except Exception as error:
            log_event("poll_error", error_type=type(error).__name__)
            time.sleep(2)


if __name__ == "__main__":
    main()
