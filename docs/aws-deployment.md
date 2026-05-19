# AWS Deployment Guide

Deploys BookForge to AWS using App Runner (API) + Fargate (worker).
Estimated cost: $15-25/month at portfolio scale.

## Prerequisites

1. **AWS account** — [aws.amazon.com](https://aws.amazon.com) (free tier for 12 months)
2. **Terraform** — `winget install Hashicorp.Terraform` or [terraform.io](https://terraform.io)
3. **AWS CLI** — `winget install Amazon.AWSCLI`
4. **Neon** — free Postgres at [neon.tech](https://neon.tech) (0 cost, serverless)
5. **Upstash** — free Redis at [upstash.com](https://upstash.com) (0 cost, serverless)

## Step 1 — AWS credentials

```bash
aws configure
# Enter: Access Key ID, Secret Access Key, region (us-east-1), output (json)
```

Get your access key from AWS Console → IAM → Users → your user → Security credentials.

## Step 2 — External services (free)

**Neon (PostgreSQL):**
1. Sign up at neon.tech
2. Create a project → copy the connection string
3. Change `postgresql://` to `postgresql+asyncpg://` in the URL
4. Add `?sslmode=require` at the end

**Upstash (Redis):**
1. Sign up at upstash.com
2. Create a Redis database → copy the REST URL
3. Use the `rediss://` connection string

## Step 3 — Configure Terraform

```bash
cd deploy/aws/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your real values:
- Paste your Neon connection string
- Paste your Upstash Redis URL
- Generate keys (commands are in the file)
- Set your email for budget alerts

## Step 4 — Initialize and apply

```bash
terraform init
terraform plan    # review what will be created
terraform apply   # type 'yes' when prompted
```

Takes about 5-10 minutes. When done, you'll see:

```
Outputs:
app_runner_url = "https://abc123.us-east-1.awsapprunner.com"
api_ecr_repo   = "123456789.dkr.ecr.us-east-1.amazonaws.com/bookforge-api"
worker_ecr_repo = "123456789.dkr.ecr.us-east-1.amazonaws.com/bookforge-worker"
```

## Step 5 — Build and push Docker images

```bash
# Login to ECR (replace with your account ID and region)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and push API
docker build -t bookforge-api backend/
docker tag bookforge-api YOUR_ECR_API_REPO:latest
docker push YOUR_ECR_API_REPO:latest

# Build and push worker
docker build -t bookforge-worker -f backend/Dockerfile.worker backend/
docker tag bookforge-worker YOUR_ECR_WORKER_REPO:latest
docker push YOUR_ECR_WORKER_REPO:latest
```

## Step 6 — Run migrations

```bash
# Get a shell into the running App Runner service
# (easiest via the AWS Console → App Runner → your service → Logs)
# Or run migrations via a one-off Fargate task:

aws ecs run-task \
  --cluster bookforge \
  --task-definition bookforge-worker \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[YOUR_SUBNET],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides":[{"name":"bookforge-worker","command":["python","-m","alembic","upgrade","head"]}]}'
```

## Step 7 — Verify

Visit `https://YOUR_APP_RUNNER_URL/health` — should return `{"status": "ok"}`
Visit `https://YOUR_APP_RUNNER_URL/ready` — should return all checks passing

## Cost breakdown

| Service | Monthly cost |
|---|---|
| App Runner (1 vCPU, 2GB, ~10% utilisation) | ~$5-8 |
| Fargate tasks (on-demand, 30s each) | ~$1-2 |
| Neon PostgreSQL | $0 (free tier) |
| Upstash Redis | $0 (free tier) |
| S3 storage | ~$0.01 |
| Secrets Manager | ~$0.40 |
| CloudWatch logs | ~$0.50 |
| ECR storage | ~$0.10 |
| **Total** | **~$8-12/month** |

## Tear down

```bash
terraform destroy   # removes everything, bill goes back to ~$0
```

## CI/CD Setup (GitHub Actions)

Add these secrets to your GitHub repo (Settings → Secrets):
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `FERNET_KEY`

Push to `main` → tests run → Docker images build → App Runner updates automatically.
