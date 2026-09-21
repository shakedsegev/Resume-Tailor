from pathlib import Path
from src.universal_parser import extract_text_from_file
from src.universal_models import UniversalResume, ContactInfo, SkillCategories, EducationItem, ProjectItem, ExperienceItem
from src.universal_pdf_builder import render_resume_to_html, generate_universal_resume_pdf

TEMPLATE_PATH = Path("Shaked Segev - CV.pptx")


def test_extract_text_from_pptx():
    if TEMPLATE_PATH.exists():
        text = extract_text_from_file(TEMPLATE_PATH)
        assert len(text) > 200


def test_universal_pdf_generation(tmp_path):
    resume = UniversalResume(
        contact=ContactInfo(
            name="Jane Doe",
            email="jane@example.com",
            phone="+1-555-0199",
            location="San Francisco, CA",
            linkedin="https://linkedin.com/in/janedoe",
            github="https://github.com/janedoe",
        ),
        summary="Experienced Software Engineer specializing in backend distributed systems.",
        skills=SkillCategories(
            programming_languages=["Python", "Go", "C++"],
            frameworks_and_tools=["Docker", "Kubernetes", "Linux"],
            core_concepts=["Distributed Systems", "Concurrency", "OOP"],
        ),
        experience=[
            ExperienceItem(
                role="Senior Backend Engineer",
                company="Acme Corp",
                date_range="2022 - Present",
                bullets=[
                    "Engineered real-time data streaming pipeline handling 10k req/sec.",
                    "Optimized microservice database queries reducing P99 latency by 35%.",
                ],
            )
        ],
        projects=[
            ProjectItem(
                name="Cloud Cache Engine",
                technologies="Go, Redis, gRPC",
                description="High-performance in-memory distributed cache with Raft consensus.",
                bullets=["Implemented leader election and log replication."],
            )
        ],
        education=[
            EducationItem(
                degree="B.Sc. in Computer Science",
                institution="Stanford University",
                date_range="2018 - 2022",
                gpa="3.9",
                details="Core Coursework: Operating Systems, Distributed Algorithms.",
            )
        ],
    )

    html_p, pdf_p = generate_universal_resume_pdf(resume, tmp_path, "test_resume")
    assert html_p.exists()
    assert html_p.stat().st_size > 0
    assert pdf_p.exists()
    assert pdf_p.stat().st_size > 0
