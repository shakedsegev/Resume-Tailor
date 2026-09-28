from pathlib import Path
from src.universal_parser import extract_text_from_file
from src.universal_models import UniversalResume, ContactInfo, SkillCategories, EducationItem, ProjectItem, ExperienceItem
from src.universal_pdf_builder import render_resume_to_html, generate_universal_resume_pdf

TEMPLATE_PATH = Path("template.pptx")


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


def test_compute_multi_metric_fit():
    from src.universal_models import FitAnalysis, compute_multi_metric_fit

    jd_text = """
    We are looking for a Software Engineer with strong proficiency in Python, Docker, Kubernetes, C++, and PostgreSQL.
    Experience in distributed systems, microservices, and CI/CD is required.
    """
    resume_text = """
    Software Engineer with experience in Python, Docker, PostgreSQL, and distributed systems.
    Built microservices and scalable backend applications using modern practices.
    """

    initial_fit = FitAnalysis(
        match_score=0,
        match=["Proficient in Python and backend services", "Experience with distributed systems"],
        partial=["Familiarity with containerization (Docker)"],
        gap=["C++ low-level systems programming", "Kubernetes cluster administration"],
        recommendation="Strong candidate with minor gaps in C++ and Kubernetes orchestration.",
        experience_score=80,
    )

    result = compute_multi_metric_fit(initial_fit, resume_text, jd_text)

    # 1. Keywords verification
    stats = result.keyword_stats
    assert stats["total_count"] > 0
    assert stats["found_count"] > 0
    assert "python" in stats["matched_keywords"]
    assert "docker" in stats["matched_keywords"]
    assert "c++" in stats["missing_keywords"]
    assert result.keyword_score == round((stats["found_count"] / stats["total_count"]) * 100)

    # 2. Requirements score verification: 2 strong, 1 partial, 2 gaps -> (2*1.0 + 1*0.5)/5 = 2.5/5 = 50%
    assert result.requirements_score == 50

    # 3. Experience score preservation/bounds
    assert result.experience_score == 80

    # 4. Composite score check: round(0.40 * kw + 0.35 * 50 + 0.25 * 80)
    expected_composite = round(0.40 * result.keyword_score + 0.35 * result.requirements_score + 0.25 * result.experience_score)
    assert result.match_score == expected_composite

    # 5. Determinism check: same inputs yield exact same outputs
    fit_copy = FitAnalysis(
        match_score=0,
        match=["Proficient in Python and backend services", "Experience with distributed systems"],
        partial=["Familiarity with containerization (Docker)"],
        gap=["C++ low-level systems programming", "Kubernetes cluster administration"],
        recommendation="Strong candidate with minor gaps in C++ and Kubernetes orchestration.",
        experience_score=80,
    )
    result_repeat = compute_multi_metric_fit(fit_copy, resume_text, jd_text)
    assert result_repeat.match_score == result.match_score
    assert result_repeat.keyword_score == result.keyword_score
    assert result_repeat.requirements_score == result.requirements_score
    assert result_repeat.experience_score == result.experience_score
    assert result_repeat.keyword_stats == result.keyword_stats


def test_compute_multi_metric_fit_empty_edge_cases():
    from src.universal_models import FitAnalysis, compute_multi_metric_fit

    empty_fit = FitAnalysis(
        match_score=0,
        match=[],
        partial=[],
        gap=[],
        recommendation="",
    )
    # Should not raise ZeroDivisionError with empty texts and empty lists
    res = compute_multi_metric_fit(empty_fit, "", "")
    assert 0 <= res.keyword_score <= 100
    assert 0 <= res.requirements_score <= 100
    assert 0 <= res.experience_score <= 100
    assert 0 <= res.match_score <= 100


