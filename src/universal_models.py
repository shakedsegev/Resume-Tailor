"""
Universal Resume Data Models.
Standardized representation of any technical or professional resume.
"""

from pydantic import BaseModel, Field


class ContactInfo(BaseModel):
    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""


class ExperienceItem(BaseModel):
    role: str
    company: str
    location: str = ""
    date_range: str = ""
    bullets: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: str
    technologies: str = ""
    description: str = ""
    bullets: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    degree: str
    institution: str
    date_range: str = ""
    gpa: str = ""
    details: str = ""


class SkillCategories(BaseModel):
    programming_languages: list[str] = Field(default_factory=list)
    frameworks_and_tools: list[str] = Field(default_factory=list)
    core_concepts: list[str] = Field(default_factory=list)
    spoken_languages: list[str] = Field(
        default_factory=list,
        description="Spoken/natural languages with proficiency as stated by the candidate (e.g. 'Spanish (Fluent)', 'German (Native)', 'French (Professional)'). Empty if none listed.",
    )


class AdditionalSection(BaseModel):
    title: str
    items: list[str] = Field(default_factory=list)


class UniversalResume(BaseModel):
    contact: ContactInfo
    summary: str = ""
    skills: SkillCategories
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    additional_sections: list[AdditionalSection] = Field(default_factory=list)


class FitAnalysis(BaseModel):
    match_score: int = Field(
        default=85,
        description="Estimated match percentage between 0 and 100 based on core requirements.",
    )
    match: list[str] = Field(
        description="Requirements the candidate strongly covers."
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


class ChangeAnnotation(BaseModel):
    section: str = Field(description="Section name (e.g. Experience, Projects, Skills, Coursework)")
    original_text: str = Field(description="Original phrasing or content from the source resume")
    tailored_text: str = Field(description="New tailored phrasing incorporating target keywords")
    rationale: str = Field(description="Clear explanation of why this change was made, what was changed from what, and which JD keyword was highlighted")


class UniversalTailoredOutput(BaseModel):
    fit_analysis: FitAnalysis
    tailored_resume: UniversalResume
    changes_log: list[ChangeAnnotation] = Field(default_factory=list)


def clean_gpa_val(val: str) -> str:
    """Normalizes GPA string to prevent duplicate 'GPA: GPA' prefixes."""
    if not val:
        return ""
    import re
    cleaned = val.strip()
    m = re.search(
        r"(?:first[- ]year\s+)?(?:gpa|grade|average)\s*(?:of|[:=–—\-])?\s*([0-9\.]+(?:\s*/\s*[0-9\.]+)?(?:\s*%)?)",
        cleaned,
        re.IGNORECASE,
    )
    if m:
        grade = m.group(1)
        if "first" in cleaned.lower():
            return f"First Year: {grade}"
        return grade
    cleaned = re.sub(
        r"^(?:GPA|Grade|Average)\s*[:=–—\-]?\s*", "", cleaned, flags=re.IGNORECASE
    ).strip()
    return cleaned


def clean_summary_gpa(summary: str) -> str:
    """Exacting regex purge of GPA/grades from Professional Summary."""
    if not summary:
        return ""
    import re
    s = summary
    # 'with a first-year GPA of 92 and strong' -> 'with strong'
    s = re.sub(
        r"\bwith\s+(?:a\s+)?(?:first[- ]year\s+)?(?:gpa|grade average)\s*(?:of|[:=–—\-])?\s*[0-9\.]+(?:\s*%)?\s+and\s+",
        "with ",
        s,
        flags=re.IGNORECASE,
    )
    # ', with a GPA of 92,' -> ','
    s = re.sub(
        r",\s*(?:with\s+)?(?:a\s+)?(?:first[- ]year\s+)?(?:gpa|grade average)\s*(?:of|[:=–—\-])?\s*[0-9\.]+(?:\s*%)?\s*,",
        ",",
        s,
        flags=re.IGNORECASE,
    )
    # Standalone clauses
    s = re.sub(
        r"\b(?:with\s+)?(?:a\s+)?(?:first[- ]year\s+)?(?:gpa|grade average)\s*(?:of|[:=–—\-])?\s*[0-9\.]+(?:\s*%)?\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\bGPA\s*(?:of|[:=–—\-])?\s*[0-9\.]+\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\(\s*\)", "", s)
    s = re.sub(r"\s*,\s*,+", ",", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,\.\?!])", r"\1", s)
    s = re.sub(r",\s*\.", ".", s)
    return s


