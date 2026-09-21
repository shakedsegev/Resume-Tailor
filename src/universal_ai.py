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
    profile: Optional[dict] = None,
    client: Optional[genai.Client] = None,
) -> UniversalTailoredOutput:
    """
    Performs substantive, ATS-optimized tailoring on any UniversalResume against a target JD.
    If a CandidateProfile is provided, actively enriches the resume with verified skills,
    detailed accomplishments, unlisted projects, and exact metrics from the Master Profile.
    Returns both the tailored resume structure and the comprehensive FitAnalysis.
    """
    client = client or get_client()

    profile_context = ""
    if profile:
        profile_context = f"""
Candidate Master Profile & Ground Truth (Verified Extended Background & Newer Experience):
{json.dumps(profile, indent=2, ensure_ascii=False)}
"""

    prompt = f"""
You are an elite technical resume strategist and ATS optimization expert.
Tailor the candidate's resume for the target Job Description to achieve the HIGHEST POSSIBLE ATS MATCH while maintaining 100% factual truth.

Original Candidate Resume (May be older or less detailed):
{resume.model_dump_json(indent=2)}
{profile_context}

Target Job Description:
{job_description}

CRITICAL GROUND-TRUTH ENRICHMENT & ATS MAXIMIZATION MANDATE:
The candidate's primary goal is to pass ATS screens and stand out to technical hiring managers.
When a Candidate Master Profile is provided, actively synthesize and enrich the resume using verified facts from both sources:

1. PROGRAMMING LANGUAGES & TECHNICAL SKILLS (ACTIVE EXPANSION):
   - Cross-reference the Master Profile. If the candidate possesses programming languages, developer tools, frameworks, or engineering concepts in their Master Profile that are required, preferred, or valuable for this target Job Description, YOU MUST ADD THEM into 'programming_languages', 'frameworks_and_tools', or 'core_concepts'!
   - Do not restrict yourself to only the skills on the old resume if the candidate legitimately possesses them in their Master Profile.
   - Reorder skills so that the top languages and technologies explicitly demanded by the JD appear first in each category.

2. WORK EXPERIENCE ENRICHMENT:
   - Actively cross-reference each experience role with the Master Profile.
   - If the Master Profile provides more detailed accomplishment bullets, technical depth (architectural patterns, protocols, concurrency, debugging), or verified performance metrics (e.g. speedups, automated queries, downtime reduction, awards), ENRICH and ELEVATE the experience bullets to reflect these verified achievements!
   - Rewrite bullets to lead with high-impact engineering verbs and mirror ATS keywords from the JD.
   - PRESERVE all factual numbers, turnaround times, dates, and metrics exactly.

3. ACADEMIC & SIDE PROJECTS:
   - Cross-reference projects with the Master Profile.
   - Update technology tags and descriptions to highlight architectural patterns, networking, concurrency, or algorithms verified in the profile that align with the role.
   - If the Master Profile contains a highly relevant verified project not listed on the old resume, include or adapt it to maximize role fit.

4. PROFESSIONAL SUMMARY & EDUCATION:
   - Align summary (if present) to target role, weaving together the candidate's strongest combined strengths from the resume and profile.
   - Prioritize verified relevant coursework and retain exact grades/GPAs.

5. ZERO FABRICATION (STRICT FACTUAL INTEGRITY):
   - ZERO HALLUCINATIONS: Every technology, tool, company, degree, metric, and achievement MUST be grounded in either the Original Resume OR the Master Profile.
   - Never invent credentials or experiences the candidate does not have.

6. CHANGES LOG & RATIONALE:
   - For every skill added from the profile, modified bullet, enriched project, or reordered technology, create a ChangeAnnotation in 'changes_log'.
   - In 'original_text', specify what was there originally (or 'Added from Master Profile' if newly incorporated).
   - In 'tailored_text', specify the new text.
   - In 'rationale', explain why it was added or rewritten and which JD keyword or profile achievement it aligns with.
"""

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=UniversalTailoredOutput,
        temperature=0.3,
    )

    response = _generate_with_fallback(client, prompt, config)
    return UniversalTailoredOutput.model_validate_json(response.text)
