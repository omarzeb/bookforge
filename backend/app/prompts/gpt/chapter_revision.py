def get(
    book_title: str,
    outline: str,
    chapter_title: str,
    chapter_number: int,
    previous_summaries: list[dict],
    original_content: str,
    editor_notes: str,
) -> dict[str, str]:
    system = (
        "You are a skilled author revising a book chapter. "
        "Apply all editor feedback. No title heading. No preamble. "
        "Begin with the chapter content directly."
    )
    parts = [
        f'Book: "{book_title}"',
        f"\nOutline:\n{outline}",
        f"\nRevise Chapter {chapter_number}: {chapter_title}",
    ]
    if previous_summaries:
        lines = "\n".join(
            f"Ch{s['chapter_number']}: {s['summary']}" for s in previous_summaries
        )
        parts.append(f"\nContext:\n{lines}")
    parts.append(f"\nOriginal:\n{original_content}")
    parts.append(f"\nFeedback:\n{editor_notes}")
    return {"system": system, "user": "\n".join(parts)}
