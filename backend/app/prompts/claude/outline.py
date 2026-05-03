def get(
    title: str,
    notes_before: str,
    notes_after: str = "",
    previous_outline: str = "",
) -> dict[str, str]:
    system = (
        "You are an expert book editor. Think carefully about structure before writing. "
        "Output a numbered chapter list using exactly this format on each line:\n"
        "Chapter N: Title - Description\n"
        "8-15 chapters. No preamble, no closing remarks, no markdown."
    )

    parts = [f'Book title: "{title}"', f"\nGuidance:\n{notes_before}"]
    if previous_outline and notes_after:
        parts.append(f"\nRejected outline:\n{previous_outline}")
        parts.append(f"\nRevision notes:\n{notes_after}")
        parts.append("\nRevise accordingly.")

    return {"system": system, "user": "\n".join(parts)}
