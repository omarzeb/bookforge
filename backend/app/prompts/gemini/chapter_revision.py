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
        "You are revising a book chapter. Rules:\n"
        "1. Apply all editor notes precisely.\n"
        "2. Do not include the chapter title.\n"
        "3. Begin with content immediately.\n"
        "4. Preserve the voice and style."
    )
    parts = [
        f'Book: "{book_title}"',
        f"\nOutline:\n{outline}",
        f"\nRevise Chapter {chapter_number}: {chapter_title}",
    ]
    if previous_summaries:
        lines = "\n".join(f"- Ch{s['chapter_number']}: {s['summary']}" for s in previous_summaries)
        parts.append(f"\nContext:\n{lines}")
    parts.append(f"\nOriginal chapter:\n{original_content}")
    parts.append(f"\nEditor notes:\n{editor_notes}")
    return {"system": system, "user": "\n".join(parts)}
