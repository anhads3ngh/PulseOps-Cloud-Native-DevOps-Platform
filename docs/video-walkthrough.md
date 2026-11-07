# PulseOps video walkthrough

**[Watch the walkthrough (MP4)](pulseops-walkthrough.mp4)** · **Duration: ~59 seconds** · 1280 × 720 · on-screen captions / no voiceover

This is an **animated visual overview using synthetic sample data**, based on the project's real dashboard design and documented code architecture. It is *not* a capture of a functioning AWS deployment, and it does not demonstrate real social-media publishing. To record a real hosted demo, deploy the repository and capture the browser interactions and matching CloudWatch evidence yourself.

## Scene-by-scene transcript

| Approx. time | On-screen narration / explanation |
|---|---|
| 00:00–00:06 | **PulseOps — Ship confidently. Fail gracefully.** A social-delivery reliability sandbox built with Python, AWS, Terraform and CI/CD. |
| 00:06–00:13 | **One dashboard. Every event.** See simulated delivery volume, successful deliveries, retries and pipeline health. |
| 00:13–00:19 | **Follow a delivery request.** The FastAPI endpoint queues work in SQS; a Lambda worker processes the message and updates DynamoDB. Repeated failures can reach a dead-letter queue. |
| 00:19–00:26 | **Inject failure on purpose.** Choose healthy, transient-failure or permanent-failure modes in the Chaos Lab. |
| 00:26–00:33 | **Recovery is engineered.** A transient job succeeds on attempt three; the permanent example exhausts the retry budget and is eligible for DLQ redrive. |
| 00:33–00:39 | **Duplicates are not new jobs.** Reuse an Idempotency-Key for the same payload and get the same job identity; reuse it with a different payload and receive HTTP 409. |
| 00:39–00:46 | **Every change passes a pipeline.** GitHub Actions checks code, scans container images and can publish immutable images to Amazon ECR. |
| 00:46–00:52 | **Infrastructure you can review.** Terraform manages the AWS stack, CloudWatch collects signals, and OIDC avoids static GitHub AWS credentials. |
| 00:52–00:59 | **Clone. Run. Inject. Observe.** Start locally with `docker compose up --build`, open the dashboard and try a chaos demo. |

## Record a live walkthrough after deployment

1. Run `docker compose up --build` and make sure the dashboard is reachable on `http://localhost:8000`.
2. In the **Demo write key** field use `demo-local-key` (only for local Moto; do not reveal real deployment keys).
3. Submit one successful synthetic job. Then create transient and permanent failure jobs and observe the actual status / attempts.
4. Record the browser with an ordinary screen-recording tool. Include a short terminal clip of `docker compose logs -f worker` and a brief tour of `.github/workflows/`, `infra/`, and the test results.
5. If you deploy to AWS, demonstrate real CloudWatch metrics and a confirmed DLQ message separately; do not present the local Moto demo as a live AWS deployment.
6. Replace `docs/pulseops-walkthrough.mp4` with your screen recording (same filename) and keep the README's relative link unchanged. Do not publish passwords, tokens, account numbers or account IDs in footage.

The image preview in `docs/pulseops-preview.gif` is a short animated overview, not an interactive GIF or a simulated real-time cloud trace.
