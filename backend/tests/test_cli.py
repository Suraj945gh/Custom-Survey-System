"""python -m app.cli check <file>"""

from app.cli import main
from tests.conftest import SAMPLES


def test_sample_file_passes(capsys):
    assert main(["check", str(SAMPLES / "concave_sample_questionnaire.txt")]) == 0
    assert "no errors" in capsys.readouterr().out


def test_broken_file_lists_errors(capsys):
    assert main(["check", str(SAMPLES / "concave_broken_questionnaire.txt")]) == 1
    out = capsys.readouterr().out
    assert "11 error(s)" in out
    assert "Line 11" in out and "Line 58" in out


def test_missing_file(capsys, tmp_path):
    assert main(["check", str(tmp_path / "nope.txt")]) == 2
    assert "Cannot read" in capsys.readouterr().out


def test_file_that_is_not_text(capsys, tmp_path):
    binary = tmp_path / "photo.txt"
    binary.write_bytes(b"\xff\xfe\x00\x81\x82")
    assert main(["check", str(binary)]) == 2