def test_normalize_url_and_extract_social_links():
    from src.universal_models import normalize_url, extract_social_links, sanitize_universal_resume

    # URL normalization
    assert normalize_url("linkedin.com/in/john-doe") == "https://www.linkedin.com/in/john-doe"
    assert normalize_url("http://github.com/johndoe") == "http://github.com/johndoe"
    assert normalize_url("github.com/johndoe") == "https://github.com/johndoe"
    assert normalize_url("https://www.linkedin.com/in/john-doe") == "https://www.linkedin.com/in/john-doe"

    # Social links regex extraction from raw text
    sample_text = """
    Software Engineer based in Tel Aviv
    Check out my profile: linkedin.com/in/dev-lead-42
    Open source contributions: https://github.com/lead-dev
    """
    links = extract_social_links(sample_text)
    assert "linkedin" in links
    assert "linkedin.com/in/dev-lead-42" in links["linkedin"]
    assert links["linkedin"].startswith("https://")
    assert "github" in links
    assert "github.com/lead-dev" in links["github"]
    assert links["github"].startswith("https://")

    # Sanitize auto-normalizes contact links
    res = UniversalResume(
        contact=ContactInfo(
            name="John Doe",
            linkedin="linkedin.com/in/john-doe",
            github="github.com/john-doe",
        ),
        skills=SkillCategories(),
    )
    sanitized = sanitize_universal_resume(res)
    assert sanitized.contact.linkedin.startswith("https://")
    assert sanitized.contact.github.startswith("https://")


def test_tournament_champion_synthesis():
    from src.universal_models import (
        UniversalResume,
        UniversalTailoredOutput,
        FitAnalysis,
        SkillCategories,
        ContactInfo,
    )
    from src.universal_ai import _synthesize_tournament_champion

    original = UniversalResume(
        contact=ContactInfo(name="Candidate"),
        skills=SkillCategories(
            programming_languages=["Python", "C++", "Go"],
            frameworks_and_tools=["Docker", "Linux", "Git"],
            core_concepts=["Distributed Systems", "Concurrency"],
        ),
    )

    cand1 = UniversalTailoredOutput(
        tailored_resume=UniversalResume(
            contact=ContactInfo(name="Candidate"),
            skills=SkillCategories(
                programming_languages=["Python", "C++"],
                frameworks_and_tools=["Docker"],
                core_concepts=["Concurrency"],
            ),
        ),
        fit_analysis=FitAnalysis(
            match_score=85,
            keyword_score=80,
            match=["Strong Python"],
            partial=[],
            gap=[],
        ),
    )

    cand2 = UniversalTailoredOutput(
        tailored_resume=UniversalResume(
            contact=ContactInfo(name="Candidate"),
            skills=SkillCategories(
                programming_languages=["Python"],
                frameworks_and_tools=["Docker", "Linux"],
                core_concepts=["Distributed Systems"],
            ),
        ),
        fit_analysis=FitAnalysis(
            match_score=92,
            keyword_score=90,
            match=["Strong Python", "Linux Systems"],
            partial=[],
            gap=[],
        ),
    )

    # Cand2 has higher match_score (92 > 85), so Cand2 is champion
    # Cand1 had verified skill 'C++' which is in original resume.
    # Tournament synthesis should merge 'C++' into the champion.
    champion = _synthesize_tournament_champion(
        candidates=[cand1, cand2],
        original_resume=original,
        profile=None,
        jd_text="Looking for C++ and Python engineer with Docker and Linux experience.",
    )

    assert champion.fit_analysis.match_score >= 90
    assert "C++" in champion.tailored_resume.skills.programming_languages
    assert "Linux" in champion.tailored_resume.skills.frameworks_and_tools


