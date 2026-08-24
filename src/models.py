from dataclasses import dataclass, field

@dataclass
class Job:
    title: str
    company: str
    description: str
    url: str = ""
    source: str = ""

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