#!/usr/bin/env bash
# One-time ECR creation and initial Lambda image push, before Terraform apply.
set -euo pipefail
REGION="${AWS_REGION:-ca-central-1}"
REPO="pulseops-delivery"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
URI="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${REPO}"
if ! aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" >/dev/null 2>&1; then
  aws ecr create-repository --repository-name "$REPO" --image-scanning-configuration scanOnPush=true --region "$REGION" >/dev/null
fi
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
docker buildx build --platform linux/amd64 --provenance=false -f Dockerfile.lambda --load -t "${URI}:bootstrap" .
docker push "${URI}:bootstrap"
printf '\nImage pushed. Terraform image_uri:\n%s\n' "${URI}:bootstrap"
printf '\nNext: cd infra && terraform init && terraform apply -var="image_uri=%s" -var="github_repository=OWNER/REPO"\n' "${URI}:bootstrap"
