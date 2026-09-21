"""
Generic Sample Data for Demonstration and Testing.
Completely free of any personal or private data.
"""

GENERIC_SAMPLE_PROFILE = {
    "personal": {
        "name": "Alex Morgan",
        "title": "Software Engineering Student",
        "email": "alex.morgan.dev@example.com",
        "phone": "+1 (555) 234-5678",
        "location": "San Francisco, CA",
        "linkedin": "https://linkedin.com/in/alexmorgandev",
        "github": "https://github.com/alexmorgandev"
    },
    "skills": {
        "programming_languages": ["Python", "C++", "Java", "TypeScript", "SQL"],
        "frameworks_and_tools": ["Docker", "Git", "Linux", "Bash", "VS Code", "WSL"],
        "core_concepts": ["Multithreading", "Concurrency", "Sockets", "OOP", "Memory Management", "SOLID Principles"],
        "spoken_languages": ["English", "Spanish"]
    },
    "experience": [
        {
            "company": "CloudScale Technologies",
            "role": "Technical Systems Specialist",
            "location": "San Francisco, CA",
            "start_date": "June 2023",
            "end_date": "August 2024",
            "bullets": [
                "Slashing client deployment wait times from 45 minutes to under 2 minutes by optimizing database queries and automation pipelines.",
                "Consulted core engineering teams on distributed debugging, low-level socket troubleshooting, and customer issue resolution.",
                "Authored 15+ comprehensive technical runbooks and led technical onboarding seminars for new engineering hires."
            ],
            "unlisted_nuances": [
                "Hands-on root cause analysis for distributed payment microservices.",
                "Wrote Python and Bash diagnostic scripts running inside Docker containers."
            ]
        }
    ],
    "projects": [
        {
            "name": "Distributed Pub/Sub Messaging Server",
            "technologies": ["Java", "C++", "Sockets", "Reactor Pattern"],
            "description": "High-throughput messaging server implementing custom protocols, thread-pool concurrency, and non-blocking I/O.",
            "bullets": [
                "Engineered socket-based client-server architecture handling concurrent streaming connections.",
                "Benchmarked throughput and achieved sub-5ms message dispatch latency."
            ],
            "deep_dive_details": "Implemented cross-language protocol communication between Java server and C++ client using raw TCP sockets."
        },
        {
            "name": "Parallel Linear Algebra Computation Engine",
            "technologies": ["Java", "Multithreading", "Synchronization"],
            "description": "High-performance matrix computation engine utilizing thread synchronization primitives for parallel calculations.",
            "bullets": [
                "Designed thread-safe shared resource managers preventing race conditions.",
                "Accelerated large matrix operations by 4.2x utilizing multicore CPU architectures."
            ],
            "deep_dive_details": "Fine-grained locking and custom worker pools optimized for cache locality."
        }
    ],
    "education": [
        {
            "institution": "University of California, Berkeley",
            "degree": "B.Sc. in Computer Science",
            "graduation_date": "2026 Expected",
            "gpa": "3.85",
            "coursework": [
                "Operating Systems",
                "Computer Architecture",
                "Data Structures & Algorithms",
                "Systems Programming"
            ],
            "honors_and_awards": ["Dean's Honor List (3 semesters)"]
        }
    ],
    "additional_background": [
        {
            "category": "Leadership",
            "title": "Lead Instructor & Squad Commander",
            "details": "Directed tactical teams under strict operational timelines; founded specialized operational logistics unit."
        }
    ],
    "target_roles": [
        "Software Engineering Student / Intern",
        "Backend Infrastructure Engineer"
    ]
}

GENERIC_SAMPLE_JD = """Backend Software Engineering Student / Intern
Cloud Infrastructure Team

About the Role:
We are seeking a driven Software Engineering Student to join our high-performance backend infrastructure team. You will build and scale distributed services, optimize socket communication protocols, and enhance system reliability.

Key Qualifications:
- Currently enrolled in a B.Sc. in Computer Science or related engineering discipline.
- Strong programming foundation in Python, C++, or Java.
- Solid understanding of multithreading, concurrency, thread-safety, and socket networking.
- Experience with Linux environments, Docker containers, and Git version control.
- Clear passion for writing clean, maintainable, and high-performance code.
- Excellent analytical debugging, root-cause analysis, and cross-functional communication skills.
"""
