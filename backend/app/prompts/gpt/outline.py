def get(
    title: str,
    notes_before: str,
    notes_after: str = "",
    previous_outline: str = "",
) -> dict[str, str]:
    system = (
        "You are a professional book editor. Create a structured book outline. "
        "Output ONLY a numbered chapter list, one per line, in this exact format:\n"
        "Chapter N: Title - Brief one-sentence description\n"
        "Include 8-15 chapters. No preamble, no closing remarks, no markdown headers."
    )

    parts = [f'Book title: "{title}"', f"\nGuidance:\n{notes_before}"]
    if previous_outline and notes_after:
        parts.append(f"\nPrevious outline:\n{previous_outline}")
        parts.append(f"\nRevision feedback:\n{notes_after}")
        parts.append("\nRevise the outline based on the feedback.")

    return {"system": system, "user": "\n".join(parts)}
