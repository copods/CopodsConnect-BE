# services/moderation_service.py
import os
import httpx

# OpenAI client kept for future use — currently using Mistral for text moderation
# from openai import AsyncOpenAI
# _openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── Sightengine (Image Moderation) ────────────────────────────
SIGHTENGINE_API_URL = "https://api.sightengine.com/1.0/check.json"
SIGHTENGINE_USER = os.getenv("SIGHTENGINE_API_USER")
SIGHTENGINE_SECRET = os.getenv("SIGHTENGINE_API_SECRET")

# ── Mistral (Text Moderation) ─────────────────────────────────
MISTRAL_API_URL = "https://api.mistral.ai/v1/moderations"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# async def scan_text(text: str) -> tuple[float, str | None]:
#     """
#     Returns (score, category) where score is 0.0–1.0.
#     score = highest flagged category score from OpenAI moderation.
#     """
#     if not text or not text.strip():
#         return 0.0, None

#     response = await _openai_client.moderations.create(input=text)
#     result = response.results[0]

#     if not result.flagged:
#         # Even if not flagged, return the highest score so thresholds work
#         scores = result.category_scores.model_dump()
#         top_category = max(scores, key=scores.get)
#         return scores[top_category], None

#     scores = result.category_scores.model_dump()
#     top_category = max(scores, key=scores.get)
#     return scores[top_category], top_category

# ── Text Scan ─────────────────────────────────────────────────

async def scan_text(text: str) -> tuple[float, str | None]:
    """
    Returns (score, category) where score is 0.0–1.0.
    Uses Mistral moderation API — free, no billing required.

    Kept below for reference if switching back to OpenAI moderation:
    ----------------------------------------------------------------
    # response = await _openai_client.moderations.create(input=text)
    # result = response.results[0]
    # if not result.flagged:
    #     scores = result.category_scores.model_dump()
    #     top_category = max(scores, key=scores.get)
    #     return scores[top_category], None
    # scores = result.category_scores.model_dump()
    # top_category = max(scores, key=scores.get)
    # return scores[top_category], top_category
    ----------------------------------------------------------------
    """
    if not text or not text.strip():
        return 0.0, None

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            MISTRAL_API_URL,
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": "mistral-moderation-latest", "input": text},
        )
        resp.raise_for_status()
        data = resp.json()

    result = data["results"][0]
    categories = result["category_scores"]
    top_category = max(categories, key=categories.get)
    top_score = categories[top_category]

    flagged = any(result["categories"].values())
    if not flagged:
        return 0.0, None
    return top_score, top_category


# ── Image Scan ────────────────────────────────────────────────

async def scan_images(image_urls: list[str]) -> tuple[float, str | None]:
    """
    Returns (score, reason) where score is the highest nudity/offensive score
    across all images. Uses Sightengine REST API — 2000 free calls/month.
    """
    if not image_urls:
        return 0.0, None

    highest_score = 0.0
    highest_reason = None

    async with httpx.AsyncClient(timeout=15.0) as client:
        for url in image_urls:
            resp = await client.get(
                SIGHTENGINE_API_URL,
                params={
                    "url": url,
                    "models": "nudity-2.0,offensive",
                    "api_user": SIGHTENGINE_USER,
                    "api_secret": SIGHTENGINE_SECRET,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            # Nudity score — worst case across sexual_activity, sexual_display, erotica
            nudity = data.get("nudity", {})
            nudity_score = max(
                nudity.get("sexual_activity", 0.0),
                nudity.get("sexual_display", 0.0),
                nudity.get("erotica", 0.0),
            )

            # Offensive score
            offensive = data.get("offensive", {})
            offensive_score = offensive.get("prob", 0.0)

            score = max(nudity_score, offensive_score)
            reason = "nudity" if nudity_score >= offensive_score else "offensive"

            if score > highest_score:
                highest_score = score
                highest_reason = reason

    return highest_score, highest_reason