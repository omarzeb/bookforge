"""
Tolerant outline parser.

Handles the various ways LLMs format chapter lists:
  Chapter 1: Title - Description
  1. Title
  1) Title
  Chapter One: Title
  **Chapter 1: Title**   (markdown bold)
"""

import re
import structlog

logger = structlog.get_logger(__name__)

# All the numbering patterns we recognise
_PATTERNS = [
    # "Chapter 1: Title" or "Chapter 1. Title" or "Chapter 1 - Title"
    re.compile(r"^(?:chapter\s+)?(\d+)[.:)\-]\s*(.+)", re.IGNORECASE),
    # "1. Title" or "1) Title"
    re.compile(r"^(\d+)[.)]\s+(.+)"),
    # "**Chapter 1: Title**" — markdown bold
    re.compile(r"^\*{1,2}(?:chapter\s+)?(\d+)[.:)\-]\s*(.+?)\*{0,2}$", re.IGNORECASE),
]

# Separators that split "Title - Description" → we keep only the title part
_DESCRIPTION_SEP = re.compile(r"\s*[-–—]\s*")

# Code fences and leading #/> characters to strip
_CLEAN_RE = re.compile(r"^[#>`*\s]+|[#>`*\s]+$")


def _extract_title(raw: str) -> str:
    """Strip description after the first dash and clean up markdown."""
    title = _DESCRIPTION_SEP.split(raw, maxsplit=1)[0]
    title = _CLEAN_RE.sub("", title)
    return title.strip()


def parse_outline(outline_text: str) -> list[str]:
    """
    Extract chapter titles from a raw outline string.

    Returns a list of title strings in chapter order.
    Returns an empty list if nothing could be parsed
    (caller should retry with a nudge prompt).
    """
    titles: dict[int, str] = {}

    for line in outline_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        for pattern in _PATTERNS:
            match = pattern.match(line)
            if match:
                chapter_num = int(match.group(1))
                raw_title = match.group(2).strip()
                titles[chapter_num] = _extract_title(raw_title)
                break

    if not titles:
        logger.warning("outline_parse_failed", preview=outline_text[:200])
        return []

    # Sort by chapter number so any out-of-order lines are handled
    sorted_titles = [titles[n] for n in sorted(titles)]
    logger.info("outline_parsed", chapter_count=len(sorted_titles))
    return sorted_titles


NUDGE_PROMPT = (
    "Your previous outline could not be parsed. "
    "Please reformat it so each chapter is on its own line using this exact pattern:\n"
    "Chapter 1: Title\n"
    "Chapter 2: Title\n"
    "Do not include descriptions, bullet points, or markdown formatting."
)
