<div align="center">

# 📚 BookForge

**AI-powered book generation — bring your own key, keep your words.**

[![Tests](https://github.com/YOUR_USERNAME/book-forge/actions/workflows/backend-deploy.yml/badge.svg)](https://github.com/YOUR_USERNAME/book-forge/actions)
[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Terraform](https://img.shields.io/badge/Terraform-AWS-7B42BC?logo=terraform)](deploy/aws/terraform)

[Live Demo](https://YOUR_APP_RUNNER_URL) · [Architecture](#architecture) · [Deployment](#deployment) · [API Docs](https://YOUR_APP_RUNNER_URL/docs)

</div>

---

## What it does

BookForge generates full-length books chapter by chapter using any AI model available on [OpenRouter](https://openrouter.ai). You review and revise at every stage — outline, each chapter, and the final compiled book.

**Bring your own key.** Your OpenRouter API key is AES-256 encrypted before storage. You pay OpenRouter directly — no platform markup. A complete 10-chapter book typically costs $0.02–$0.30 depending on the model.

---

## Architecture

```
Browser
  │
  ▼
Caddy (reverse proxy, TLS)
  │
  ├── /api/* ──► FastAPI (App Runner)
  │                │
  │                ├── PostgreSQL (Neon serverless)
  │                ├── Redis (Upstash serverless)
  │                ├── S3 (compiled books)
  │                └── boto3.run_task() ──► Fargate (one-shot worker)
  │                                              │
  │                                              └── OpenRouter API
  │
  └── /* ──────► Next.js 14 (App Router)
```

**Key design decisions:**

- **One-shot Fargate tasks** instead of a long-running worker daemon — $0 cost when idle, isolated crashes, free horizontal scaling
- **BYOK (bring your own key)** — Fernet-encrypted OpenRouter key stored per user, never logged
- **Correlation IDs** — every API request gets an `X-Correlation-ID` that flows through logs and SSE streams for instant debugging
- **Stage machine** — books move through `INPUT_RECEIVED → OUTLINE_REVIEW → CHAPTERS_GENERATING → CHAPTER_REVIEW → COMPLETE` with human review at every transition

---

## Tech stack

| Layer | Technology |
|---|---|
| **API** | FastAPI 0.111, Python 3.11, SQLAlchemy (async), Alembic |
| **Frontend** | Next.js 14 (App Router), TypeScript, Tailwind CSS, SWR |
| **Database** | PostgreSQL 16 (Neon serverless on AWS, local Docker) |
| **Cache / Queue** | Redis 7 (Upstash on AWS, local Docker) + RQ |
| **Workers** | AWS Fargate one-shot tasks (local: RQ workers) |
| **Storage** | AWS S3 (compiled books), local volume (dev) |
| **Auth** | JWT + bcrypt (SHA-256 pre-hash for passwords >72 bytes) |
| **AI** | OpenRouter — 100+ models: Claude, GPT-4o, Gemini, DeepSeek |
| **Observability** | structlog JSON logs, Sentry, correlation IDs, CloudWatch |
| **IaC** | Terraform — ECR, App Runner, Fargate, S3, Secrets Manager, Budgets |
| **CI/CD** | GitHub Actions — test → build → ECR push → App Runner deploy |

---

## Running locally

**Prerequisites:** Docker Desktop, Python 3.11+, Node.js 20+

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/book-forge
cd book-forge

# Configure
cp backend/.env.example backend/.env
# Edit backend/.env — minimum required: APP_SECRET_KEY, FERNET_KEY, JWT_SECRET

# Start everything
docker compose -f deploy/local/docker-compose.yml up -d --build

# Run migrations and seed demo data
docker compose -f deploy/local/docker-compose.yml exec api alembic upgrade head
docker compose -f deploy/local/docker-compose.yml exec api python scripts/seed_dev.py
```

Visit **http://localhost** — login with `demo@bookforge.app` / `demo1234`

---

## Project structure

```
book-forge/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # FastAPI routers (auth, books, chapters, jobs, prompts…)
│   │   ├── core/            # Auth, logging, correlation ID middleware
│   │   ├── db/              # SQLAlchemy models, Alembic migrations
│   │   ├── providers/       # LLM provider abstraction (OpenRouter)
│   │   ├── prompts/         # Prompt families per model (claude/, gpt/, gemini/, deepseek/)
│   │   ├── services/        # Business logic (orchestrator, book, chapter, usage…)
│   │   └── workers/         # RQ tasks + Fargate one-shot runner
│   └── tests/               # 103 passing tests across 8 phases
├── frontend/
│   ├── app/                 # Next.js App Router pages
│   ├── components/          # ModelDropdown, JobProgress, PromptEditor, CostEstimate…
│   ├── hooks/               # useJobStream (SSE + polling fallback)
│   └── lib/                 # API client, auth helpers, types
├── deploy/
│   ├── local/               # Docker Compose, Caddyfile, backup scripts, systemd
│   └── aws/terraform/       # Full IaC — ECR, App Runner, Fargate, S3, budgets
└── docs/                    # Deployment guides, observability, Cloudflare tunnel
```

---

## Deployment

### Self-hosted (any machine with Docker)

```bash
docker compose -f deploy/local/docker-compose.yml up -d --build
```

Add a free public URL via Cloudflare Tunnel:
```bash
cloudflared tunnel --url http://localhost:80
```
See [docs/cloudflare-tunnel.md](docs/cloudflare-tunnel.md) for the full guide.

### AWS (App Runner + Fargate)

```bash
cd deploy/aws/terraform
cp terraform.tfvars.example terraform.tfvars
# Fill in Neon + Upstash connection strings and generated secrets
terraform init && terraform apply
```

Estimated cost: **$8–12/month** (App Runner + Fargate on-demand + free Neon/Upstash).

Full guide: [docs/aws-deployment.md](docs/aws-deployment.md)

---

## API

Interactive docs at `/docs` (disabled in production).

Key endpoints:

```
POST /api/v1/auth/register
POST /api/v1/auth/login

POST /api/v1/books                    # create book
POST /api/v1/books/{id}/advance       # generate outline / next chapter / compile
POST /api/v1/books/{id}/outline/approve
POST /api/v1/books/{id}/outline/revise

GET  /api/v1/books/{id}/chapters
POST /api/v1/books/{id}/chapters/{n}/approve
POST /api/v1/books/{id}/chapters/{n}/revise

GET  /api/v1/jobs/{id}                # job status
GET  /api/v1/jobs/{id}/stream         # SSE stream

GET  /api/v1/models/curated           # 8 curated models with pricing
GET  /api/v1/models/estimate          # cost estimate for a book
GET  /api/v1/usage                    # per-user spend summary

GET  /health                          # liveness
GET  /ready                           # readiness (DB + Redis + OpenRouter)
```

---

## Test suite

```bash
docker compose -f deploy/local/docker-compose.yml exec api pytest tests/ -v
```

103 passing, 3 skipped (OpenRouter contract tests — require real API key)

| Phase | Coverage |
|---|---|
| Providers + OpenRouter | Contract tests, fake provider, key validation |
| Domain + orchestrator | State machine, parser, all transitions |
| HTTP API | Auth, books CRUD, chapter lifecycle |
| Background jobs + SSE | Queue, job status, streaming |
| Fargate launcher | ECS mock, RQ fallback, reconciliation |
| Prompt families | GPT, Gemini, DeepSeek, Claude, resolver |
| Cost + usage | Estimation, per-user logging, endpoint |
| Observability | Correlation IDs, health checks, usage logging |

---

## Cost breakdown

| Service | Monthly (portfolio scale) |
|---|---|
| App Runner (1 vCPU, 2GB, ~5% utilisation) | ~$5–8 |
| Fargate tasks (on-demand, ~30s each) | ~$1–2 |
| Neon PostgreSQL | **$0** (free tier) |
| Upstash Redis | **$0** (free tier) |
| S3 + ECR | ~$0.10 |
| Secrets Manager | ~$0.40 |
| CloudWatch logs (7-day retention) | ~$0.50 |
| **Total** | **~$8–12/month** |

AWS Budget alert set at $25/month — you'll get an email before anything surprising happens.

---

## License

MIT — do whatever you want with it.
