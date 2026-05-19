# Contributing

## Development setup

```bash
git clone https://github.com/YOUR_USERNAME/book-forge
cd book-forge

# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -e ".[dev]"

# Frontend
cd ../frontend
npm install
```

## Running tests

```bash
# Backend (with Docker for DB + Redis)
docker compose -f deploy/local/docker-compose.yml up -d postgres redis
cd backend
pytest tests/ -v

# Run a specific phase
pytest tests/test_phase8.py -v

# With coverage
pytest tests/ --cov=app --cov-report=term-missing
```

## Environment variables

Copy `backend/.env.example` to `backend/.env`. Minimum required:

```bash
APP_SECRET_KEY=any-random-string
FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
JWT_SECRET=any-random-string
```

## Code style

- Python: ruff (line length 100)
- TypeScript: ESLint with Next.js config
- Commits: conventional commits preferred (`feat:`, `fix:`, `docs:`)

## Adding a new prompt family

1. Create `backend/app/prompts/{family}/` with `__init__.py`, `outline.py`, `chapter.py`, `chapter_revision.py`, `summary.py`
2. Add the family fragment to `_FAMILY_MAP` in `backend/app/prompts/__init__.py`
3. Add to `MODEL_FAMILIES` in `frontend/components/PromptEditor.tsx`
4. Write tests in `tests/test_phase8.py`
