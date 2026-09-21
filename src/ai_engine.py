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


class TailoredProject(BaseModel):
    title_suffix: str = Field(
        description="The technology tags following the pipe '|' in the project title. Strictly MAX 45 characters (e.g. ' | Java, C++, Sockets, Reactor'). Must start with ' | '."
    )
    description: str = Field(
        description="Tailored project description. Strictly MAX 140 characters to fit exactly in 2 lines and prevent vertical overlap."
    )


class TailoredProjects(BaseModel):
    projects: list[TailoredProject] = Field(
        description="List of tailored project items matching original count."
    )


class FullTailoredResume(BaseModel):
    fit_analysis: FitAnalysis = Field(
        description="Structured assessment of candidate fit against the job description."
    )
    experience_bullets: list[str] = Field(
        description="Exactly 6 tailored experience bullets for Verifone. Each bullet strictly MAX 135 characters to fit in 2 lines without overlapping."
    )
    academic_projects: list[TailoredProject] = Field(
        description="3 tailored projects with relevant tech tags and descriptions strictly MAX 140 characters."
    )
    ordered_languages: list[str] = Field(
        default_factory=list,
        description="Reordered list of the candidate's 7 languages with top JD requirements first (e.g. Python, C++, SQL, Java, TypeScript, C, Assembly x86)."
    )
    tools_lines: list[str] = Field(
        description="Candidate's tools and platforms (e.g. Linux, Docker, Git, Bash, WSL, macOS, VS Code, Claude, ChatGPT, AntiGravity) formatted across exactly 4 lines, each strictly MAX 25 characters. Do NOT include programming languages."
    )
    core_concepts_lines: list[str] = Field(
        description="Candidate's engineering concepts (e.g. Multithreading, Concurrency, Sockets, OOP, Memory Management, SOLID Principles) formatted across exactly 2 lines, line 1 MAX 35 characters, line 2 MAX 30 characters."
    )
    coursework_line: str = Field(
        description="Coursework line starting with 'Core CS Coursework: ' strictly MAX 180 characters, keeping exact grades."
    )
    military_bullets: list[str] = Field(
        description="3 sharpened military leadership bullets, each strictly MAX 135 characters."
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


def tailor_academic_projects(
    projects: list[dict[str, str]],
    job_description: str,
    profile: Optional[dict] = None,
    client: Optional[genai.Client] = None,
) -> list[TailoredProject]:
    """
    Tailors academic project tags and descriptions to align with the target job description.
    Preserves all facts, original project names, and architectures.
    """
    client = client or get_client()

    prompt = f"""
Tailor the technology tags and descriptions for the following academic projects to highlight relevance to the target job description.

Original Projects:
{json.dumps(projects, indent=2, ensure_ascii=False)}

Target Job Description:
{job_description}

Rules:
- Keep the exact project names and factual core of what was built.
- In 'title_suffix', emphasize relevant tools and concepts that match the JD (e.g. ' | Java, C++, Reactor Pattern, Network Sockets'). ALWAYS start with ' | '.
- In 'description', emphasize relevant architectural patterns, protocols, concurrency, or performance metrics that legitimately match the work.
- DO NOT invent technologies or features not present in the original projects.
"""

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=TailoredProjects,
        temperature=0.2,
    )

    response = _generate_with_fallback(client, prompt, config)
    parsed = TailoredProjects.model_validate_json(response.text)
    return parsed.projects


def tailor_full_resume(
    profile: dict,
    job_description: str,
    original_data: dict[str, Any],
    client: Optional[genai.Client] = None,
) -> FullTailoredResume:
    """
    Executes a comprehensive, full-resume tailoring across all sections:
    - Fit & Pitch Analysis
    - Experience Bullets (Verifone)
    - Academic Projects (STOMP Server, Linear Algebra Engine, DJ Station)
    - Programming Language Pills Priority Ordering
    - Tools & Platforms Reordering
    - Core Concepts Reordering
    - Relevant Coursework Prioritization
    - Military Leadership Framing
    """
    client = client or get_client()

    prompt = f"""
You are an elite technical resume strategist tailoring the candidate for this specific Job Description.

Candidate Profile & Ground Truth:
{json.dumps(profile, indent=2, ensure_ascii=False)}

Current Resume Content To Tailor:
{json.dumps(original_data, indent=2, ensure_ascii=False)}

Target Job Description:
{job_description}

SUBSTANTIVE TAILORING MANDATE:
Do NOT merely return the original text with 1-2 words swapped.
Actively rewrite, elevate, and align every bullet point and description so the candidate stands out as a stellar match:
1. Experience (Verifone):
   - Reframe technical support and supervision into high-impact systems engineering, R&D troubleshooting, infrastructure automation, and software reliability.
   - Lead with the most impressive, technically relevant achievements.
   - Preserve exact metrics (e.g. turnaround from 40 min to <1 min).
2. Academic Projects:
   - STOMP Server: Emphasize network sockets, Reactor pattern, thread-pool concurrency, and packet protocols.
   - Linear Algebra Engine: Emphasize multithreading, thread safety, synchronization, and CPU optimization.
   - DJ Station Audio Processor: Emphasize C++, manual memory management, and OOP/SOLID design.
3. Languages & Tools:
   - In 'ordered_languages', put the top languages required by the JD first (e.g. Python, C++, SQL).
   - In 'tools_lines', put required developer tools/environments (e.g. Docker, Git, Linux, Bash, WSL, macOS, VS Code, Claude, ChatGPT, AntiGravity). NEVER put programming languages here.
   - In 'core_concepts_lines', put required concepts (e.g. Multithreading, Concurrency, Sockets, Memory Management, OOP, SOLID Principles).
4. Coursework:
   - Order Systems Programming, Operating Systems, Computer Architecture (91), Data Structures, Algorithms first.
5. Military:
   - Frame squad leadership, founding the special mobility unit, and high-stakes operational execution.

CRITICAL CANVA LAYOUT BUDGET CONSTRAINTS:
The resume is a single-page fixed Canva design. Any text overflow will collide with other sections.
You MUST strictly obey these exact limits:
1. Academic Projects (3 items):
   - title_suffix: MAX 45 characters (e.g. ' | Java, C++, Sockets, Reactor'). Must start with ' | '.
   - description: Strictly MAX 140 characters (fits in 2 lines).
2. Experience Bullets (6 items):
   - Each bullet strictly MAX 135 characters (fits in 2 lines).
3. Tools & Platforms (4 lines):
   - Exactly 4 lines, each line strictly MAX 25 characters.
4. Core Concepts (2 lines):
   - Exactly 2 lines, line 1 MAX 35 characters, line 2 MAX 30 characters.
5. Coursework (1 line):
   - Starts with 'Core CS Coursework: ' and strictly MAX 180 characters.
6. Military Bullets (3 items):
   - Each bullet strictly MAX 135 characters.

STRICT CONTENT GUARDRAILS:
1. ZERO FABRICATION: Only surface skills, tools, and experiences the candidate actually has. Do NOT invent technologies or credentials.
2. PRESERVE METRICS: Keep all numbers, grades, metrics exactly as stated.
"""

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=FullTailoredResume,
        temperature=0.35,
    )

    response = _generate_with_fallback(client, prompt, config)
    return FullTailoredResume.model_validate_json(response.text)