def normalize_section_title(title: str) -> str:
    """
    Normalizes any section title by trimming whitespace, trailing colons/dashes,
    and standardizing casing (e.g. 'LANGUAGES:' -> 'Languages', 'WORK EXPERIENCE' -> 'Work Experience').
    Ensures identical or equivalent headers are recognized as the same section for any candidate.
    """
    if not title:
        return ""
    import re
    cleaned = re.sub(r"[:\-–—\.]+$", "", title.strip()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned.isupper():
        cleaned = cleaned.title()
    return cleaned


def sanitize_universal_resume(resume: UniversalResume) -> UniversalResume:
    """
    Universal, candidate-agnostic resume sanitizer:
    1. Isolates GPA strictly to Education; purges numerical grades/GPA from Summary.
    2. Cleans GPA string so redundant 'GPA: GPA' prefixes never render.
    3. Groups all items sharing the same header together into ONE section,
       guaranteeing no duplicate headers across the document for any candidate.
    4. Absorbs any 'Languages' from additional_sections into skills.spoken_languages.
    5. Deduplicates identical bullets within sections.
    """
    import re
    from difflib import SequenceMatcher

    # 1. Clean Summary GPA (purely numerical/GPA patterns, candidate-agnostic)
    if resume.summary:
        resume.summary = clean_summary_gpa(resume.summary)

    # 2. Clean Education GPA and remove duplicate GPA from details
    for edu in resume.education:
        if edu.gpa:
            edu.gpa = clean_gpa_val(edu.gpa)
        if edu.details and edu.gpa:
            gpa_num_m = re.search(r"[0-9]+(?:\.[0-9]+)?", edu.gpa)
            if gpa_num_m:
                edu.details = re.sub(
                    r"\s*\|\s*GPA\s*[:=–—\-]?\s*" + re.escape(gpa_num_m.group(0)) + r"\b",
                    "",
                    edu.details,
                    flags=re.IGNORECASE,
                )
                edu.details = re.sub(
                    r"\bGPA\s*[:=–—\-]?\s*" + re.escape(gpa_num_m.group(0)) + r"\b",
                    "",
                    edu.details,
                    flags=re.IGNORECASE,
                )
            edu.details = re.sub(
                r"\bGPA\s*[:=–—\-]?\s*" + re.escape(edu.gpa) + r"\b",
                "",
                edu.details,
                flags=re.IGNORECASE,
            )
            edu.details = re.sub(r"\|\s*\|+", "|", edu.details).strip(" |")

    # 3. Check additional_sections against spoken languages
    kept_sections: list[AdditionalSection] = []
    for sec in resume.additional_sections:
        sec_title_lower = sec.title.strip().lower()

        # If it's a natural/spoken languages section, absorb into spoken_languages
        if any(sec_title_lower == k or sec_title_lower.startswith(k) for k in [
            "language", "languages", "spoken language", "spoken languages",
            "natural language", "natural languages", "language skills", "foreign languages"
        ]):
            for item in sec.items:
                clean_it = item.strip()
                if clean_it and clean_it not in resume.skills.spoken_languages:
                    resume.skills.spoken_languages.append(clean_it)
            continue

        kept_sections.append(sec)

    # 4. Group all items with the same header together under ONE section
    merged_sections: dict[str, list[str]] = {}
    title_display_map: dict[str, str] = {}

    for sec in kept_sections:
        norm = normalize_section_title(sec.title)
        key = norm.lower()
        if not key:
            continue

        if key not in merged_sections:
            merged_sections[key] = []
            title_display_map[key] = norm

        for it in sec.items:
            clean_it = it.strip()
            if not clean_it:
                continue
            is_dup = False
            for existing in merged_sections[key]:
                if clean_it.lower() == existing.lower() or SequenceMatcher(None, clean_it.lower(), existing.lower()).ratio() >= 0.90:
                    is_dup = True
                    break
            if not is_dup:
                merged_sections[key].append(clean_it)

    # 5. Rebuild additional_sections: each unique header appears exactly once
    resume.additional_sections = [
        AdditionalSection(title=title_display_map[key], items=items)
        for key, items in merged_sections.items()
        if items
    ]

    return resume

