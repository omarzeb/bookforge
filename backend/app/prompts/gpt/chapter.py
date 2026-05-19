def get(
    book_title: str,
    outline: str,
    chapter_title: str,
    chapter_number: int,
    previous_summaries: list[dict],
    chapter_notes: str = "",
) -> dict[str, str]:
    system = (
        "You are a skilled author writing a book chapter. "
        "Write detailed, engaging prose. "
        "Do NOT include the chapter title as a heading. "
        "Do NOT include any preamble like 'Here is the chapter:'. "
        "Start writing the chapter content immediately."
    )

    parts = [
        f'Book: "{book_title}"',
        f"\nOutline:\n{outline}",
        f"\nWrite Chapter {chapter_number}: {chapter_title}",
    ]

    if previous_summaries:
        lines = "\n".join(
            f"Ch{s['chapter_number']} ({s['chapter_title']}): {s['summary']}"
            for s in previous_summaries
        )
        parts.append(f"\nPrevious chapters (for continuity):\n{lines}")

    if chapter_notes:
        parts.append(f"\nEditor notes:\n{chapter_notes}")

    return {"system": system, "user": "\n".join(parts)}
