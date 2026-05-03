def get(
    title: str,
    notes_before: str,
    notes_after: str = "",
    previous_outline: str = "",
) -> dict[str, str]:
    system = (
        "You are a professional book editor and outline architect. "
        "Create detailed, well-structured book outlines with chapter titles and brief descriptions. "
        "Output the outline as a numbered list. Each line must follow this exact format:\n"
        "Chapter N: Title - Brief description\n"
        "Include 8-15 chapters unless the notes specify otherwise. "
        "Do not include any preamble or closing remarks."
    )

    parts = [f'Create a detailed outline for a book titled: "{title}"']
    parts.append(f"\nEditor guidance:\n{notes_before}")

    if previous_outline and notes_after:
        parts.append(f"\nPrevious outline (rejected):\n{previous_outline}")
        parts.append(f"\nEditor revision notes:\n{notes_after}")
        parts.append("\nRevise the outline based on the editor feedback above.")

    return {"system": system, "user": "\n".join(parts)}
