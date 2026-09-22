"""
Unified Data Models for Resume-Tailor.
Completely generic and extensible representations of candidate profiles,
resumes, and ATS tailoring analyses.
"""

from typing import Optional, Any
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


@dataclass
class TextBlock:
    text: str
    bold: bool = False
    font_size: float = 0.0


@dataclass
class ResumeShape:
    name: str
    blocks: list[TextBlock] = field(default_factory=list)


@dataclass
class ResumeContent:
    shapes: list[ResumeShape] = field(default_factory=list)



class PersonalInfo(BaseModel):
    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""


class ExperienceRecord(BaseModel):
    company: str
    role: str
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    bullets: list[str] = Field(default_factory=list)
    unlisted_nuances: list[str] = Field(
        default_factory=list,
        description="Deep technical context, tools used, or architectural nuances not fully listed on the resume.",
    )


class ProjectRecord(BaseModel):
    name: str
    technologies: list[str] = Field(default_factory=list)
    description: str = ""
    bullets: list[str] = Field(default_factory=list)
    deep_dive_details: str = Field(
        default="",
        description="Extended architectural, algorithmic, or implementation details from the candidate's background.",
    )


class EducationRecord(BaseModel):
    institution: str
    degree: str
    graduation_date: str = ""
    gpa: str = ""
    coursework: list[str] = Field(default_factory=list)
    honors_and_awards: list[str] = Field(default_factory=list)


class SkillSet(BaseModel):
    programming_languages: list[str] = Field(default_factory=list)
    frameworks_and_tools: list[str] = Field(default_factory=list)
    core_concepts: list[str] = Field(default_factory=list)
    spoken_languages: list[str] = Field(default_factory=list)


class BackgroundHighlight(BaseModel):
    category: str  # e.g., "Leadership", "Military Service", "Athletics", "Volunteering"
    title: str
    details: str


class CandidateProfile(BaseModel):
    """
    The candidate's master ground-truth profile.
    Contains all verified experience, projects, skills, and extended background
    that can be drawn upon to substantively tailor resumes without hallucinations.
    """
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    skills: SkillSet = Field(default_factory=SkillSet)
    experience: list[ExperienceRecord] = Field(default_factory=list)
    projects: list[ProjectRecord] = Field(default_factory=list)
    education: list[EducationRecord] = Field(default_factory=list)
    additional_background: list[BackgroundHighlight] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)


class FitAnalysis(BaseModel):
    """ATS Fit Analysis comparing candidate against a Job Description."""
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
    keyword_stats: dict[str, Any] = Field(
        default_factory=dict,
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
        description="1-2 sentences on how best to strategically position the candidate for this specific role.",
    )


class TailoredProjectItem(BaseModel):
    original_name: str
    tech_tags: str = Field(
        description="Tailored technology tags to display next to or beneath the project name."
    )
    description: str = Field(
        description="Tailored project description or bullet points highlighting relevant architecture."
    )


class TailoredExperienceItem(BaseModel):
    company: str
    role: str
    bullets: list[str] = Field(
        description="Rewritten, high-impact bullet points leading with JD-relevant achievements."
    )


class ChangeAnnotation(BaseModel):
    section: str = Field(description="Section name, e.g. Experience, Projects, Skills, Coursework")
    original_text: str = Field(description="Original phrasing or content from the source resume")
    tailored_text: str = Field(description="New tailored phrasing incorporating target keywords")
    rationale: str = Field(description="Clear explanation of why this change was made, what was changed from what, and which JD keyword or profile achievement was highlighted")


class GenericTailoredResume(BaseModel):
    """Universal tailored content schema ready to inject back into any design."""
    fit_analysis: FitAnalysis
    ordered_languages: list[str] = Field(
        default_factory=list,
        description="Programming languages reordered with top JD requirements first.",
    )
    ordered_tools: list[str] = Field(
        default_factory=list,
        description="Tools & platforms reordered with top JD requirements first.",
    )
    ordered_concepts: list[str] = Field(
        default_factory=list,
        description="Core concepts reordered with top JD requirements first.",
    )
    tailored_projects: list[TailoredProjectItem] = Field(default_factory=list)
    tailored_experience: list[TailoredExperienceItem] = Field(default_factory=list)
    tailored_coursework: str = Field(
        default="",
        description="Prioritized coursework string highlighting courses relevant to the JD.",
    )
    tailored_additional: list[dict[str, str]] = Field(default_factory=list)
    changes_log: list[ChangeAnnotation] = Field(default_factory=list)