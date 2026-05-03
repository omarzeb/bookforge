# BookForge

> AI-powered multi-user book generation platform — BYOK (Bring Your Own Key).

[![Backend CI](https://github.com/YOUR_USERNAME/book-forge/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/book-forge/actions/workflows/backend-ci.yml)
[![Frontend CI](https://github.com/YOUR_USERNAME/book-forge/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/book-forge/actions/workflows/frontend-ci.yml)

<!-- TODO: Add demo GIF here -->

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI on AWS App Runner |
| Workers | AWS Fargate (on-demand tasks) |
| Database | Neon (serverless Postgres) |
| Cache / Queue | Upstash (serverless Redis) |
| Storage | S3 |
| Frontend | Next.js on Vercel |
| IaC | Terraform |

**Target cost: ~$20/month.** See [docs/cost-analysis.md](docs/cost-analysis.md).

## Quick start (local)

```bash
cp backend/.env.example backend/.env   # fill in your keys
make dev                               # starts api + worker + postgres + redis
```

## Documentation

- [Architecture](docs/architecture.md)
- [State machine](docs/state-machine.md)
- [API reference](docs/api.md)
- [Local deployment](docs/deployment-local.md)
- [AWS deployment](docs/deployment-aws.md)
- [Cost analysis](docs/cost-analysis.md)

## Development

```bash
make test        # run backend tests
make migrate     # run alembic migrations
make deploy-api  # build + push API image, trigger App Runner update
```
