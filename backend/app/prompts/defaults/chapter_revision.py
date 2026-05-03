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
        "You are a professional author revising a book chapter based on editorial feedback. "
        "Maintain consistency with the overall book while fully incorporating the editor's notes. "
        "Do NOT include the chapter title as a heading. Begin writing the revised chapter directly."
    )

    parts = [
        f'Book title: "{book_title}"',
        f"\nFull outline:\n{outline}",
        f"\nYou are revising Chapter {chapter_number}: {chapter_title}",
    ]

    if previous_summaries:
        summary_lines = "\n".join(
            f"Chapter {s['chapter_number']} ({s['chapter_title']}): {s['summary']}"
            for s in previous_summaries
        )
        parts.append(f"\nPrevious chapter summaries:\n{summary_lines}")

    parts.append(f"\nOriginal chapter (to be revised):\n{original_content}")
    parts.append(f"\nEditor revision notes:\n{editor_notes}")
    parts.append("\nWrite the complete revised chapter now.")

    return {"system": system, "user": "\n".join(parts)}
