#!/usr/bin/env python3
"""
Seed script — creates a demo user with one sample book pre-populated.

Usage:
    docker compose exec api python scripts/seed.py
    docker compose exec api python scripts/seed.py --demo   # also enables DEMO_MODE user
"""

import asyncio
import argparse
import hashlib
import bcrypt
import sys
import os

sys.path.insert(0, "/app")


async def seed():
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from app.config import settings
    from app.db.models import Base, User, Book, BookStatus, Chapter

    engine = create_async_engine(settings.database_url)

    # Create tables if not exists
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as db:
        # Check if demo user already exists
        result = await db.execute(select(User).where(User.email == "demo@bookforge.app"))
        existing = result.scalar_one_or_none()

        if existing:
            print("Demo user already exists — skipping.")
            return

        # Create demo user
        pwd_hash = bcrypt.hashpw(
            hashlib.sha256(b"demo1234").hexdigest().encode(),
            bcrypt.gensalt()
        ).decode()

        user = User(
            email="demo@bookforge.app",
            hashed_password=pwd_hash,
            is_active=True,
        )
        db.add(user)
        await db.flush()

        # Create a sample book with an approved outline and 3 chapters
        book = Book(
            user_id=user.id,
            title="The Art of Getting Started",
            status=BookStatus.COMPLETE,
            selected_model="openai/gpt-4o-mini",
            outline_raw="""Chapter 1: Why Starting is the Hardest Part - The psychology of procrastination and why we avoid beginning.
Chapter 2: The Two-Minute Rule - A simple framework for breaking inertia on any task.
Chapter 3: Building Momentum - How small wins compound into lasting habits.""",
            outline_approved=True,
        )
        db.add(book)
        await db.flush()

        chapters_data = [
            (1, "Why Starting is the Hardest Part",
             """Every person who has ever faced a blank page, an empty project folder, or an unbegun task knows the feeling: a subtle but powerful resistance that keeps you from taking the first step. This isn't laziness. It's not a character flaw. It's a deeply human response to uncertainty.

When we haven't started something, it exists in a state of potential — perfect, unblemished, full of possibility. The moment we begin, we commit to one path and close off others. We risk discovering that the task is harder than we thought, or that our first attempt falls short of our imagination. Starting means accepting imperfection, and that's psychologically costly.

The good news is that this resistance is predictable, which means it's manageable. Understanding why starting feels so difficult is the first step toward overcoming it.""",
             "Explores the psychology of why starting is difficult — uncertainty, fear of imperfection, and the gap between imagination and execution."),
            (2, "The Two-Minute Rule",
             """The two-minute rule is elegantly simple: if a task takes less than two minutes to start, start it now. But its power extends beyond quick tasks. For anything that feels overwhelming, commit to just two minutes of work. Not completion — just two minutes.

This works because of a quirk in how our brains assess effort. The anticipation of a task is almost always worse than the task itself. Once you're in motion, the psychological barrier dissolves. Two minutes of actual work rewires your perception of the entire project from threatening to manageable.

Set a timer. Open the document. Write one sentence. Close one email. That's it. Most of the time, you'll keep going. And on the days you don't, you've still moved forward — which is infinitely better than standing still.""",
             "Introduces the two-minute rule as a practical technique for overcoming inertia, explaining the neuroscience behind why it works."),
            (3, "Building Momentum",
             """Momentum isn't a metaphor — it's a measurable psychological state. When we complete small tasks, our brains release dopamine, a neurotransmitter associated with motivation and reward. This creates a positive feedback loop: completion leads to motivation, motivation leads to action, action leads to more completion.

The key is engineering your environment to manufacture early wins. Break your goal into the smallest possible units. Define what 'done' looks like for each unit. Celebrate completions explicitly, even briefly. This isn't self-delusion — it's training your reward system to associate effort with positive outcomes.

Over time, momentum becomes self-sustaining. The person who struggled to begin a task becomes someone for whom beginning is simply what they do. Not because they changed who they are, but because they changed the conditions in which they work.""",
             "Explains how to build and sustain momentum through small wins and dopamine loops, with practical techniques for maintaining progress."),
        ]

        for num, title, content, summary in chapters_data:
            chapter = Chapter(
                book_id=book.id,
                number=num,
                title=title,
                content=content,
                summary=summary,
                approved=True,
            )
            db.add(chapter)

        await db.commit()

        print(f"✓ Demo user created: demo@bookforge.app / demo1234")
        print(f"✓ Sample book created: '{book.title}'")
        print(f"✓ 3 chapters seeded")
        print()
        print("Login at /login with demo@bookforge.app / demo1234")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
