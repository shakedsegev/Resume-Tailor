import os
import json
import time
from typing import Optional, Any
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from google import genai
# pyrefly: ignore [missing-import]
from google.genai import types
# pyrefly: ignore [missing-import]
from google.genai.errors import ServerError
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

# Load environment variables from .env
load_dotenv()

# Default model priorities (can be overridden via GEMINI_MODEL in .env)
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
FALLBACK_MODELS = ["gemini-3.5-flash-lite", "gemini-3.6-flash"]

SYSTEM_INSTRUCTION = """
You are an expert ATS (Applicant Tracking System) optimization and technical resume tailoring specialist.
Your role is to analyze job descriptions against a candidate's verified profile and tailor resume content with precision.

HARD RULES:
1. ZERO FABRICATION (NO HALLUCINATIONS): Never invent technologies, tools, companies, degrees, dates, metrics, or achievements. Every claim MUST be grounded in the candidate's actual profile.
2. METRIC PRESERVATION: Never alter or inflate numbers, percentages, team sizes, dollar amounts, or timelines. Keep all verified metrics exactly as stated.
3. KEYWORD ALIGNMENT: Naturally incorporate relevant keywords and terminology from the job description to optimize for ATS filters, but only when describing legitimate matching experience.
4. ACTION-ORIENTED & CONCISE: Format bullet points using strong action verbs, context, and clear impact (e.g., "Accomplished [X] as measured by [Y], by doing [Z]"). Avoid padding, buzzwords, and fluff.
5. NO FLATTERY: Be objective and honest about match gaps and alignment.
"""


class FitAnalysis(BaseModel):
    match: list[str] = Field(
        description="List of JD requirements the candidate strongly covers."
    )
    partial: list[str] = Field(
        description="Requirements touched lightly or covered with transferable skills."
    )
    gap: list[str] = Field(
        description="Requirements the candidate lacks (must not be fabricated)."
    )
    pitch_angle: str = Field(
        description="1-2 sentences on how best to position the candidate for this specific role."
    )


class TailoredBullets(BaseModel):
    bullets: list[str] = Field(
        description="List of tailored, ATS-aligned bullet points preserving original facts."
    )


def get_client() -> genai.Client:
    """
    Initializes and returns a Google Gen AI client.
    Raises ValueError if GEMINI_API_KEY is not configured in the environment.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. Please add it to your .env file."
        )
    return genai.Client(api_key=api_key)


def _generate_with_fallback(
    client: genai.Client,
    contents: str,
    config: types.GenerateContentConfig,
    preferred_model: Optional[str] = None,
) -> Any:
    """
    Calls the Gemini API with automatic fallback and retry if a model experiences high demand (503).
    """
    primary = preferred_model or DEFAULT_MODEL
    models_to_try = [primary] + [m for m in FALLBACK_MODELS if m != primary]

    last_error = None
    for model in models_to_try:
        for attempt in range(2):  # Try twice per model
            try:
                return client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
            except ServerError as err:
                last_error = err
                time.sleep(1.0)
            except Exception as err:
                last_error = err
                break  # If non-server error (e.g., 404), move to next model

    raise RuntimeError(
        f"All models failed to respond. Last error: {last_error}"
    )


def analyze_job_fit(
    profile: dict, job_description: str, client: Optional[genai.Client] = None
) -> FitAnalysis:
    """
    Compares the candidate's profile to a job description.
    Returns structured MATCH, PARTIAL, GAP, and PITCH ANGLE.
    """
    client = client or get_client()

    prompt = f"""
Analyze the candidate's profile against the target job description.

Candidate Profile:
{json.dumps(profile, indent=2, ensure_ascii=False)}

Target Job Description:
{job_description}

Provide an honest, objective breakdown following the schema:
- match: Must-have requirements the candidate legitimately covers
- partial: Requirements covered via adjacent or transferable skills
- gap: Requirements lacking from the candidate's background
- pitch_angle: Recommended 1-2 sentence framing angle for this application
"""

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=FitAnalysis,
        temperature=0.2,
    )

    response = _generate_with_fallback(client, prompt, config)
    return FitAnalysis.model_validate_json(response.text)


def tailor_experience_bullets(
    bullets: list[str],
    job_description: str,
    profile: Optional[dict] = None,
    client: Optional[genai.Client] = None,
) -> list[str]:
    """
    Rewrites and reorders a list of bullet points for a specific job description.
    Preserves all facts and metrics while aligning keywords to ATS expectations.
    """
    client = client or get_client()

    profile_context = (
        f"\nCandidate Background Context:\n{json.dumps(profile, indent=2, ensure_ascii=False)}"
        if profile
        else ""
    )

    prompt = f"""
Tailor the following resume bullet points for the target job description.

Original Bullet Points:
{json.dumps(bullets, indent=2, ensure_ascii=False)}
{profile_context}

Target Job Description:
{job_description}

Rules:
- Reorder bullets so the most relevant experience to the JD leads first.
- Mirror ATS keywords from the JD where they honestly describe the original work.
- DO NOT invent new metrics or technologies not present in the original bullets or background.
- Keep all numbers and metrics exactly as stated.
"""

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=TailoredBullets,
        temperature=0.3,
    )

    response = _generate_with_fallback(client, prompt, config)
    parsed = TailoredBullets.model_validate_json(response.text)
    return parsed.bullets
