# PulseOps security guidance

This repository is **an educational simulation, not a production service**.

- Use fake post content only. GET endpoints do not have tenant authentication.
- Protect the deployment with a long random `DEMO_API_KEY` and keep it out of source control.
- `terraform.tfstate` contains sensitive environment variables: encrypt and restrict it; never commit it.
- GitHub AWS role assumption is restricted to an exact `owner/repository:main` subject.
- Limit who can push to `main` and require CI checks and approvals before deploying.
- API and worker IAM roles have distinct, least-necessary data permissions.
- Manage cloud charges by destroying unused demo resources.
- Report security issues privately rather than publishing credentials or real data in GitHub issues.
