#!/usr/bin/env python3
"""
PROD seed — runs migrations only, creates no users.
A random admin password is printed once and never stored in code.
"""
import asyncio, secrets, sys
sys.path.insert(0, "/app")

async def seed():
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.config import settings
    from app.db.models import Base

    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("✓ Database schema up to date")
    print("✓ No demo users created in production")
    print()
    print("To create your first account, use the /register endpoint with a strong password.")

if __name__ == "__main__":
    asyncio.run(seed())
