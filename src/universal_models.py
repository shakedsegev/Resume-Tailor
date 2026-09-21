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
        description="Spoken/natural languages with proficiency, e.g. 'English (Native Proficiency)', 'Hebrew (Native)'",
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

