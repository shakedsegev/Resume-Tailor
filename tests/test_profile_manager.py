from pathlib import Path
from src.models import CandidateProfile, PersonalInfo, SkillSet
from src.profile_manager import save_profile_file, load_profile_file
from src.sample_data import GENERIC_SAMPLE_PROFILE


def test_save_and_load_profile(tmp_path):
    profile = CandidateProfile(
        personal=PersonalInfo(name="Jordan Smith", email="jordan@example.com"),
        skills=SkillSet(programming_languages=["Python", "Go"]),
    )

    file_p = tmp_path / "jordan_profile.json"
    saved_p = save_profile_file(profile, file_p)
    assert saved_p.exists()

    loaded = load_profile_file(file_p)
    assert loaded is not None
    assert loaded.personal.name == "Jordan Smith"
    assert "Go" in loaded.skills.programming_languages


def test_generic_sample_profile_validity():
    profile = CandidateProfile.model_validate(GENERIC_SAMPLE_PROFILE)
    assert profile.personal.name == "Alex Morgan"
    assert len(profile.skills.programming_languages) >= 4
    assert len(profile.experience) >= 1
    assert len(profile.projects) >= 2


def test_candidate_profile_personal_info_alias():
    profile = CandidateProfile(
        personal=PersonalInfo(name="Dana Cohen", email="dana@example.com", linkedin="https://linkedin.com/in/danac"),
    )
    # Test property getter
    assert profile.personal_info.name == "Dana Cohen"
    assert profile.personal_info.linkedin == "https://linkedin.com/in/danac"

    # Test property setter
    profile.personal_info = PersonalInfo(name="Dana Lev", email="danalev@example.com")
    assert profile.personal.name == "Dana Lev"
    assert profile.personal_info.name == "Dana Lev"


def test_api_upload_profile_single_json():
    from fastapi.testclient import TestClient
    from src.web_app import app
    import json

    client = TestClient(app)
    sample_json = json.dumps(GENERIC_SAMPLE_PROFILE).encode("utf-8")

    response = client.post(
        "/api/profile/upload",
        files=[("profile_files", ("profile.json", sample_json, "application/json"))],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["personal"]["name"] == "Alex Morgan"


def test_api_upload_profile_multi_files(monkeypatch):
    from fastapi.testclient import TestClient
    from src.web_app import app
    from src.models import CandidateProfile, PersonalInfo

    captured_text = []

    def mock_convert(text, client=None):
        captured_text.append(text)
        return CandidateProfile(
            personal=PersonalInfo(name="Synthesized Candidate", email="synth@example.com"),
        )

    monkeypatch.setattr("src.web_app.convert_document_to_profile", mock_convert)

    client = TestClient(app)
    file1 = ("doc1.txt", b"Experience: Senior Engineer at TechCorp 2020-2023", "text/plain")
    file2 = ("doc2.md", b"# Projects\nBuilt high-throughput indexing engine in Go", "text/markdown")

    response = client.post(
        "/api/profile/upload",
        files=[("profile_files", file1), ("profile_files", file2)],
        data={"notes_text": "Additional note: GPA 3.9/4.0"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["personal"]["name"] == "Synthesized Candidate"
    assert len(captured_text) == 1
    assert "=== Source Document: doc1.txt ===" in captured_text[0]
    assert "=== Source Document: doc2.md ===" in captured_text[0]
    assert "=== Additional Background Notes ===" in captured_text[0]
    assert "GPA 3.9/4.0" in captured_text[0]

