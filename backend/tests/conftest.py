from pathlib import Path

import pytest

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


@pytest.fixture
def sample_text() -> str:
    return (SAMPLES / "concave_sample_questionnaire.txt").read_text(encoding="utf-8")


@pytest.fixture
def broken_text() -> str:
    return (SAMPLES / "concave_broken_questionnaire.txt").read_text(encoding="utf-8")
