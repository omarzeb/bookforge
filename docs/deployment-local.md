# Self-Hosted Deployment Guide

This guide deploys BookForge on any machine with Docker installed —
your laptop, a home server, or a cheap VPS.

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- A domain name added to Cloudflare (free)
- 2GB RAM minimum

## Quick start (5 steps)

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/book-forge
cd book-forge
cp backend/.env.example backend/.env
```

Edit `backend/.env` — the required fields are:
- `APP_SECRET_KEY` — any random string (e.g. `openssl rand -hex 32`)
- `FERNET_KEY` — run `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `JWT_SECRET` — any random string

Everything else has working defaults for local deployment.

### 2. Build and start

```bash
docker compose -f deploy/local/docker-compose.yml up -d --build
```

### 3. Run migrations and seed

```bash
docker compose -f deploy/local/docker-compose.yml exec api alembic upgrade head
docker compose -f deploy/local/docker-compose.yml exec api python scripts/seed_dev.py
```

### 4. Set up Cloudflare Tunnel

Follow `docs/cloudflare-tunnel.md` to get a public HTTPS URL.
Update `deploy/local/Caddyfile` with your domain.

### 5. Restart with domain

```bash
docker compose -f deploy/local/docker-compose.yml restart caddy
```

Visit `https://bookforge.yourdomain.com` — done.

## Make it survive reboots (Linux)

```bash
sudo cp deploy/local/bookforge.service /etc/systemd/system/
sudo systemctl enable bookforge
```

## Set up daily backups

```bash
# Add to crontab (runs at 2am daily)
echo "0 2 * * * /opt/bookforge/deploy/local/scripts/backup.sh" | crontab -
```

## Update to latest version

```bash
git pull
docker compose -f deploy/local/docker-compose.yml up -d --build
docker compose -f deploy/local/docker-compose.yml exec api alembic upgrade head
```

## Demo mode

Set `DEMO_MODE=true` and `OPENROUTER_DEMO_KEY=sk-or-...` in `.env` to
let visitors generate books without signing up — using your demo key with
a rate limit.
