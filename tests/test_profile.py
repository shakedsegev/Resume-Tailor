from pathlib import Path
import json
from src.profile import load_profile


def test_load_profile_success(tmp_path):
    sample_data = {
        "personal": {"name": "Alex Doe", "degree": "B.Sc. Computer Science"},
        "skills": {"programming_languages": ["Python", "C++", "SQL"]},
    }
    file_p = tmp_path / "test_profile.json"
    file_p.write_text(json.dumps(sample_data), encoding="utf-8")

    profile = load_profile(file_p)
    assert profile is not None
    assert profile["personal"]["name"] == "Alex Doe"
    assert "Python" in profile["skills"]["programming_languages"]


def test_load_profile_missing():
    profile = load_profile(Path("non_existent_profile.json"))
    assert profile is None
