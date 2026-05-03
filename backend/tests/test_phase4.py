"""
Phase 4 tests — full book lifecycle with mocked LLM.
No real API calls, no DB needed (uses in-memory SQLite).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import Base
from app.db.models import Book, BookStatus, Chapter
from app.services import book_service, chapter_service, orchestrator
from app.services.outline_service import approve_outline, generate_outline
from app.services.chapter_service import approve_chapter, get_chapters
from tests.fake_provider import FakeLLMProvider


FAKE_OUTLINE = """
Chapter 1: The Beginning - Where it all starts
Chapter 2: Rising Action - Things get complicated
Chapter 3: The Climax - Everything comes to a head
"""

FAKE_CHAPTER = "This is the full chapter content. It is engaging and well-written."
FAKE_SUMMARY = "A brief summary of the chapter for context chaining."


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def provider():
    return FakeLLMProvider(response=FAKE_OUTLINE)


@pytest.fixture
async def user_and_book(db):
    from app.db.models import User
    import hashlib, bcrypt
    pwd = bcrypt.hashpw(
        hashlib.sha256(b"password").hexdigest().encode(), bcrypt.gensalt()
    ).decode()
    user = User(email="test@example.com", hashed_password=pwd)
    db.add(user)
    await db.flush()

    book = await book_service.create_book(
        db=db,
        user_id=user.id,
        title="Test Book",
        selected_model="defaults",
    )
    await db.commit()
    return user, book


# ── Parser tests ──────────────────────────────────────────────────────────────

def test_outline_parser_standard():
    from app.parsers.outline_parser import parse_outline
    result = parse_outline(FAKE_OUTLINE)
    assert len(result) == 3
    assert result[0] == "The Beginning"
    assert result[1] == "Rising Action"


def test_outline_parser_various_formats():
    from app.parsers.outline_parser import parse_outline
    text = "1. First Chapter\n2. Second Chapter\n3. Third Chapter"
    result = parse_outline(text)
    assert len(result) == 3
    assert result[0] == "First Chapter"


def test_outline_parser_empty():
    from app.parsers.outline_parser import parse_outline
    result = parse_outline("no chapters here at all")
    assert result == []


def test_text_cleaner_preamble():
    from app.parsers.text_cleaner import clean_text
    assert clean_text("Here's your chapter:\nActual content") == "Actual content"
    assert clean_text("Certainly! Here is the outline:\nChapter 1") == "Chapter 1"


def test_text_cleaner_code_fence():
    from app.parsers.text_cleaner import clean_text
    assert clean_text("```markdown\nChapter 1: Title\n```") == "Chapter 1: Title"


def test_clean_chapter_strips_title():
    from app.parsers.text_cleaner import clean_chapter
    result = clean_chapter("Chapter 1: The Beginning\nActual content starts here.")
    assert "Chapter 1" not in result
    assert "Actual content" in result


# ── Prompt resolver tests ─────────────────────────────────────────────────────

def test_prompt_resolver_defaults():
    from app.prompts import resolve_outline
    result = resolve_outline(
        model_id="openai/gpt-4o",
        title="My Book",
        notes_before="A story about adventure",
    )
    assert "system" in result
    assert "user" in result
    assert "My Book" in result["user"]


def test_prompt_resolver_claude_family():
    from app.prompts import resolve_outline
    result = resolve_outline(
        model_id="anthropic/claude-3.5-sonnet",
        title="My Book",
        notes_before="A story about adventure",
    )
    assert "system" in result


def test_prompt_resolver_user_override():
    from app.prompts import resolve_outline
    result = resolve_outline(
        model_id="openai/gpt-4o",
        title="My Book",
        notes_before="notes",
        user_override="CUSTOM SYSTEM PROMPT",
    )
    assert result["system"] == "CUSTOM SYSTEM PROMPT"


# ── Service tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_outline(db, user_and_book):
    _, book = user_and_book
    provider = FakeLLMProvider(response=FAKE_OUTLINE)

    outline = await generate_outline(
        db=db,
        book=book,
        provider=provider,
        notes_before="A thrilling three-chapter story",
    )

    assert "Chapter 1" in outline
    assert book.status == BookStatus.OUTLINE_REVIEW
    assert book.outline_raw is not None


@pytest.mark.asyncio
async def test_approve_outline(db, user_and_book):
    _, book = user_and_book
    provider = FakeLLMProvider(response=FAKE_OUTLINE)

    await generate_outline(db=db, book=book, provider=provider, notes_before="notes")
    await approve_outline(db=db, book=book)
    await db.commit()

    assert book.status == BookStatus.CHAPTERS_GENERATING
    assert book.outline_approved is True


@pytest.mark.asyncio
async def test_initialize_chapters(db, user_and_book):
    _, book = user_and_book
    provider = FakeLLMProvider(response=FAKE_OUTLINE)

    await generate_outline(db=db, book=book, provider=provider, notes_before="notes")
    await approve_outline(db=db, book=book)
    count = await chapter_service.initialize_chapters(db, book)
    await db.commit()

    assert count == 3
    chapters = await get_chapters(db, book.id)
    assert len(chapters) == 3
    assert chapters[0].title == "The Beginning"


@pytest.mark.asyncio
async def test_generate_chapter(db, user_and_book):
    _, book = user_and_book
    provider = FakeLLMProvider(response=FAKE_OUTLINE)

    await generate_outline(db=db, book=book, provider=provider, notes_before="notes")
    await approve_outline(db=db, book=book)
    await chapter_service.initialize_chapters(db, book)

    chapters = await get_chapters(db, book.id)
    ch = chapters[0]

    provider_ch = FakeLLMProvider(response=FAKE_CHAPTER)
    await chapter_service.generate_chapter(db, book, ch, provider_ch)
    await db.commit()

    assert ch.content == FAKE_CHAPTER
    assert ch.summary is not None


# ── Full orchestrator lifecycle test ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_lifecycle(db, user_and_book):
    """
    INPUT_RECEIVED → OUTLINE_REVIEW (stops for human approval)
    After approve → CHAPTERS_GENERATING → CHAPTER_REVIEW (stops for human)
    After approve all → FINAL_REVIEW → COMPLETE
    """
    _, book = user_and_book

    # Fake provider returns outline text for outline stage, chapter content for chapter stage
    outline_provider = FakeLLMProvider(response=FAKE_OUTLINE)
    chapter_provider = FakeLLMProvider(response=FAKE_CHAPTER)

    # Step 1: run orchestrator — should stop at OUTLINE_REVIEW
    state = await orchestrator.run(
        db=db,
        book=book,
        provider=outline_provider,
        notes_before="A three-chapter adventure story",
    )
    assert state == BookStatus.OUTLINE_REVIEW

    # Step 2: human approves outline
    await approve_outline(db=db, book=book)
    await db.commit()
    await db.refresh(book)

    # Step 3: run orchestrator — generates all chapters, stops at CHAPTER_REVIEW
    state = await orchestrator.run(
        db=db, book=book, provider=chapter_provider
    )
    assert state == BookStatus.CHAPTER_REVIEW

    # Step 4: human approves all chapters
    chapters = await get_chapters(db, book.id)
    for ch in chapters:
        await approve_chapter(db=db, chapter=ch)
    book.status = BookStatus.CHAPTERS_GENERATING  # re-trigger orchestrator
    db.add(book)
    await db.commit()
    await db.refresh(book)

    # Step 5: orchestrator sees all approved → FINAL_REVIEW → auto-compiles → COMPLETE
    state = await orchestrator.run(
        db=db, book=book, provider=chapter_provider
    )
    assert state == BookStatus.COMPLETE
    assert book.compiled_path is not None
