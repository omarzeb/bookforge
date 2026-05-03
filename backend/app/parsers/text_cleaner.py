"""
Text cleaner — strips LLM preambles from generated content.

LLMs often prepend phrases like "Here's your chapter:" or
"Certainly! Here is the outline:" before the actual content.
These need to be stripped before saving.
"""

import re

# Patterns that commonly appear before actual content
_PREAMBLES = [
    r"^here'?s?\s+(your\s+)?(chapter|outline|summary|revised|rewritten|updated)[^:]*:\s*",
    r"^certainly[!,.]?\s*(here'?s?\s+)?(the|your|a)?\s*(chapter|outline|summary)?[^:]*:\s*",
    r"^sure[!,.]?\s*(here'?s?\s+)?(the|your|a)?\s*(chapter|outline|summary)?[^:]*:\s*",
    r"^of course[!,.]?\s*(here'?s?\s+)?(the|your|a)?\s*(chapter|outline|summary)?[^:]*:\s*",
    r"^absolutely[!,.]?\s*(here'?s?\s+)?(the|your|a)?\s*(chapter|outline|summary)?[^:]*:\s*",
    r"^below\s+is\s+(the|your|a)\s*(chapter|outline|summary)[^:]*:\s*",
    r"^i('ve)?\s+(written|created|generated|drafted)[^:]*:\s*",
]

_PREAMBLE_RE = re.compile(
    "|".join(_PREAMBLES),
    re.IGNORECASE | re.MULTILINE,
)

# Code fences that sometimes wrap content
_CODE_FENCE_RE = re.compile(r"^```[a-z]*\n?(.*?)\n?```$", re.DOTALL)


def clean_text(text: str) -> str:
    """
    Remove LLM preambles and code fences from generated text.
    Returns the cleaned content.
    """
    text = text.strip()

    # Strip code fences first (```markdown ... ```)
    fence_match = _CODE_FENCE_RE.match(text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Strip leading preamble phrases
    text = _PREAMBLE_RE.sub("", text, count=1).strip()

    return text


def clean_chapter(text: str) -> str:
    """
    Clean a generated chapter. Same as clean_text but also strips
    a repeated chapter title if the LLM included it despite being told not to.
    """
    text = clean_text(text)

    # Strip a leading "Chapter N: Title" line if present
    text = re.sub(
        r"^chapter\s+\d+[.:)]\s*.+\n",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    ).strip()

    return text
