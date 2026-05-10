def get(
    book_title: str,
    outline: str,
    chapter_title: str,
    chapter_number: int,
    previous_summaries: list[dict],
    original_content: str,
    editor_notes: str,
) -> dict[str, str]:
    system = "Revise book chapters per editor notes. No heading. No preamble. Start immediately."
    user_parts = [
        f'Book: "{book_title}"',
        f"Chapter {chapter_number}: {chapter_title}",
        f"Feedback: {editor_notes}",
        f"Original:\n{original_content}",
    ]
    return {"system": system, "user": "\n".join(user_parts)}
