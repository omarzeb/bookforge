.PHONY: dev test migrate lint deploy-api deploy-worker destroy-aws help

# ── Local development ─────────────────────────────────────────────────────────
dev:
	docker compose -f deploy/local/docker-compose.yml \
	               -f deploy/local/docker-compose.override.yml up --build

dev-down:
	docker compose -f deploy/local/docker-compose.yml down

# ── Testing & linting ─────────────────────────────────────────────────────────
test:
	cd backend && python -m pytest tests/ -v

lint:
	cd backend && ruff check app/ && mypy app/

# ── Database migrations ───────────────────────────────────────────────────────
migrate:
	cd backend && alembic upgrade head

migrate-new:
	cd backend && alembic revision --autogenerate -m "$(msg)"

# ── AWS deployment ────────────────────────────────────────────────────────────
deploy-api:
	bash deploy/aws/scripts/deploy-api.sh

deploy-worker:
	bash deploy/aws/scripts/deploy-worker.sh

# ── Terraform ─────────────────────────────────────────────────────────────────
tf-init:
	cd deploy/aws/terraform && terraform init

tf-plan:
	cd deploy/aws/terraform && terraform plan -var-file=environments/prod.tfvars

tf-apply:
	cd deploy/aws/terraform && terraform apply -var-file=environments/prod.tfvars

destroy-aws:
	cd deploy/aws/terraform && terraform destroy -var-file=environments/prod.tfvars

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  make dev           Start full local stack (docker compose)"
	@echo "  make test          Run pytest"
	@echo "  make lint          Run ruff + mypy"
	@echo "  make migrate       Apply alembic migrations"
	@echo "  make migrate-new   Create new migration (msg=<description>)"
	@echo "  make deploy-api    Build + push API image, trigger App Runner update"
	@echo "  make deploy-worker Build + push worker image, update task definition"
	@echo "  make tf-plan       Preview infrastructure changes"
	@echo "  make tf-apply      Apply infrastructure changes"
	@echo "  make destroy-aws   Tear down all AWS resources"
	@echo ""

# ── Self-hosted deployment ────────────────────────────────────────────────────
deploy-local:
	docker compose -f deploy/local/docker-compose.yml up -d --build

seed:
	docker compose -f deploy/local/docker-compose.yml exec api python scripts/seed_dev.py

backup:
	bash deploy/local/scripts/backup.sh

migrate-prod:
	docker compose -f deploy/local/docker-compose.yml exec api alembic upgrade head
