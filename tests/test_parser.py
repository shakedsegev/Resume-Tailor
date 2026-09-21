from pathlib import Path
import pytest
from src.parser import extract_resume_sections, parse_resume

TEMPLATE_PATH = Path("Shaked Segev - CV.pptx")


def test_extract_resume_sections():
    assert TEMPLATE_PATH.exists(), "Template PPTX must exist"
    data = extract_resume_sections(TEMPLATE_PATH)

    assert "experience_bullets" in data
    assert len(data["experience_bullets"]) >= 5

    assert "academic_projects" in data
    assert len(data["academic_projects"]) == 3
    for proj in data["academic_projects"]:
        assert "title_line" in proj
        assert "description" in proj

    assert "coursework" in data
    assert "Systems Programming" in data["coursework"] or "Computer Architecture" in data["coursework"]

    assert "military_bullets" in data
    assert len(data["military_bullets"]) >= 2

    assert "tools_raw" in data
    assert len(data["tools_raw"]) == 4

    assert "concepts_raw" in data
    assert len(data["concepts_raw"]) == 2


def test_parse_resume():
    assert TEMPLATE_PATH.exists()
    content = parse_resume(TEMPLATE_PATH)
    assert len(content.shapes) > 0