def test_recompile_pdf_endpoint(tmp_path):
    from fastapi.testclient import TestClient
    from src.web_app import app, OUTPUTS_DIR

    client = TestClient(app)

    base_name = "test_recompile_run"
    jd_content = "Senior Software Engineer requiring Python, Docker, and Redis."
    (OUTPUTS_DIR / f"{base_name}_jd.txt").write_text(jd_content, encoding="utf-8")

    resume_payload = {
        "contact": {
            "name": "Jane Recompiler",
            "email": "jane@example.com",
            "phone": "+1-555-1234",
            "location": "Boston, MA",
            "linkedin": "linkedin.com/in/janerecompiler",
            "github": "github.com/janerecompiler",
        },
        "summary": "Experienced engineer specializing in high-throughput microservices.",
        "skills": {
            "programming_languages": ["Python", "Go"],
            "frameworks_and_tools": ["Docker", "Redis"],
            "core_concepts": ["Concurrency", "REST APIs"],
            "spoken_languages": ["English"],
        },
        "experience": [
            {
                "role": "Backend Engineer",
                "company": "Tech Corp",
                "date_range": "2021 - 2024",
                "location": "Boston, MA",
                "bullets": [
                    "Engineered Redis caching layer improving response times by 40%.",
                    "Deployed Python microservices using Docker containers.",
                ],
            }
        ],
        "projects": [],
        "education": [],
        "additional_sections": [],
    }

    response = client.post(
        "/api/recompile-pdf",
        json={
            "filename_base": base_name,
            "resume": resume_payload,
            "jd_text": jd_content,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename_base"] == base_name
    assert "fit_analysis" in data
    assert "tailored_resume" in data
    assert data["tailored_resume"]["contact"]["linkedin"].startswith("https://")
    assert (OUTPUTS_DIR / f"{base_name}.pdf").exists()


def test_is_generic_social_url():
    from src.universal_models import is_generic_social_url
    assert is_generic_social_url("https://github.com") is True
    assert is_generic_social_url("https://github.com/") is True
    assert is_generic_social_url("https://github.com/GitHub") is True
    assert is_generic_social_url("https://linkedin.com") is True
    assert is_generic_social_url("https://linkedin.com/in/LinkedIn") is True
    assert is_generic_social_url("https://linkedin.com/in/") is True
    assert is_generic_social_url("github") is True
    assert is_generic_social_url("") is True

    # Real personal URLs should not be marked generic
    assert is_generic_social_url("https://github.com/shakedsegev") is False
    assert is_generic_social_url("https://www.linkedin.com/in/shaked-segev-424178298/") is False
    assert is_generic_social_url("https://linkedin.com/in/alexmorgan") is False


def test_format_social_display():
    from src.universal_models import format_social_display
    assert format_social_display("https://github.com/shakedsegev", "github") == "GitHub"
    assert format_social_display("https://www.linkedin.com/in/shaked-segev-424178298/", "linkedin") == "LinkedIn"
    assert format_social_display("https://github.com/shakedsegev", "") == "github.com/shakedsegev"
    assert format_social_display("", "linkedin") == ""


def test_recompile_pdf_score_preservation(tmp_path):
    from fastapi.testclient import TestClient
    from src.web_app import app, OUTPUTS_DIR
    from src.universal_models import FitAnalysis

    client = TestClient(app)
    base_name = "test_score_preservation_session"
    jd_content = "Looking for a Python and Go backend engineer with Docker and Concurrency experience."
    (OUTPUTS_DIR / f"{base_name}_jd.txt").write_text(jd_content, encoding="utf-8")

    initial_fit = FitAnalysis(
        match=["Python backend engineering", "Go concurrent services", "Docker containerization"],
        partial=["Kubernetes clusters"],
        gap=[],
        match_score=96,
        keyword_score=100,
        requirements_score=95,
        experience_score=94,
        pitch_angle="High-alignment candidate across core distributed systems.",
    )
    (OUTPUTS_DIR / f"{base_name}_fit.json").write_text(initial_fit.model_dump_json(indent=2), encoding="utf-8")

    resume_payload = {
        "contact": {
            "name": "Shaked Segev",
            "title": "Software Engineer",
            "email": "shaked@example.com",
            "phone": "+972-555-0100",
            "location": "Tel Aviv, Israel",
            "linkedin": "https://linkedin.com/in/shaked-segev-424178298",
            "github": "https://github.com/shakedsegev",
        },
        "summary": "Software engineer with background in Python and Go concurrent services and Docker.",
        "skills": {
            "programming_languages": ["Python", "Go"],
            "frameworks_and_tools": ["Docker"],
            "core_concepts": ["Concurrency"],
            "spoken_languages": ["English"],
        },
        "experience": [
            {
                "role": "Backend Engineer",
                "company": "Tech Corp",
                "date_range": "2022 - Present",
                "location": "Tel Aviv",
                "bullets": ["Engineered high-throughput Go and Python backend microservices."],
            }
        ],
        "projects": [],
        "education": [],
        "additional_sections": [],
    }

    # Recompile with only contact info modified
    response = client.post(
        "/api/recompile-pdf",
        json={
            "filename_base": base_name,
            "resume": resume_payload,
            "jd_text": jd_content,
        },
    )

    assert response.status_code == 200
    data = response.json()
    # The score should remain preserved (>= 94%), NOT plummet to 91% or 84%!
    assert data["fit_analysis"]["match_score"] >= 94
    assert data["tailored_resume"]["contact"]["github"] == "https://github.com/shakedsegev"
    assert data["tailored_resume"]["contact"]["linkedin"] == "https://linkedin.com/in/shaked-segev-424178298"






