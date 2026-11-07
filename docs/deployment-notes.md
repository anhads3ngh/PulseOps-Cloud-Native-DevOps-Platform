# Deployment and operational notes

## AWS prerequisites

Use your own AWS account and appropriate credentials. Choose a nonproduction AWS account if possible. Set billing alerts and review pricing before deployment. Default region is ca-central-1; align every CLI command, Terraform variable, and CD workflow if changing it.

Terraform provider version is `~> 6.0`. Image URI must exist before the first `terraform apply`; run `scripts/bootstrap_aws.sh`. Terraform references ECR as a **data source** because ECR is intentionally bootstrapped outside this state. The initial image has an API Lambda handler and a worker Lambda handler supplied via function-specific `image_config.command`.

### Existing GitHub OIDC provider

AWS permits only one OIDC provider with URL `https://token.actions.githubusercontent.com` per account. If you already use GitHub Actions in that account, import the provider into Terraform state instead of creating a duplicate. Its account ID is returned by `aws sts get-caller-identity`.

```bash
cd infra
terraform import \
  -var="image_uri=YOUR_ECR_BOOTSTRAP_URI" \
  -var="github_repository=YOUR_USERNAME/pulseops" \
  aws_iam_openid_connect_provider.github \
  arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com
```

Terraform may prompt for the demo API key. **Caution:** If the OIDC provider is shared across unrelated workflows, importing it into this demo stack means `terraform destroy` would try to remove the shared resource. In shared accounts, refactor the provider to a `data` source or use a dedicated account. Do not destroy a shared provider.

### Secrets

The demo API key is stored in the Lambda configuration and **in Terraform state**. Do not use a real account password. Use only a long random demo key. Never commit `.tfstate` or `terraform.tfvars`. A future production version should manage infrastructure state remotely with encryption and use a dedicated secret provider.

### Function readiness

The CD workflow uses GitHub Actions OIDC, pushes an immutable SHA-tagged image to ECR, updates the API Lambda first, waits until its update completes, then updates the worker. This is **not an atomic two-service release**: during a deployment they can briefly run different revisions. The contract should remain backward compatible or you should use weighted Lambda aliases/canaries and a coordinated rollout.

### Verify after deployment

- Open `terraform output -raw dashboard_url` and verify `/healthz` and `/docs`.
- Queue a `none` job and confirm published status.
- Queue a `transient` job and wait for retry. The cloud visibility timeout is 180s; retry is not immediate.
- Queue a `permanent` job and examine both DynamoDB status and the DLQ after the retry budget is exhausted.
- Open `terraform output -raw cloudwatch_dashboard` in your browser. CloudWatch metrics may take some time to appear.
- Inspect AWS costs and disable/destroy the stack when you're done.

### Troubleshooting

- `ResourceConflictException` on the OIDC provider: import existing or refactor to a data source.
- Lambda cannot pull image: check that ECR URI is in the same AWS region/account and that the image manifest is Lambda compatible (`--platform linux/amd64 --provenance=false`).
- API returns 401: you must supply the X-Demo-Key chosen during `terraform apply`.
- Jobs stuck queued: inspect API Lambda logs, SQS queue size, and worker IAM / event source mapping; retry a request with the same `Idempotency-Key` if send failed.
- Lambda retries appear slow: AWS queue visibility timeout is 180s by design.
- No metrics yet: produce several jobs and give CloudWatch time to aggregate.
- Costs: run `terraform destroy`; separately delete the bootstrapped ECR repository after confirming no other systems use it.
