def get(
    book_title: str,
    outline: str,
    chapter_title: str,
    chapter_number: int,
    previous_summaries: list[dict],
    chapter_notes: str = "",
) -> dict[str, str]:
    system = (
        "You are writing a chapter for a book. Follow these rules:\n"
        "1. Write in flowing, engaging prose.\n"
        "2. Do NOT start with the chapter title or number.\n"
        "3. Do NOT write 'Here is the chapter' or any preamble.\n"
        "4. Maintain consistency with previous chapters.\n"
        "5. Begin the chapter content immediately."
    )

    parts = [
        f'Book title: "{book_title}"',
        f"\nFull outline:\n{outline}",
        f"\nCurrent task: Write Chapter {chapter_number}: {chapter_title}",
    ]

    if previous_summaries:
        lines = "\n".join(
            f"- Chapter {s['chapter_number']} ({s['chapter_title']}): {s['summary']}"
            for s in previous_summaries
        )
        parts.append(f"\nPrevious chapter summaries:\n{lines}")
    else:
        parts.append("\nThis is the opening chapter.")

    if chapter_notes:
        parts.append(f"\nSpecial instructions:\n{chapter_notes}")

    return {"system": system, "user": "\n".join(parts)}
