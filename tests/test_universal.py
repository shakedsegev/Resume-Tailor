from pathlib import Path
from src.universal_parser import extract_text_from_file
from src.universal_models import UniversalResume, ContactInfo, SkillCategories, EducationItem, ProjectItem, ExperienceItem
from src.universal_pdf_builder import render_resume_to_html, generate_universal_resume_pdf

TEMPLATE_PATH = Path("template.pptx") if Path("template.pptx").exists() else Path("Shaked Segev - CV.pptx")


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

    html_p, pdf_p = generate_universal_resume_pdf(resume, tmp_path, "test_resume", force_single_page=True)
    assert html_p.exists()
    assert html_p.stat().st_size > 0
    assert pdf_p.exists()
    assert pdf_p.stat().st_size > 0

    import pypdf
    reader = pypdf.PdfReader(str(pdf_p))
    assert len(reader.pages) == 1


def test_single_page_density_guardian_dense_resume(tmp_path):
    from src.universal_pdf_builder import count_pdf_pages
    # Create a dense resume with lots of bullets
    resume = UniversalResume(
        contact=ContactInfo(
            name="Alex Developer",
            email="alex@example.com",
            phone="+1-555-0199",
            location="New York, NY",
            linkedin="https://linkedin.com/in/alexdev",
            github="https://github.com/alexdev",
        ),
        summary="Principal Software Engineer with extensive experience building high-throughput distributed systems, microservice architectures, and real-time data pipelines.",
        skills=SkillCategories(
            programming_languages=["Python", "C++", "Java", "Go", "TypeScript", "Rust", "SQL", "Bash"],
            frameworks_and_tools=["Docker", "Kubernetes", "AWS", "Kafka", "PostgreSQL", "Redis", "Terraform", "Git"],
            core_concepts=["Distributed Systems", "Concurrency", "High Availability", "Microservices", "Design Patterns"],
        ),
        experience=[
            ExperienceItem(
                role="Lead Infrastructure Architect",
                company="Tech Global Systems",
                date_range="2021 - Present",
                bullets=[
                    "Spearheaded cloud migration of 45+ enterprise microservices to Kubernetes, achieving 99.99% system uptime.",
                    "Designed event-driven streaming pipeline leveraging Apache Kafka processing 250M events daily with sub-second latency.",
                    "Implemented zero-trust security architecture across distributed Kubernetes clusters reducing vulnerability exposure by 70%.",
                    "Mentored team of 14 engineers across 3 time zones, establishing high engineering standards and CI/CD best practices.",
                ],
            ),
            ExperienceItem(
                role="Senior Software Engineer",
                company="DataCore Solutions",
                date_range="2018 - 2021",
                bullets=[
                    "Architected high-concurrency caching layer in Go and Redis, slashing database query load by 60%.",
                    "Refactored legacy monolithic billing engine into scalable distributed microservices.",
                    "Optimized SQL indexing strategies and transaction isolation levels across multi-tenant PostgreSQL databases.",
                ],
            ),
        ],
        projects=[
            ProjectItem(
                name="Distributed Consensus Key-Value Store",
                technologies="Go, Raft, gRPC, Protobuf",
                description="Engineered distributed fault-tolerant Raft key-value database supporting linearizable reads and cluster resizing.",
                bullets=["Benchmarked 85,000 write ops/sec across 5-node cluster with zero data loss under simulated network partitions."],
            ),
            ProjectItem(
                name="Real-Time Network Telemetry Engine",
                technologies="Python, eBPF, ClickHouse",
                description="Low-overhead Linux kernel packet inspection and flow metric visualization pipeline.",
                bullets=["Captured packet-level performance telemetry with less than 1.5% CPU overhead."],
            ),
        ],
        education=[
            EducationItem(
                degree="M.Sc. in Computer Science",
                institution="Columbia University",
                date_range="2016 - 2018",
                gpa="3.95",
                details="Specialization in Distributed Systems & Network Architecture.",
            ),
            EducationItem(
                degree="B.Sc. in Computer Science",
                institution="New York University",
                date_range="2012 - 2016",
                gpa="3.90",
                details="Magna Cum Laude.",
            ),
        ],
    )

    html_p, pdf_p = generate_universal_resume_pdf(resume, tmp_path, "dense_resume", force_single_page=True)
    assert pdf_p.exists()
    pages = count_pdf_pages(pdf_p)
    assert pages == 1, f"Expected 1 page but got {pages} pages!"


