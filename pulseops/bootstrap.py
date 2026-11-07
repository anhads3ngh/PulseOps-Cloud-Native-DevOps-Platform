"""Provision AWS-emulated resources in Moto for zero-cloud local demos."""
import json
import time

import boto3

from pulseops.settings import settings
from pulseops.telemetry import log_event


def main():
    kwargs = {"region_name": settings.aws_region, "endpoint_url": settings.endpoint_url}
    sqs = boto3.client("sqs", **kwargs)
    dynamo = boto3.client("dynamodb", **kwargs)
    for attempt in range(40):
        try:
            sqs.list_queues()
            break
        except Exception:
            if attempt == 39:
                raise
            time.sleep(1)

    tables = dynamo.list_tables()["TableNames"]
    if settings.table_name not in tables:
        dynamo.create_table(
            TableName=settings.table_name,
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
    dlq_name = f"{settings.queue_name}-dlq"
    dead = sqs.create_queue(QueueName=dlq_name)
    dead_arn = sqs.get_queue_attributes(
        QueueUrl=dead["QueueUrl"], AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    sqs.create_queue(
        QueueName=settings.queue_name,
        Attributes={
            "VisibilityTimeout": "6",
            "RedrivePolicy": json.dumps({"deadLetterTargetArn": dead_arn, "maxReceiveCount": 4}),
        },
    )
    log_event("bootstrap_complete", table=settings.table_name, queue=settings.queue_name)


if __name__ == "__main__":
    main()
