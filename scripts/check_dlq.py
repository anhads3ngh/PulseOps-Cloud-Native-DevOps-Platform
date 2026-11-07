"""Inspect dead-letter queue depth using the configured Moto or AWS endpoint.

Local usage (in a Docker Compose container):
    python scripts/check_dlq.py
Cloud usage: set AWS_REGION and use valid AWS credentials.
"""
import os
import boto3

region = os.getenv("AWS_REGION", "ca-central-1")
client = boto3.client("sqs", region_name=region, endpoint_url=os.getenv("AWS_ENDPOINT_URL"))
queue_name = f"{os.getenv('SQS_QUEUE_NAME', 'pulseops-jobs')}-dlq"
url = client.get_queue_url(QueueName=queue_name)["QueueUrl"]
response = client.get_queue_attributes(
    QueueUrl=url,
    AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
)
print("DLQ:", queue_name)
print("Visible messages:", response["Attributes"].get("ApproximateNumberOfMessages", "0"))
print("In-flight messages:", response["Attributes"].get("ApproximateNumberOfMessagesNotVisible", "0"))
