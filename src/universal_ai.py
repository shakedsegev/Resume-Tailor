"""
Universal AI Tailoring Engine.
Parses arbitrary raw resume text into standardized schema and tailors it
against any target Job Description with Gemini AI.
"""

import json
from typing import Optional
from google import genai
from google.genai import types
# pyrefly: ignore [missing-import]
from src.ai_engine import get_client, _generate_with_fallback, SYSTEM_INSTRUCTION
# pyrefly: ignore [missing-import]
from src.universal_models import (
    UniversalResume,
    UniversalTailoredOutput,
    FitAnalysis,
    sanitize_universal_resume,
    restore_course_grades,
    compute_multi_metric_fit,
)


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
2. Extract all skills and divide them into:
   - programming_languages (e.g., Python, C++, Java, TypeScript, SQL, C, x86 Assembly)
   - frameworks_and_tools (e.g., Docker, Git, Linux, Bash, WSL, macOS)
   - core_concepts (e.g., Multithreading, Concurrency, OOP, Sockets, Memory Management, SOLID)
   - spoken_languages: Extract any natural/spoken languages and proficiency levels explicitly stated in the document (e.g. Spanish, French, German, Mandarin, English, Arabic, etc.). If none are listed by the candidate, return an empty list. NEVER invent or assume languages!
