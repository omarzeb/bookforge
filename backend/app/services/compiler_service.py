"""
Compiler service — assembles approved chapters into docx or txt.
Ported from compiler.py. Accepts a storage_backend dependency.
"""

import re
from pathlib import Path

import structlog
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import ConflictError
from app.db.models import Book, BookStatus, OutputFormat
from app.services.chapter_service import get_chapters

logger = structlog.get_logger(__name__)


def _sanitize(title: str) -> str:
    safe = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
    return safe.strip().replace(" ", "_")[:80]


async def compile_book(
    db: AsyncSession,
    book: Book,
    output_format: OutputFormat = OutputFormat.DOCX,
    output_dir: str = "/app/output",
) -> str:
    """
    Compile the book into a file.
    Returns the file path (local) or S3 key (production).
    Phase 6 will swap local writes for S3 uploads via storage_backend dependency.
    """
    chapters = await get_chapters(db, book.id)

    if not chapters:
        raise ConflictError("No chapters to compile")

    unapproved = [c for c in chapters if not c.approved]
    if unapproved:
        nums = [str(c.number) for c in unapproved]
        raise ConflictError(f"Chapters not yet approved: {', '.join(nums)}")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename = f"{book.id}.{output_format.value}"  # UUID filename — safe, no path traversal
    filepath = str(Path(output_dir) / filename)

    if output_format == OutputFormat.DOCX:
        _write_docx(book, chapters, filepath)
    else:
        _write_txt(book, chapters, filepath)

    book.compiled_path = filepath
    book.output_format = output_format
    book.status = BookStatus.COMPLETE
    db.add(book)

    logger.info("book_compiled", book_id=book.id, path=filepath, fmt=output_format)
    return filepath


def _write_docx(book: Book, chapters: list, filepath: str) -> None:
    doc = Document()

    style = doc.styles["Normal"]
    style.font.name = "Georgia"
    style.font.size = Pt(12)

    # Title page
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_para.space_before = Pt(200)
    run = title_para.add_run(book.title)
    run.font.size = Pt(28)
    run.bold = True
    doc.add_page_break()

    # TOC
    doc.add_heading("Table of Contents", level=1)
    for ch in chapters:
        doc.add_paragraph(f"Chapter {ch.number}: {ch.title}", style="List Number")
    doc.add_page_break()

    # Chapters
    for ch in chapters:
        doc.add_heading(f"Chapter {ch.number}: {ch.title}", level=1)
        for para in (ch.content or "").split("\n"):
            para = para.strip()
            if para:
                doc.add_paragraph(para)
        doc.add_page_break()

    doc.save(filepath)


def _write_txt(book: Book, chapters: list, filepath: str) -> None:
    lines = [
        "=" * 60,
        book.title.center(60),
        "=" * 60,
        "",
        "TABLE OF CONTENTS",
        "-" * 40,
    ]
    for ch in chapters:
        lines.append(f"  Chapter {ch.number}: {ch.title}")
    lines += ["", "=" * 60, ""]

    for ch in chapters:
        lines += [
            f"CHAPTER {ch.number}: {ch.title.upper()}",
            "-" * 40,
            "",
            ch.content or "",
            "",
            "=" * 60,
            "",
        ]

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
