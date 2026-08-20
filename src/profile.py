from pathlib import Path
import json
from typing import Optional

def load_profile(profile_path: Path = Path("profile.json")) -> Optional[dict]:
    """
    Load a profile from a JSON file.

    Args:
        profile_path (Path): The path to the profile JSON file.

    Returns:
        Optional[dict]: The loaded profile data or None if the file is not found or invalid.
    """
    try:
        with open(profile_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None