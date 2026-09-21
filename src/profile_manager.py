"""
Candidate Master Profile Manager.
Provides mechanisms to build, convert, load, and manage master ground-truth profiles
from free-form notes, uploaded files, or interactive questionnaire responses.
"""

import json
from pathlib import Path
from typing import Optional, Any
from google import genai
from google.genai import types
# pyrefly: ignore [missing-import]
from src.models import CandidateProfile
# pyrefly: ignore [missing-import]
from src.ai_engine import get_client, _generate_with_fallback, SYSTEM_INSTRUCTION


def convert_document_to_profile(
    document_text: str, client: Optional[genai.Client] = None
) -> CandidateProfile:
    """
    Parses any background document, notes, markdown, or existing CV text
    into a comprehensive, structured CandidateProfile.
    """
    client = client or get_client()

    prompt = f"""
You are an expert career profiler and technical background analyst.
Extract all verified background information from the candidate's notes or document into the CandidateProfile schema.

Source Text:
{document_text}

Extraction Guidelines:
1. Capture all verified work experience, including company, role, dates, bullets, and any unlisted nuances or engineering details mentioned.
2. Capture all projects, their tech stacks, descriptions, and any deep-dive architecture/implementation notes.
3. Categorize all technical skills into programming_languages, frameworks_and_tools, and core_concepts.
4. Extract all education records, GPAs, coursework, and honors.
5. Capture any leadership, military service, athletics, or volunteering into additional_background.
6. PRESERVE all factual metrics (e.g., speedups, wait-time reductions, team sizes, grades) exactly.
7. Do not fabricate facts or invent technologies not present in the source.
"""

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=CandidateProfile,
        temperature=0.1,
    )

    response = _generate_with_fallback(client, prompt, config)
    return CandidateProfile.model_validate_json(response.text)


def build_profile_from_questionnaire(
    answers: dict[str, Any], client: Optional[genai.Client] = None
) -> CandidateProfile:
    """
    Takes user questionnaire responses and synthesizes them into a structured CandidateProfile.
    """
    client = client or get_client()

    prompt = f"""
Convert the following candidate questionnaire answers into a polished CandidateProfile.

Candidate Responses:
{json.dumps(answers, indent=2, ensure_ascii=False)}

Rules:
1. Organize into clean, verified records across personal, skills, experience, projects, education, and background.
2. Preserve all stated metrics, numbers, and specific technologies without alteration.
3. Do not invent details not provided by the user.
"""

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=CandidateProfile,
        temperature=0.15,
    )

    response = _generate_with_fallback(client, prompt, config)
    return CandidateProfile.model_validate_json(response.text)


def load_profile_file(path: Path) -> Optional[CandidateProfile]:
    """Loads a candidate profile from a JSON file."""
    path = Path(path).resolve()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return CandidateProfile.model_validate(data)
    except Exception:
        return None


def save_profile_file(profile: CandidateProfile, path: Path) -> Path:
    """Saves a candidate profile to a JSON file."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return path
