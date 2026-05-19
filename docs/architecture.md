# Architecture Deep Dive

## Overview

BookForge is built around three design principles:

1. **Human in the loop** — every AI generation requires explicit user approval before moving to the next stage
2. **Cost-safe by default** — one-shot Fargate tasks cost $0 when idle; AWS Budget caps at $25/month
3. **BYOK** — users bring their own OpenRouter key; BookForge never touches the credits

---

## Request lifecycle

### Book creation + outline generation

```
User → POST /api/v1/books
         │
         ├── Insert Book (status=INPUT_RECEIVED)
         └── 200 OK { book_id }

User → POST /api/v1/books/{id}/advance
         │
         ├── Create Job (status=QUEUED)
         ├── boto3.run_task() ──► Fargate container starts
         └── 200 OK { job_id, message: "Outline queued" }

                    Fargate container:
                    ├── Job → RUNNING
                    ├── resolve_outline() → prompt
                    ├── OpenRouter API → LLM response
                    ├── parse_outline() → chapters
                    ├── Book → OUTLINE_REVIEW
                    └── Job → DONE

User → GET /api/v1/jobs/{id}/stream (SSE)
         └── polls DB every 500ms → pushes status updates
```

### Chapter generation

Same pattern, repeated per chapter:
- User approves outline → `CHAPTER_REVIEW`
- User clicks "Write next chapter" → new Job + Fargate task
- Worker finds next unapproved chapter, generates content + summary
- User approves or requests revision
- All approved → `FINAL_REVIEW` → auto-compile

---

## Prompt resolver

```python
resolve_outline(model_id="openai/gpt-4o-mini", ...)
  → _family("openai/gpt-4o-mini") → "gpt"
  → import app.prompts.gpt.outline
  → mod.get(title, notes, chapter_count=10)
  → { system: "...", user: "..." }
```

Resolution order:
1. User override from `PromptOverride` table (per stage, per model family)
2. Model-family prompt (gpt/, gemini/, deepseek/, claude/)
3. defaults/ fallback

---

## Security model

| Concern | Approach |
|---|---|
| API key storage | Fernet (AES-128-CBC + HMAC-SHA256) encryption at rest |
| Password hashing | bcrypt with SHA-256 pre-hash (handles passwords >72 bytes) |
| Auth | JWT (HS256), 7-day expiry, no refresh tokens |
| Secrets in prod | AWS Secrets Manager — never in env vars or code |
| Internal endpoints | `X-Internal-Secret` header (EventBridge reconciliation) |
| User data isolation | All DB queries filter by `user_id` from JWT |

---

## Local vs production parity

| Feature | Local dev | Production |
|---|---|---|
| Database | PostgreSQL in Docker | Neon serverless |
| Redis | Redis in Docker | Upstash serverless |
| Worker | RQ in Docker | Fargate one-shot task |
| Storage | Local volume | AWS S3 |
| TLS | Plain HTTP via Caddy | App Runner managed TLS |
| Secrets | `.env` file | AWS Secrets Manager |

The abstraction is in `task_launcher.py`:
```python
if settings.is_production and _is_fargate_available():
    return await _launch_fargate(db, job, extra_env)
else:
    _launch_rq(job, extra_env)
```

Zero code changes between environments.
