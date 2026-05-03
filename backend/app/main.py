from fastapi import FastAPI

app = FastAPI(
    title="BookForge API",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    # Phase 2 will add real DB + Redis checks here
    return {"status": "ok"}
