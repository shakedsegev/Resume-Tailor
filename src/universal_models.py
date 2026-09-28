"""
Universal Resume Data Models.
Standardized representation of any technical or professional resume.
"""

import re
from typing import Any
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


def is_generic_social_url(url: str) -> bool:
    """
    Returns True if the URL points to a generic website homepage rather than a candidate's personal profile.
    e.g. 'https://github.com', 'https://linkedin.com', 'https://linkedin.com/in/LinkedIn', 'https://github.com/GitHub'
    """
    if not url:
        return True
    clean = url.strip().rstrip("/").lower()
    clean = re.sub(r"^https?://", "", clean)
    clean = re.sub(r"^www\.", "", clean)

    # Generic LinkedIn targets
    if clean in {
        "linkedin.com",
        "linkedin.com/in",
        "linkedin.com/in/linkedin",
        "linkedin.com/in/in",
        "linkedin.com/company",
        "linkedin.com/feed",
        "linkedin",
    }:
        return True
    if clean.startswith("linkedin.com") and len(clean.split("/")) <= 2 and clean.split("/")[-1] in {"", "in", "feed", "jobs", "home"}:
        return True

    # Generic GitHub targets
    if clean in {
        "github.com",
        "github.com/github",
        "github.com/home",
        "github.com/login",
        "github",
    }:
        return True

    return False


def normalize_url(url: str, default_domain: str = "") -> str:
    """Ensures URLs are well-formed absolute https:// links for active clickable PDF hyperlinks."""
    if not url:
        return ""
    clean = url.strip()
    if clean.startswith("http://") or clean.startswith("https://"):
        return clean
    if clean.startswith("www."):
        return f"https://{clean}"
    if "linkedin.com" in clean.lower():
        clean = re.sub(r"^(?:https?://)?(?:www\.)?", "", clean, flags=re.IGNORECASE)
        return f"https://www.{clean}"
    if "github.com" in clean.lower():
        clean = re.sub(r"^(?:https?://)?(?:www\.)?", "", clean, flags=re.IGNORECASE)
        return f"https://{clean}"
    if default_domain:
        return f"https://{default_domain.rstrip('/')}/{clean.lstrip('/')}"
    return f"https://{clean}"


def format_social_display(url: str, network: str = "") -> str:
    """
    Formats a full profile URL into a clean display string for PDF & HTML rendering.
    e.g. 'https://www.linkedin.com/in/shaked-segev-424178298/' -> 'LinkedIn'
         'https://github.com/shakedsegev' -> 'GitHub'
    """
    if not url:
        return ""
    if network:
        # Standardize capitalization: e.g. 'LinkedIn', 'GitHub'
        low = network.lower()
        if low == "linkedin":
            return "LinkedIn"
        if low == "github":
            return "GitHub"
        return network.capitalize()
    clean = url.strip().rstrip("/")
    clean = re.sub(r"^https?://", "", clean)
    clean = re.sub(r"^www\.", "", clean)
    return clean


def extract_social_links(text: str) -> dict[str, str]:
    """Extracts LinkedIn and GitHub URLs from raw text or profile notes."""
    links: dict[str, str] = {}
    if not text:
        return links
    m_li = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_\-\.%]+/?", text, re.IGNORECASE)
    if m_li:
        cand = normalize_url(m_li.group(0), "linkedin.com/in")
        if not is_generic_social_url(cand):
            links["linkedin"] = cand
    m_gh = re.search(r"(?:https?://)?(?:www\.)?github\.com/[a-zA-Z0-9_\-\.%]+/?", text, re.IGNORECASE)
    if m_gh:
        cand = normalize_url(m_gh.group(0), "github.com")
        if not is_generic_social_url(cand):
            links["github"] = cand
    return links


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


class KeywordStats(BaseModel):
    found_count: int = 0
    total_count: int = 0
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)

    def __getitem__(self, item: str):
        return getattr(self, item)

    def get(self, item: str, default=None):
        return getattr(self, item, default)


