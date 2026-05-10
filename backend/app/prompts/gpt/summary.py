def get(
    chapter_content: str,
    chapter_number: int,
    chapter_title: str,
) -> dict[str, str]:
    system = (
        "Summarize the following chapter in 150-250 words for use as context "
        "when writing subsequent chapters. Preserve key plot points, character "
        "developments, and important details. Output only the summary."
    )
    user = (
        f"Chapter {chapter_number}: {chapter_title}\n\n{chapter_content}"
    )
    return {"system": system, "user": user}
