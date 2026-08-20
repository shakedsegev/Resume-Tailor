from dataclasses import dataclass

@dataclass
class Job:
    title: str
    company: str
    description: str
    url: str = ""
    source: str = ""