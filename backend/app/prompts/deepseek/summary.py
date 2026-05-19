def get(
    chapter_content: str,
    chapter_number: int,
    chapter_title: str,
) -> dict[str, str]:
    system = "Summarize book chapters in 150-250 words for continuity context. Output only the summary."
    user = f"Summarize Chapter {chapter_number} ({chapter_title}):\n\n{chapter_content}"
    return {"system": system, "user": user}
