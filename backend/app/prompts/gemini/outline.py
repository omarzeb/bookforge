def get(
    title: str,
    notes_before: str,
    notes_after: str = "",
    previous_outline: str = "",
    chapter_count: int = 10,
) -> dict[str, str]:
    system = (
        "You are a professional book editor creating a book outline. "
        f"You MUST write EXACTLY {chapter_count} chapters — not more, not fewer. "
        "Each chapter must be on its own line in this exact format:\n"
        "Chapter N: Title - Brief one-sentence description\n"
        "Do not include any introduction, conclusion, or other text. "
        "Only the chapter list."
    )

    parts = [
        f'Book title: "{title}"',
        f"Number of chapters required: {chapter_count} (you must write exactly {chapter_count} chapters)",
        f"\nGuidance:\n{notes_before}",
    ]

    if previous_outline and notes_after:
        parts.append(f"\nPrevious outline (needs revision):\n{previous_outline}")
        parts.append(f"\nRevision feedback:\n{notes_after}")
        parts.append(f"\nIMPORTANT: Still write exactly {chapter_count} chapters.")

    parts.append(f"\nWrite the {chapter_count}-chapter outline now:")

    return {"system": system, "user": "\n".join(parts)}
