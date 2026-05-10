def get(
    title: str,
    notes_before: str,
    notes_after: str = "",
    previous_outline: str = "",
) -> dict[str, str]:
    # DeepSeek responds well to concise, directive prompts
    system = "You are a book outline generator. Output only a numbered chapter list."

    user_parts = [
        f'Generate a book outline for: "{title}"',
        f"Guidance: {notes_before}",
        "Format each line as: Chapter N: Title - Description",
        "Include 8-15 chapters. No other text.",
    ]

    if previous_outline and notes_after:
        user_parts += [
            f"\nReject this outline:\n{previous_outline}",
            f"Reason: {notes_after}",
            "Generate a revised version.",
        ]

    return {"system": system, "user": "\n".join(user_parts)}