class FitAnalysis(BaseModel):
    match_score: int = Field(
        default=85,
        description="Overall composite ATS readiness score between 0 and 100.",
    )
    keyword_score: int = Field(
        default=85,
        description="Deterministic keyword & technical skills match percentage (0-100).",
    )
    requirements_score: int = Field(
        default=85,
        description="Core qualifications & requirements coverage percentage (0-100).",
    )
    experience_score: int = Field(
        default=85,
        description="Experience & impact alignment percentage (0-100).",
    )
    keyword_stats: KeywordStats = Field(
        default_factory=KeywordStats,
        description="Stats on keywords: found_count, total_count, matched_keywords, missing_keywords",
    )
    match: list[str] = Field(
        default_factory=list,
        description="Requirements the candidate strongly covers.",
    )
    partial: list[str] = Field(
        default_factory=list,
        description="Requirements touched lightly or covered with transferable skills.",
    )
    gap: list[str] = Field(
        default_factory=list,
        description="Requirements the candidate lacks (must not be fabricated).",
    )
    pitch_angle: str = Field(
        default="",
        description="1-2 sentences on how best to position the candidate for this specific role.",
    )


COMMON_TECH_KEYWORDS = [
    # Languages
    "python", "c++", "java", "c#", "golang", "go", "rust", "javascript", "typescript", "c", "assembly",
    "ruby", "php", "swift", "kotlin", "scala", "sql", "html", "css", "bash", "shell", "r",
    # Frameworks & Libraries
    "react", "angular", "vue", "node.js", "nodejs", "express", "django", "flask", "fastapi",
    "spring", "spring boot", "next.js", "nextjs", ".net", "dotnet", "pytorch", "tensorflow",
    # Tools & Platforms
    "docker", "kubernetes", "k8s", "aws", "gcp", "azure", "git", "github", "gitlab", "linux",
    "unix", "wsl", "macos", "ci/cd", "terraform", "ansible", "jenkins", "jira", "kafka",
    "rabbitmq", "redis", "mongodb", "postgresql", "postgres", "mysql", "sqlite", "graphql", "rest", "api",
    # Concepts
    "multithreading", "concurrency", "sockets", "tcp/ip", "tcp", "networking", "microservices",
    "distributed systems", "oop", "object-oriented", "data structures", "algorithms",
    "solid principles", "design patterns", "reactor pattern", "unit testing", "tdd",
    "memory management", "performance optimization", "low-level", "cloud", "agile", "scrum"
]


def _keyword_regex(kw: str) -> str:
    """Builds a precise regex pattern respecting symbols in C++, C#, .NET, etc."""
    if kw == "c":
        return r"(?<![a-zA-Z0-9_#+])c(?![a-zA-Z0-9_#+])"
    elif kw.startswith("."):
        return r"(?<![a-zA-Z0-9])" + re.escape(kw) + r"(?![a-zA-Z0-9])"
    else:
        return r"(?<![a-zA-Z0-9_])" + re.escape(kw) + r"(?![a-zA-Z0-9_])"


def extract_jd_keywords(jd_text: str) -> list[str]:
    """Extracts relevant technical keywords and tools explicitly mentioned in the Job Description."""
    jd_lower = jd_text.lower()
    found = []
    for kw in COMMON_TECH_KEYWORDS:
        pattern = _keyword_regex(kw)
        if re.search(pattern, jd_lower):
            found.append(kw)
    return found


def compute_multi_metric_fit(
    fit: FitAnalysis, resume_text: str, jd_text: str
) -> FitAnalysis:
    """
    Computes dependable, mathematically grounded multi-metric scores:
    1. Keyword & Skills Match %: Exact ratio of JD tech keywords present in resume.
    2. Qualifications & Requirements %: Formula based on verified Strong vs Partial vs Gap lists.
    3. Experience & Impact Alignment %: Verified engineering depth and accomplishment alignment.
    4. Composite Overall ATS Readiness %: Weighted blend (40% Keywords + 35% Qualifications + 25% Experience).
    """
    resume_lower = resume_text.lower()
    jd_keywords = extract_jd_keywords(jd_text)

    matched_kw = []
    missing_kw = []
    for kw in jd_keywords:
        pattern = _keyword_regex(kw)
        if re.search(pattern, resume_lower):
            matched_kw.append(kw)
        else:
            missing_kw.append(kw)

    if jd_keywords:
        keyword_score = round((len(matched_kw) / len(jd_keywords)) * 100)
    else:
        keyword_score = fit.keyword_score if fit.keyword_score else 88

    # Requirements Coverage:
    strong_len = len(fit.match)
    partial_len = len(fit.partial)
    gap_len = len(fit.gap)
    total_reqs = strong_len + partial_len + gap_len

    req_curr = getattr(fit, "requirements_score", None)
    if total_reqs > 0:
        req_score = round(((strong_len * 1.0 + partial_len * 0.5) / total_reqs) * 100)
    else:
        req_score = req_curr if req_curr else 85

    # Experience Alignment:
    exp_curr = getattr(fit, "experience_score", None)
    raw_exp = exp_curr if (exp_curr and exp_curr > 0) else (
        round(min(96, max(60, (strong_len / max(1, strong_len + gap_len)) * 100)))
    )
    exp_score = max(50, min(98, raw_exp))

    # Composite Overall ATS Readiness Score:
    composite = round(0.40 * keyword_score + 0.35 * req_score + 0.25 * exp_score)
    composite = max(40, min(99, composite))

    setattr(fit, "keyword_score", max(0, min(100, keyword_score)))
    setattr(fit, "requirements_score", max(0, min(100, req_score)))
    setattr(fit, "experience_score", max(0, min(100, exp_score)))
    setattr(fit, "match_score", composite)
    setattr(fit, "keyword_stats", KeywordStats(
        found_count=len(matched_kw),
        total_count=len(jd_keywords),
        matched_keywords=matched_kw,
        missing_keywords=missing_kw,
    ))
    return fit


