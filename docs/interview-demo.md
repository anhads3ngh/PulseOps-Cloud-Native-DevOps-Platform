# PulseOps — technical interview demonstration

## A 45-second opening pitch

"I built PulseOps to explore the operational problems behind delivering social-media jobs reliably. The API is built with Python and FastAPI, requests are queued through Amazon SQS, and a Lambda worker persists job state in DynamoDB. I designed idempotent submissions, conditional worker leases, partial-batch SQS retries, dead-letter handling, and structured CloudWatch metrics. I use Terraform for infrastructure and GitHub Actions with OIDC for deployment. I added failure injection so I could demonstrate how the system behaves during outages instead of just showing the happy path."

**Say only what you have actually run and verified.** If you have tested locally but not deployed AWS, distinguish those facts instead of claiming a production deployment.

## Demo flow

1. Show dashboard and high-level architecture.
2. Send a normal job and watch status change queued → processing → published.
3. Send `transient`. Explain first two attempts fail and the third succeeds. Demonstrate the attempt counter.
4. Send `permanent`. Explain how a terminal state in DynamoDB is distinct from when SQS redrives the message into the DLQ.
5. Resend the same `Idempotency-Key` with the same content. Show the same job ID; then send different content with the same key to demonstrate HTTP 409.
6. Open Terraform and explain separate IAM roles, encryption-at-rest, timeout choices, and API throttling.
7. Open GitHub Actions CI and CD: unit tests, Docker build, Trivy scan, Terraform validation, short-lived OIDC identity, SHA-tagged image.

## Hard interview questions

**Q: Does this guarantee exactly-once publishing?** No. SQS is at least once, and the lease keeps concurrent workers from taking the same job, but it doesn't create an atomic transaction with a real remote publishing provider. A real adapter would use that provider's idempotency key and compensating reconciliation.

**Q: What happens if DynamoDB succeeds but enqueueing to SQS fails?** The API returns 503. Retrying the same Idempotency-Key safely reuses the durable job and attempts enqueue again. Without retry, it may remain queued; a transactional outbox or stream relay would close this gap.

**Q: Why not directly call the social network from the API?** Asynchronous queues decouple user requests from external latency or outages. SQS buffers spikes, enables controlled concurrency and retry, and protects the API from downstream failure.

**Q: Why a DLQ?** A poison message should not retry forever. Failed messages are isolated for inspection and possible repair, with an alarm on visible DLQ depth.

**Q: Why serverless instead of Kubernetes?** For an intermittent portfolio workload, Lambda + SQS has less idle infrastructure and fewer moving parts. Kubernetes makes sense if workloads need persistent workers, richer scheduling or portability; it adds cluster operations and cost.

**Q: How do you make a rollout safe?** CI checks, immutable SHA image tags, least-privilege OIDC, and staging checks help. This demo updates API and worker sequentially, not atomically; I'd add canary aliases, rollback, and coordinated compatibility tests before production.

**Q: What would you change next?** Transactional outbox, production authentication and tenant isolation, paginated query model, provider-side idempotency, tracing and better SLOs, traffic replay benchmarks, alarms routed to an on-call channel.

## Resume-ready entry (only after implementing and verifying relevant claims)

**PulseOps — Cloud-Native Delivery Reliability Platform** | Python, FastAPI, AWS, Terraform, Docker, GitHub Actions

- Built an event-driven simulated publishing pipeline using Amazon SQS, AWS Lambda, and DynamoDB, including idempotent API requests and conditional worker leases.
- Implemented failure injection, SQS partial-batch retries, dead-letter handling, and CloudWatch operational metrics to demonstrate recovery and troubleshooting workflows.
- Automated unit testing, container security scanning, infrastructure validation, and immutable deployment through GitHub Actions with AWS OIDC-based authentication.

Do not claim the AWS deployment, real workload reliability, customer usage, or production outcomes until actually demonstrated.
