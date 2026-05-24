#!/usr/bin/env python3
"""
DEV seed — creates demo@bookforge.app / demo1234.
NEVER run this in production.
"""
import asyncio, hashlib, bcrypt, sys
sys.path.insert(0, "/app")

async def seed():
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from app.config import settings
    from app.db.models import Base, User, Book, BookStatus, Chapter

    assert not settings.is_production, "seed_dev.py must not run in production!"

    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        if (await db.execute(select(User).where(User.email == "demo@bookforge.app"))).scalar_one_or_none():
            print("Demo user already exists — skipping.")
            return

        import hmac as _hmac
        pepper = settings.app_secret_key.encode()
        peppered = _hmac.new(pepper, "demo1234".encode(), "sha256").hexdigest().encode()
        pwd_hash = bcrypt.hashpw(peppered, bcrypt.gensalt()).decode()

        user = User(email="demo@bookforge.app", hashed_password=pwd_hash, is_active=True)
        db.add(user)
        await db.flush()

        book = Book(
            user_id=user.id, title="The Art of Getting Started",
            status=BookStatus.COMPLETE, selected_model="openai/gpt-4o-mini",
            outline_raw="Chapter 1: Why Starting is Hard\nChapter 2: The Two-Minute Rule\nChapter 3: Building Momentum",
            outline_approved=True,
        )
        db.add(book)
        await db.flush()

        for num, title, content in [
            (1, "Why Starting is Hard", "Every person who has faced a blank page knows the feeling..."),
            (2, "The Two-Minute Rule", "The two-minute rule is elegantly simple: if a task takes less than two minutes, start it now..."),
            (3, "Building Momentum", "Momentum is a measurable psychological state. Small wins release dopamine..."),
        ]:
            db.add(Chapter(book_id=book.id, number=num, title=title, content=content, approved=True))

        await db.commit()
        print("✓ Demo user: demo@bookforge.app / demo1234")
        print("✓ Sample book seeded")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed())
