def get(
    book_title: str,
    outline: str,
    chapter_title: str,
    chapter_number: int,
    previous_summaries: list[dict],
    chapter_notes: str = "",
) -> dict[str, str]:
    system = (
        "Write book chapters. Rules: no chapter heading, no preamble, "
        "start content immediately, maintain narrative continuity."
    )

    user_parts = [
        f'Book: "{book_title}"',
        f"Outline:\n{outline}",
        f"Write Chapter {chapter_number}: {chapter_title}",
    ]

    if previous_summaries:
        ctx = " | ".join(
            f"Ch{s['chapter_number']}: {s['summary']}" for s in previous_summaries
        )
        user_parts.append(f"Context: {ctx}")

    if chapter_notes:
        user_parts.append(f"Notes: {chapter_notes}")

    return {"system": system, "user": "\n".join(user_parts)}
