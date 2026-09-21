from pathlib import Path
from src.profile import load_profile

PROFILE_PATH = Path("profile.json")


def test_load_profile_success():
    assert PROFILE_PATH.exists()
    profile = load_profile(PROFILE_PATH)
    assert profile is not None
    assert "personal" in profile
    assert profile["personal"]["name"] == "Shaked Segev"
    assert "skills" in profile
    assert "Python" in profile["skills"]["programming_languages"]
    assert "C++" in profile["skills"]["programming_languages"]


def test_load_profile_missing():
    profile = load_profile(Path("non_existent_profile.json"))
    assert profile is None
