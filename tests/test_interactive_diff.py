from pathlib import Path
from src.universal_models import (
    UniversalResume,
    ContactInfo,
    SkillCategories,
    EducationItem,
    ProjectItem,
    ExperienceItem,
    AdditionalSection,
    ChangeAnnotation,
)
from src.interactive_diff import build_interactive_resume_diff_html, highlight_text, find_matching_change


def test_highlight_text_matching():
    changes = [
        ChangeAnnotation(
            section="Experience",
            original_text="Diagnosed software issues.",
            tailored_text="Diagnosed and resolved complex low-level software and hardware issues, significantly reducing downtime.",
            rationale="Aligned with systems reliability requirements in target JD.",
        ),
        ChangeAnnotation(
            section="Projects",
            original_text="Built a C++ audio app.",
            tailored_text="Engineered an OOP-based audio processing application in C++ utilizing manual memory management.",
            rationale="Emphasized low-level C++ memory management required by Apple.",
        )
    ]

    # Test exact match
    h1 = highlight_text(
        text="Diagnosed and resolved complex low-level software and hardware issues, significantly reducing downtime.",
        section="Experience",
        changes_log=changes,
    )
    assert "change-highlight" in h1
    assert "data-original=\"Diagnosed software issues.\"" in h1
    assert "data-rationale=\"Aligned with systems reliability requirements in target JD.\"" in h1

    # Test fallback diff match
    h2 = highlight_text(
        text="Brand new bullet point tailored by strategy",
        section="Experience",
        changes_log=[],
        original_fallback="Old bullet point from resume",
    )
    assert "change-highlight" in h2
    assert "data-original=\"Old bullet point from resume\"" in h2

    # Test unchanged text (should NOT highlight)
    h3 = highlight_text(
        text="Same old bullet text that did not change at all",
        section="Experience",
        changes_log=changes,
        original_fallback="Same old bullet text that did not change at all",
    )
    assert "change-highlight" not in h3


def test_build_interactive_resume_diff_html(tmp_path):
    orig_resume = UniversalResume(
        contact=ContactInfo(
            name="Alex Morgan",
            email="alex@example.com",
            phone="+1-555-0199",
            location="San Francisco, CA",
            linkedin="https://linkedin.com/in/alexmorgan",
            github="https://github.com/alexmorgan",
        ),
        summary="Software engineer with backend experience.",
        skills=SkillCategories(
            programming_languages=["Python", "C++", "Java"],
            frameworks_and_tools=["Docker", "Linux"],
            core_concepts=["OOP", "Concurrency"],
        ),
        experience=[
            ExperienceItem(
                role="Software Engineer",
                company="TechCorp",
                date_range="2022 - 2024",
                bullets=[
                    "Developed backend microservices.",
                    "Maintained internal documentation.",
                ],
            )
        ],
        projects=[
            ProjectItem(
                name="Cache Server",
                technologies="C++",
                description="Built an in-memory cache server.",
                bullets=["Implemented LRU eviction."],
            )
        ],
        education=[
            EducationItem(
                degree="B.Sc. Computer Science",
                institution="University of Technology",
                date_range="2018 - 2022",
                gpa="3.85",
                details="Core Coursework: Operating Systems, Algorithms.",
            )
        ],
        additional_sections=[
            AdditionalSection(
                title="Leadership & Extracurriculars",
                items=["Team Lead for university coding hackathon."],
            )
        ],
    )

    tailored_resume = UniversalResume(
        contact=ContactInfo(
            name="Alex Morgan",
            email="alex@example.com",
            phone="+1-555-0199",
            location="San Francisco, CA",
            linkedin="https://linkedin.com/in/alexmorgan",
            github="https://github.com/alexmorgan",
        ),
        summary="High-performance systems software engineer specializing in low-level concurrency and memory safety.",
        skills=SkillCategories(
            programming_languages=["C++", "Python", "Java"],  # Reordered C++ to #1
            frameworks_and_tools=["Docker", "Linux", "gdb"],
            core_concepts=["Low-Level Memory Management", "Concurrency", "OOP"],
        ),
        experience=[
            ExperienceItem(
                role="Software Engineer",
                company="TechCorp",
                date_range="2022 - 2024",
                bullets=[
                    "Architected high-throughput microservices handling 10k req/sec with low latency.",
                    "Maintained internal documentation.",  # Unchanged
                ],
            )
        ],
        projects=[
            ProjectItem(
                name="Cache Server",
                technologies="C++, POSIX Sockets, Lock-Free Concurrency",
                description="Engineered an in-memory cache server utilizing atomic operations for lock-free concurrency.",
                bullets=["Implemented LRU eviction."],
            )
        ],
        education=[
            EducationItem(
                degree="B.Sc. Computer Science",
                institution="University of Technology",
                date_range="2018 - 2022",
                gpa="3.85",
                details="Core Coursework: Operating Systems (96), Advanced Concurrency, Algorithms.",
            )
        ],
        additional_sections=[
            AdditionalSection(
                title="Leadership & Extracurriculars",
                items=["Team Lead for university coding hackathon managing 12 developers."],
            )
        ],
    )

    changes = [
        ChangeAnnotation(
            section="Summary",
            original_text="Software engineer with backend experience.",
            tailored_text="High-performance systems software engineer specializing in low-level concurrency and memory safety.",
            rationale="Framed pitch specifically for low-level systems requirements.",
        ),
        ChangeAnnotation(
            section="Experience",
            original_text="Developed backend microservices.",
            tailored_text="Architected high-throughput microservices handling 10k req/sec with low latency.",
            rationale="Highlighted throughput scale and latency metrics matching JD expectations.",
        ),
        ChangeAnnotation(
            section="Projects",
            original_text="Built an in-memory cache server.",
            tailored_text="Engineered an in-memory cache server utilizing atomic operations for lock-free concurrency.",
            rationale="Demonstrated concurrency primitives relevant to multi-threaded architecture.",
        ),
    ]

    out_file = tmp_path / "diff_test.html"
    result_path = build_interactive_resume_diff_html(
        resume=tailored_resume,
        changes_log=changes,
        output_html_path=out_file,
        original_resume=orig_resume,
    )

    assert result_path.exists()
    content = result_path.read_text(encoding="utf-8")

    # Verify all resume sections exist
    assert "Alex Morgan" in content
    assert "alex@example.com" in content
    assert "+1-555-0199" in content
    assert "University of Technology" in content
    assert "GPA: 3.85" in content
    assert "TechCorp" in content
    assert "Cache Server" in content
    assert "Leadership & Extracurriculars" in content

    # Verify highlights exist
    assert 'class="change-highlight' in content
    assert "data-section=" in content
    assert "data-original=" in content
    assert "data-rationale=" in content

    # Verify unchanged bullet is NOT highlighted
    assert "Maintained internal documentation." in content
    # The unchanged bullet must appear as regular li content without change-highlight
    assert '<li>Maintained internal documentation.</li>' in content

    # Verify tooltip element and scripts
    assert 'id="tooltip"' in content
    assert "addEventListener('mouseenter'" in content
    assert "#dcfce7" in content
