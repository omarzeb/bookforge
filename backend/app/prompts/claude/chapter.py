def get(
    book_title: str,
    outline: str,
    chapter_title: str,
    chapter_number: int,
    previous_summaries: list[dict],
    chapter_notes: str = "",
) -> dict[str, str]:
    system = (
        "You are a skilled author. Write immersive, detailed prose. "
        "Start the chapter content immediately — no title heading, no 'Here is the chapter' preamble. "
        "Maintain consistency with the summaries provided."
    )

    parts = [
        f'Title: "{book_title}"',
        f"\nOutline:\n{outline}",
        f"\nWrite Chapter {chapter_number}: {chapter_title}",
    ]

    if previous_summaries:
        lines = "\n".join(
            f"Ch{s['chapter_number']} ({s['chapter_title']}): {s['summary']}"
            for s in previous_summaries
        )
        parts.append(f"\nContext from previous chapters:\n{lines}")

    if chapter_notes:
        parts.append(f"\nEditor notes:\n{chapter_notes}")

    return {"system": system, "user": "\n".join(parts)}