class ChangeAnnotation(BaseModel):
    section: str = Field(description="Section name (e.g. Experience, Projects, Skills, Coursework)")
    original_text: str = Field(description="Original phrasing or content from the source resume")
    tailored_text: str = Field(description="New tailored phrasing incorporating target keywords")
    rationale: str = Field(description="Clear explanation of why this change was made, what was changed from what, and which JD keyword was highlighted")


class UniversalTailoredOutput(BaseModel):
    fit_analysis: FitAnalysis
    tailored_resume: UniversalResume
    changes_log: list[ChangeAnnotation] = Field(default_factory=list)


def extract_course_grades(details: str) -> dict[str, tuple[str, str]]:
    """Extracts course-to-grade mappings from coursework details string."""
    if not details:
        return {}
    import re
    grades: dict[str, tuple[str, str]] = {}
    items = re.split(r"[,\|;\n]+", details)
    for it in items:
        it = it.strip()
        if not it:
            continue
        m = re.search(
            r"([A-Za-z0-9\s&/\+\-]+?)\s*(?:\(([0-9]{2,3}(?:\.[0-9]+)?(?:\s*%)?)\)|[:=–—\-]\s*([0-9]{2,3}(?:\.[0-9]+)?(?:\s*%)?))$",
            it,
        )
        if m:
            course = m.group(1).strip()
            grade = (m.group(2) or m.group(3)).strip()
            course = re.split(r"[\.]", course)[-1].strip()
            course = re.sub(
                r"^(?:Selected|Core|Relevant)?\s*(?:CS\s*)?Coursework\s*[:=–—\-]?\s*",
                "",
                course,
                flags=re.IGNORECASE,
            ).strip()
            if course and len(course) > 2 and not course.lower().startswith("gpa"):
                grades[course.lower()] = (course, f"({grade})")
    return grades


def restore_course_grades(tailored_details: str, original_details: str) -> str:
    """
    Guarantees that individual course grades present in the source resume or profile
    are never stripped when coursework is tailored or reordered for the target JD.
    """
    if not tailored_details or not original_details:
        return tailored_details
    import re
    orig_grades = extract_course_grades(original_details)
    if not orig_grades:
        return tailored_details
    res = tailored_details
    for c_key, (c_name, g_str) in orig_grades.items():
        pattern = re.compile(
            r"\b" + re.escape(c_name) + r"\b(?!\s*[\(:=–—\-]\s*[0-9])", re.IGNORECASE
        )
        res = pattern.sub(f"{c_name} {g_str}", res)
    return res


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

    # 3. Normalize contact social URLs to clickable https:// links, clearing any generic homepages
    if resume.contact.linkedin:
        if is_generic_social_url(resume.contact.linkedin):
            resume.contact.linkedin = ""
        else:
            resume.contact.linkedin = normalize_url(resume.contact.linkedin, "linkedin.com/in")
    if resume.contact.github:
        if is_generic_social_url(resume.contact.github):
            resume.contact.github = ""
        else:
            resume.contact.github = normalize_url(resume.contact.github, "github.com")

    # 4. Check additional_sections against spoken languages
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

