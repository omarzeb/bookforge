def get(
    chapter_content: str,
    chapter_number: int,
    chapter_title: str,
) -> dict[str, str]:
    system = (
        "You are a precise summarizer. Create concise summaries that preserve "
        "key plot points, character developments, arguments, and important details. "
        "The summary will be used as context for writing subsequent chapters. "
        "Output only the summary text — no preamble."
    )
    user = (
        f"Summarize Chapter {chapter_number} ({chapter_title}) in 150-250 words. "
        f"Preserve all essential information needed for continuity.\n\n"
        f"Chapter content:\n{chapter_content}"
    )
    return {"system": system, "user": user}
