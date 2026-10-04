"""
Pytest configuration ensuring that all test suites use an isolated SQLite database,
preventing any test pollution from touching the live data/resume_tailor.db file.
"""

import os
import pytest
from pathlib import Path
from src.database import init_db


@pytest.fixture(autouse=True, scope="session")
def setup_test_db(tmp_path_factory):
    test_dir = tmp_path_factory.mktemp("test_db")
    test_db = test_dir / "test_resume_tailor.db"
    os.environ["RESUME_TAILOR_DB_PATH"] = str(test_db)
    init_db(test_db)
    yield
    if test_db.exists():
        try:
            test_db.unlink()
        except Exception:
            pass
