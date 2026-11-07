# Engineering decisions and failure-mode analysis

## Delivery semantics

SQS standard queues deliver **at least once**, possibly out of order. A client supplies `Idempotency-Key`, creating a deterministic job ID via SHA-256. DynamoDB `PutItem` uses `attribute_not_exists(pk)` so a repeat request cannot insert a duplicate job. Reusing the key with a different request fingerprint yields 409.

Workers first read the job; terminal states are acknowledged without additional work. For runnable jobs, an `UpdateItem` changes state to `processing`, increments `attempts`, and writes a random `lease_token` with a 90-second expiration. The conditional expression allows acquisition only from `queued` or an expired `processing` lease. Every completion update checks its own token to prevent a delayed worker from overwriting a newer worker's result.

**Important edge:** This is not full exactly-once delivery. A worker can call a real external API and crash before committing its local state, causing another request to the external provider. The sample merely simulates successful delivery and is safe from external duplicate side effects. A real adapter needs provider idempotency keys and recovery logic.

## Enqueue failure and transactional outbox

`POST /api/jobs` first inserts the DynamoDB record and then sends the SQS message. If SQS fails, the API returns 503 and encourages the client to retry using the **same** key; an existing `queued` job will be enqueued again. This design is intentionally transparent about the non-atomic gap: without client retry or a reconciler, a job can remain queued indefinitely. The production improvement is a DynamoDB transactional outbox, DynamoDB Streams + relay, or another atomic messaging design.

## Error budgets and dead-letter handling

The worker accepts three modes:

- `none`: succeeds on the first claim.
- `transient`: fails attempts 1 and 2, then succeeds on attempt 3.
- `permanent`: rejects all four attempts. On the fourth it sets state `failed` and **still returns a batch item failure**. SQS redrive then moves the message to the configured DLQ after its receive budget is exhausted.

The worker returns `{"batchItemFailures":[...]}` so a successful item in a failed batch is removed while only failed items are retried. Retries follow SQS visibility timeout (6s local, 180s cloud). The `maxReceiveCount` value matches `MAX_ATTEMPTS=4` by configuration; if those values diverge, state and DLQ behavior could diverge too.

A permanently failing job reaches `failed` in DynamoDB before SQS eventually reflects it in the DLQ. The delay is normal. The dashboard reads DynamoDB status; the DLQ appears in CloudWatch, not directly in the UI.

A lease is 90s and Lambda timeout is 30s; SQS visibility timeout is 180s (AWS). These deliberately ensure the running Lambda typically completes well before a message reappears. The bounded local emulator uses 6s visibility but quick simulated processing.

## Observability

Structured JSON events avoid message content and secrets, while CloudWatch Embedded Metric Format publishes `JobQueued`, `JobPublished`, `JobRetried`, `JobFailed`, and `ProcessingLatencyMs`. CloudWatch dashboard includes queue depth, DLQ depth, worker duration/errors, and the custom metrics. The DLQ CloudWatch alarm becomes ALARM when its visible messages exceed zero; notifications are not configured.

The UI `GET /api/stats` stats are computed from a simple capped DynamoDB scan, and are **not** a production-grade analytics source. For a production scale system, use a time-keyed GSI and streaming/metric aggregation rather than a global scan.

## Security posture

Writes require an `X-Demo-Key` when configured. This is intentionally basic and is not suitable for a public multi-tenant service. Reads are open and reveal synthetic message content, so NEVER submit real customer data. IAM grants each Lambda only the DynamoDB/SQS operations it needs. GitHub OIDC is scoped to the exact repository and `main` branch; the role can push to one ECR repository and update code for two named Lambdas.

**Not included:** tenant auth, authorization, enterprise incident paging, SQS FIFO/exactly-once semantics, real provider API integrations, rate quotas per tenant, WAF, distributed traces, secret rotation, stream-based reconciliation, deployment canaries/rollback, long-term persisted analytics, and autoscaling benchmarks. Those are potential follow-up milestones, not features to claim in interviews.