def test_tailor_universal_resume_signature():
    import inspect
    from src.universal_ai import tailor_universal_resume
    sig = inspect.signature(tailor_universal_resume)
    assert "profile" in sig.parameters
    assert "resume" in sig.parameters
    assert "job_description" in sig.parameters


def test_candidate_agnostic_sanitizer():
    from src.universal_models import (
        UniversalResume,
        ContactInfo,
        SkillCategories,
        EducationItem,
        AdditionalSection,
        sanitize_universal_resume,
    )

    resume = UniversalResume(
        contact=ContactInfo(name="Morgan Taylor"),
        summary="Computer Science graduate from University of Oxford with a first-year GPA of 92 and strong expertise in systems architecture.",
        skills=SkillCategories(
            programming_languages=["Python", "Rust"],
        ),
        education=[
            EducationItem(
                degree="B.Sc. Computer Science",
                institution="University of Oxford",
                gpa="GPA: First Year GPA: 92",
                details="Coursework: Algorithms, Operating Systems | GPA: 92",
            )
        ],
        additional_sections=[
            AdditionalSection(title="Certifications", items=["AWS Certified Solutions Architect"]),
            AdditionalSection(title="Certifications", items=["Certified Kubernetes Administrator"]),
            AdditionalSection(title="Languages", items=["French (Fluent)", "German (Intermediate)"]),
            AdditionalSection(title="Publications", items=["Paper on distributed consensus in IEEE 2024"]),
        ],
    )

    sanitized = sanitize_universal_resume(resume)

    # 1. GPA must be purged from summary
    assert "92" not in sanitized.summary
    assert "GPA" not in sanitized.summary
    assert sanitized.summary.startswith("Computer Science graduate from University of Oxford with strong expertise")

    # 2. GPA in education must be normalized
    assert sanitized.education[0].gpa == "First Year: 92"
    assert "GPA: 92" not in sanitized.education[0].details

    # 3. Spoken languages must be absorbed into skills.spoken_languages
    assert "French (Fluent)" in sanitized.skills.spoken_languages
    assert "German (Intermediate)" in sanitized.skills.spoken_languages

    # 4. There must be ZERO duplicate headers in additional_sections
    titles = [s.title for s in sanitized.additional_sections]
    assert len(titles) == len(set(titles)), f"Duplicate headers found: {titles}"
    assert "Languages" not in titles

    # 5. Items with the same header must be grouped together under that header
    cert_sec = next(s for s in sanitized.additional_sections if s.title == "Certifications")
    assert "AWS Certified Solutions Architect" in cert_sec.items
    assert "Certified Kubernetes Administrator" in cert_sec.items
    assert len(cert_sec.items) == 2


def test_restore_course_grades():
    from src.universal_models import restore_course_grades, extract_course_grades

    orig = "Core CS Coursework: Intro to CS (91), Computational Models (90), Probability & Statistics (100), Computer Architecture (91), Data Structures, Systems Programming."
    tailored = "Computer Architecture, Systems Programming, Data Structures, Computational Models, Probability & Statistics."

    restored = restore_course_grades(tailored, orig)
    assert "(91)" in restored
    assert "(90)" in restored
    assert "(100)" in restored
    assert "Computer Architecture (91)" in restored
    assert "Computational Models (90)" in restored
    assert "Probability & Statistics (100)" in restored
    # Courses without grades originally should not have grades
    assert "Systems Programming (9" not in restored



