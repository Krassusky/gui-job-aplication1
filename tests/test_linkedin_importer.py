"""Tests for LinkedIn export ZIP parsing."""

import zipfile
from pathlib import Path

import pytest

from core.linkedin_importer import parse_linkedin_export_zip


def _make_zip(files: dict[str, str]) -> Path:
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    path = Path(tmp.name)
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return path


class TestParseLinkedInExportZip:
    def test_parses_profile_and_positions(self):
        zip_path = _make_zip({
            "Profile.csv": "First Name,Last Name,Headline\nJane,Doe,Engineer\n",
            "Positions.csv": "Company Title,Description\nAcme,Software Engineer,Built APIs\n",
        })
        try:
            text = parse_linkedin_export_zip(zip_path)
            assert "Jane" in text
            assert "Acme" in text or "Software Engineer" in text
        finally:
            zip_path.unlink()

    def test_missing_files_raises(self):
        zip_path = _make_zip({"readme.txt": "hello"})
        try:
            with pytest.raises(ValueError, match="No recognizable"):
                parse_linkedin_export_zip(zip_path)
        finally:
            zip_path.unlink()