3. Extract all work experience with company, role/title, dates, and full bullet points.
4. Extract all projects with project name, tech stack tags, descriptions, and bullets.
5. Extract education: institution, degree, GPA, and coursework.
6. Extract all leadership, military service, sports excellence, and volunteering & mentorship into additional_sections. NEVER drop verified sections.
7. Preserve all original numbers, metrics, turnaround times, dates, and grades exactly as stated.
"""

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=UniversalResume,
        temperature=0.0,
    )

    response = _generate_with_fallback(
        client, prompt, config, preferred_model="gemini-3.5-flash-lite"
    )
    parsed = UniversalResume.model_validate_json(response.text)
    return sanitize_universal_resume(parsed)


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

1. PROGRAMMING LANGUAGES, TOOLS & SPOKEN LANGUAGES:
   - In 'programming_languages', cross-reference the Master Profile. Add any verified languages that are required or preferred by the JD, prioritizing the top languages required by the JD first.
   - In 'frameworks_and_tools' and 'core_concepts', prioritize technologies matching the JD.
   - SPOKEN LANGUAGES: If the candidate lists spoken languages in their resume or profile, preserve them exactly with their proficiency levels. If the candidate does not list spoken languages, leave 'spoken_languages' empty. NEVER invent, fabricate, or assume any languages!

2. WORK EXPERIENCE ENRICHMENT:
   - Actively cross-reference each experience role with the Master Profile.
   - If the Master Profile provides more detailed accomplishment bullets, technical depth (architectural patterns, protocols, concurrency, debugging), or verified performance metrics (e.g. turnaround speedups, automated queries, downtime reduction, awards), ENRICH and ELEVATE the experience bullets to reflect these verified achievements!
   - Rewrite bullets to lead with high-impact engineering verbs and mirror ATS keywords from the JD.
   - PRESERVE all factual numbers, turnaround times, dates, and metrics exactly.

3. ACADEMIC & SIDE PROJECTS (NON-REDUNDANT ARCHITECTURE):
   - In each project, provide a concise 1-sentence 'description' summarizing the overall architecture.
   - In 'bullets', provide 1-2 distinct engineering accomplishment bullets detailing specific implementation challenges, concurrency, performance benchmarks, or protocols.
   - STRICT ANTI-REDUNDANCY: Bullets MUST NOT duplicate or rephrase the description! Each bullet must provide new, unique technical information.

4. PROFESSIONAL SUMMARY & EDUCATION (STRICT GPA ISOLATION & COURSE GRADE PRESERVATION):
   - Align summary to the target role, highlighting technical identity, systems programming focus, and engineering impact.
   - NEVER repeat GPA or numerical grades in the Professional Summary! GPA belongs exclusively in the Education section. Mentioning GPA twice appears repetitive and self-conscious to recruiters.
   - In Education: retain exact institution, degree, date range. In 'education[0].gpa', provide ONLY the numerical score or concise grade (e.g. '83.5', '92', '3.85'). Do NOT include 'GPA:' prefix in this field. Prioritize the top 5-6 coursework subjects most relevant to the JD.
   - PRESERVE INDIVIDUAL COURSE GRADES: If the candidate lists individual course grades/scores (e.g. 'Computer Architecture (91)', 'Systems Programming (95)', 'Introduction to CS: 96'), ALWAYS preserve those specific grades attached to their respective courses when selecting or reordering coursework. Never strip course grades!

5. MANDATORY SECTION GROUPING & ZERO DUPLICATE HEADERS:
   - Every domain, category, or topic MUST be grouped together under ONE SINGLE HEADER. Never output two sections with the same or similar headers.
   - All items that belong to the same category (e.g. all certifications, all publications, all awards, all leadership, or all community work) must be grouped together under a single unified section header.
   - SPOKEN LANGUAGES: Place all natural/spoken languages exclusively in 'skills.spoken_languages'. NEVER create a separate additional_section titled 'Languages' or 'Spoken Languages'.
   - If a role or accomplishment is already described under 'experience', never duplicate or repeat that same role as an entry under 'additional_sections'.

6. STRICT ZERO DUPLICATION & INTENTIONAL OMISSION:
   - ZERO DUPLICATION: No sentence, metric, or bullet point may appear in more than one section of the resume. Every line must deliver unique value.
   - INTENTIONAL OMISSION: If trimming is needed for density, prune secondary administrative tasks, minor routine duties, or low-priority coursework. Never omit primary technical accomplishments, core projects, or spoken languages.

7. ZERO FABRICATION (STRICT FACTUAL INTEGRITY):
   - ZERO HALLUCINATIONS: Every technology, tool, company, degree, metric, and achievement MUST be grounded in either the Original Resume OR the Master Profile.
   - Never invent credentials or experiences the candidate does not have.

8. CHANGES LOG & RATIONALE:
   - For every skill added from the profile, modified bullet, enriched project, or reordered technology, create a ChangeAnnotation in 'changes_log'.
   - In 'original_text', specify what was there originally (or 'Added from Master Profile' if newly incorporated).
   - In 'tailored_text', specify the new text.
   - In 'rationale', explain why it was added or rewritten and which JD keyword or profile achievement it aligns with.

9. PROACTIVE OPTIMIZATION & ZERO-LAZINESS MANDATE:
   - Aim for the ABSOLUTE BEST possible tailored resume for this target JD.
   - For every single bullet, actively evaluate: "How can this bullet be rewritten to showcase maximum candidate strength for this JD while staying 100% true to verified facts?"
   - In FitAnalysis: Systematically categorize matches based on JD priority (core must-have qualifications in 'match', adjacent skills in 'partial', missing requirements in 'gap').
"""

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=UniversalTailoredOutput,
        temperature=0.05,
    )

    response = _generate_with_fallback(client, prompt, config)
    output = UniversalTailoredOutput.model_validate_json(response.text)

    # Programmatically guarantee course grades from original resume or profile are never lost
    for idx, edu in enumerate(output.tailored_resume.education):
        orig_details = ""
        if resume.education and idx < len(resume.education):
            orig_details = resume.education[idx].details
        if not orig_details and profile and "education" in profile:
            prof_edu = profile["education"]
            if isinstance(prof_edu, list) and idx < len(prof_edu):
                orig_details = prof_edu[idx].get("coursework", "") or prof_edu[idx].get("details", "")
        if orig_details:
            edu.details = restore_course_grades(edu.details, orig_details)

    output.tailored_resume = sanitize_universal_resume(output.tailored_resume)

    # Deterministically calculate 360° multi-metric job fit
    tailored_text_corpus = (
        (output.tailored_resume.summary or "") + " " +
        " ".join(output.tailored_resume.skills.programming_languages) + " " +
        " ".join(output.tailored_resume.skills.frameworks_and_tools) + " " +
        " ".join(output.tailored_resume.skills.core_concepts) + " " +
        " ".join(output.tailored_resume.skills.spoken_languages) + " " +
        " ".join(b for exp in output.tailored_resume.experience for b in exp.bullets) + " " +
        " ".join((p.description or "") + " " + " ".join(p.bullets) + " " + (p.technologies or "") for p in output.tailored_resume.projects) + " " +
        " ".join((edu.details or "") for edu in output.tailored_resume.education)
    )
    output.fit_analysis = compute_multi_metric_fit(
        output.fit_analysis,
        resume_text=tailored_text_corpus,
        jd_text=job_description,
    )
    return output
