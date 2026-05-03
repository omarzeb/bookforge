def get(
    book_title: str,
    outline: str,
    chapter_title: str,
    chapter_number: int,
    previous_summaries: list[dict],
    chapter_notes: str = "",
) -> dict[str, str]:
    system = (
        "You are a professional author writing a book chapter. "
        "Write in a consistent, engaging tone. Be thorough and detailed. "
        "Do NOT include the chapter title as a heading — it will be added automatically. "
        "Do not include any preamble like 'Here is the chapter:'. "
        "Begin writing the chapter content directly."
    )

    parts = [
        f'Book title: "{book_title}"',
        f"\nFull outline:\n{outline}",
        f"\nYou are writing Chapter {chapter_number}: {chapter_title}",
    ]

    if previous_summaries:
        summary_lines = "\n".join(
            f"Chapter {s['chapter_number']} ({s['chapter_title']}): {s['summary']}"
            for s in previous_summaries
        )
        parts.append(f"\nPrevious chapter summaries for continuity:\n{summary_lines}")
    else:
        parts.append("\nThis is the first chapter of the book.")

    if chapter_notes:
        parts.append(f"\nEditor notes for this chapter:\n{chapter_notes}")

    parts.append("\nWrite the complete chapter now.")
    return {"system": system, "user": "\n".join(parts)}
