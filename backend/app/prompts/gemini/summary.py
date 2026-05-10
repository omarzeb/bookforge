def get(
    chapter_content: str,
    chapter_number: int,
    chapter_title: str,
) -> dict[str, str]:
    system = (
        "Summarize the chapter below in 150-250 words. "
        "Focus on: key events, character actions, important revelations, "
        "and anything that affects subsequent chapters. "
        "Write only the summary, no labels or headers."
    )
    user = f"Chapter {chapter_number}: {chapter_title}\n\n{chapter_content}"
    return {"system": system, "user": user}
