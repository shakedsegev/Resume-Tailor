"""
Universal AI Tailoring Engine.
Parses arbitrary raw resume text into standardized schema and tailors it
against any target Job Description with Gemini AI.
"""

import json
from typing import Optional
from google import genai
from google.genai import types
from src.ai_engine import get_client, _generate_with_fallback, SYSTEM_INSTRUCTION
from src.universal_models import UniversalResume, UniversalTailoredOutput, FitAnalysis


def parse_raw_resume_to_schema(
    raw_text: str, client: Optional[genai.Client] = None
) -> UniversalResume:
    """
    Parses unformatted raw text extracted from any resume (PDF, DOCX, PPTX)
    into a structured UniversalResume data model.
    """
    client = client or get_client()

    prompt = f"""
Extract and structure all content from the following raw resume text into the exact UniversalResume schema.

Raw Resume Text:
{raw_text}

Rules:
1. Accurately extract full contact information: candidate's full name, email, phone, location, LinkedIn link/handle, and GitHub link/handle.
2. Extract all technical skills and divide them into:
   - programming_languages (e.g., Python, C++, Java, TypeScript, SQL, C, x86 Assembly)
   - frameworks_and_tools (e.g., Docker, Git, Linux, Bash, WSL, macOS, VS Code)
   - core_concepts (e.g., Multithreading, Concurrency, OOP, Sockets, Memory Management, SOLID)
3. Extract all work experience with company, role/title, dates, and full bullet points.
4. Extract all projects with project name, tech stack tags, and descriptions.
5. Extract education: institution, degree, GPA, and coursework.
6. Extract any military service, sports achievements, volunteering, or leadership into additional_sections.
7. Preserve all original numbers, metrics, turnaround times, dates, and grades exactly as stated.
"""

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=UniversalResume,
        temperature=0.1,
    )

    response = _generate_with_fallback(client, prompt, config)
    return UniversalResume.model_validate_json(response.text)


def tailor_universal_resume(
    resume: UniversalResume,
    job_description: str,
    client: Optional[genai.Client] = None,
) -> UniversalTailoredOutput:
    """
    Performs substantive, ATS-optimized tailoring on any UniversalResume against a target JD.
    Returns both the tailored resume structure and the comprehensive FitAnalysis.
    """
    client = client or get_client()

    prompt = f"""
You are an elite technical resume strategist and ATS optimization expert.
Tailor the candidate's resume for the target Job Description while maintaining 100% factual truth.

Original Candidate Resume:
{resume.model_dump_json(indent=2)}

Target Job Description:
{job_description}

SUBSTANTIVE TAILORING MANDATE:
1. FIT ANALYSIS:
   - Calculate match_score (0-100%) based on required skills & qualifications.
   - List strong matches, partial matches / transferable skills, and honest gaps.
   - Formulate a 1-2 sentence high-impact strategic pitch angle.
2. EXPERIENCE BULLETS:
   - Actively rewrite and sharpen bullet points to highlight skills, tools, and paradigms matching the JD.
   - Lead with the most technically relevant bullets.
   - Emphasize business impact and engineering depth.
   - PRESERVE all factual metrics (numbers, turnaround times, team sizes) without alteration.
3. ACADEMIC & SIDE PROJECTS:
   - Align technology tags and descriptions to emphasize architectural patterns, networking, concurrency, or algorithms relevant to the role.
4. SKILLS PRIORITIZATION:
   - In programming_languages, frameworks_and_tools, and core_concepts, reorder items so that those mentioned or valued in the JD appear first.
5. SUMMARY & EDUCATION:
   - Align summary (if present) to target role.
   - Prioritize relevant coursework and retain exact grades.
6. CHANGES LOG & RATIONALE:
   - For every modified bullet, project tag, skill ordering, or coursework line, create a ChangeAnnotation in 'changes_log'.
   - Detail what the original phrasing was, the new tailored text, and a clear explanation of why it was changed and which JD keyword or profile achievement was elevated.
7. HARD GUARDRAILS:
   - ZERO FABRICATION: Never invent companies, tools, dates, credentials, or technologies the candidate does not have.
   - METRIC PRESERVATION: Never alter or inflate numbers.
"""

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=UniversalTailoredOutput,
        temperature=0.3,
    )

    response = _generate_with_fallback(client, prompt, config)
    return UniversalTailoredOutput.model_validate_json(response.text)
