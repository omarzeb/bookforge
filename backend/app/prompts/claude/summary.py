def get(
    chapter_content: str,
    chapter_number: int,
    chapter_title: str,
) -> dict[str, str]:
    # Claude-specific: ask it to be even more concise
    system = (
        "You are a precise summarizer for continuity purposes. "
        "Output only the summary — no preamble, no label."
    )
    user = (
        f"Summarize Chapter {chapter_number} ({chapter_title}) in exactly 150-200 words "
        f"for use as context in future chapters.\n\nChapter:\n{chapter_content}"
    )
    return {"system": system, "user": user}
