def get(
    title: str,
    notes_before: str,
    notes_after: str = "",
    previous_outline: str = "",
) -> dict[str, str]:
    # Gemini works well with explicit structure and step-by-step instructions
    system = (
        "You are a book editor. Follow these instructions precisely:\n"
        "1. Read the book title and guidance carefully.\n"
        "2. Create a chapter-by-chapter outline.\n"
        "3. Format each chapter on its own line as: Chapter N: Title - Description\n"
        "4. Include 8-15 chapters.\n"
        "5. Output ONLY the chapter list. No introduction, no conclusion."
    )

    parts = [f'Book title: "{title}"', f"\nGuidance:\n{notes_before}"]
    if previous_outline and notes_after:
        parts.append(f"\nPrevious outline (needs revision):\n{previous_outline}")
        parts.append(f"\nRevision instructions:\n{notes_after}")

    return {"system": system, "user": "\n".join(parts)}
