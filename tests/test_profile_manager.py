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
