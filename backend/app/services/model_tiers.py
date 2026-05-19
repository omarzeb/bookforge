"""
Curated model tier configuration.

This is the source of truth for which models appear in the UI,
what tier they belong to, and their display metadata.
The ModelCache table stores live pricing from OpenRouter.
This config provides the curated subset + tier assignment.
"""

from dataclasses import dataclass


@dataclass
class CuratedModel:
    model_id: str
    name: str
    tier: str          # Recommended / Budget / Premium / Other
    context_k: int     # context window in thousands
    notes: str = ""    # shown as tooltip in UI


# The 8 curated models users see by default
CURATED_MODELS: list[CuratedModel] = [
    # ── Recommended ────────────────────────────────────────────────────────────
    CuratedModel(
        model_id="anthropic/claude-3.5-sonnet",
        name="Claude 3.5 Sonnet",
        tier="Recommended",
        context_k=200,
        notes="Best balance of quality and cost. Excellent at following complex instructions.",
    ),
    CuratedModel(
        model_id="openai/gpt-4o-mini",
        name="GPT-4o Mini",
        tier="Recommended",
        context_k=128,
        notes="Fast and affordable. Great for shorter books and drafting.",
    ),
    # ── Budget ─────────────────────────────────────────────────────────────────
    CuratedModel(
        model_id="deepseek/deepseek-chat",
        name="DeepSeek Chat",
        tier="Budget",
        context_k=64,
        notes="Very low cost. Good for long books where cost matters most.",
    ),
    CuratedModel(
        model_id="meta-llama/llama-3.1-8b-instruct",
        name="Llama 3.1 8B",
        tier="Budget",
        context_k=128,
        notes="Open-source and cheap. Quality varies — best for experimental use.",
    ),
    CuratedModel(
        model_id="google/gemini-flash-1.5",
        name="Gemini Flash 1.5",
        tier="Budget",
        context_k=1000,
        notes="Massive context window. Good for very long books.",
    ),
    # ── Premium ────────────────────────────────────────────────────────────────
    CuratedModel(
        model_id="anthropic/claude-3-opus",
        name="Claude 3 Opus",
        tier="Premium",
        context_k=200,
        notes="Highest quality output. Best for important projects where cost is secondary.",
    ),
    CuratedModel(
        model_id="openai/gpt-4o",
        name="GPT-4o",
        tier="Premium",
        context_k=128,
        notes="OpenAI's best model. Excellent reasoning and creative writing.",
    ),
    CuratedModel(
        model_id="google/gemini-pro-1.5",
        name="Gemini Pro 1.5",
        tier="Premium",
        context_k=1000,
        notes="Google's top model. Strong at structured, long-form content.",
    ),
]

CURATED_MODEL_IDS = {m.model_id for m in CURATED_MODELS}

TIER_ORDER = {"Recommended": 0, "Budget": 1, "Premium": 2, "Other": 3}


def get_curated_model(model_id: str) -> CuratedModel | None:
    return next((m for m in CURATED_MODELS if m.model_id == model_id), None)


def estimate_cost(
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    prompt_price_per_1k: float | None,
    completion_price_per_1k: float | None,
) -> float | None:
    """
    Estimate cost in USD for a generation call.
    Returns None if pricing data isn't available.
    """
    if prompt_price_per_1k is None or completion_price_per_1k is None:
        return None
    return (
        (prompt_tokens / 1000) * prompt_price_per_1k
        + (completion_tokens / 1000) * completion_price_per_1k
    )


def estimate_book_cost(
    chapters: int,
    avg_chapter_tokens: int = 3000,
    outline_tokens: int = 500,
    prompt_price_per_1k: float | None = None,
    completion_price_per_1k: float | None = None,
) -> dict:
    """
    Estimate total book generation cost.
    Returns low/high range based on token estimates.
    """
    if prompt_price_per_1k is None or completion_price_per_1k is None:
        return {"low": None, "high": None, "currency": "USD"}

    # Outline: ~500 prompt + 300 completion
    outline_cost = estimate_cost("", 500, 300, prompt_price_per_1k, completion_price_per_1k)

    # Each chapter: avg_chapter_tokens prompt context + same completion
    chapter_cost_each = estimate_cost(
        "", avg_chapter_tokens, avg_chapter_tokens,
        prompt_price_per_1k, completion_price_per_1k
    )

    # Summary per chapter: ~300 prompt + 150 completion
    summary_cost_each = estimate_cost("", 300, 150, prompt_price_per_1k, completion_price_per_1k)

    total = outline_cost + chapters * (chapter_cost_each + summary_cost_each)

    return {
        "low": round(total * 0.7, 4),   # optimistic (shorter chapters)
        "high": round(total * 1.3, 4),  # pessimistic (longer chapters)
        "currency": "USD",
    }
