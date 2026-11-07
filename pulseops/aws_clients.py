"""AWS client factory. Optional endpoint override is for local Moto ONLY."""
from functools import lru_cache

import boto3

from pulseops.settings import settings


@lru_cache
def dynamodb_table():
    resource = boto3.resource(
        "dynamodb", region_name=settings.aws_region, endpoint_url=settings.endpoint_url
    )
    return resource.Table(settings.table_name)


@lru_cache
def sqs_client():
    return boto3.client(
        "sqs", region_name=settings.aws_region, endpoint_url=settings.endpoint_url
    )


@lru_cache
def queue_url() -> str:
    if settings.queue_url:
        return settings.queue_url
    return sqs_client().get_queue_url(QueueName=settings.queue_name)["QueueUrl"]
