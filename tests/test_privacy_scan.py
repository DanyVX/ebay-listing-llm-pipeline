import pytest

from scripts.privacy_scan import private_terms, scan_blob


def test_clear_synthetic_text_passes():
    assert scan_blob(b"SKU SYN-001; synthetic product", "sample", []) == []


def test_detects_private_key_payload():
    marker = "-----BEGIN " + "PRIVATE KEY-----"
    sample = (marker + "\n" + "A" * 100).encode()
    assert scan_blob(sample, "sample", [])
    assert scan_blob(marker.encode(), "sample", []) == []


def test_external_denylist_detects_literal_without_echo():
    findings = scan_blob(b"private example value", "sample", ["Example Value"])
    assert len(findings) == 1
    assert "example value" not in findings[0].lower()


def test_denylist_must_be_outside_repository(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    path = root / "private.txt"
    path.write_text("secret", encoding="utf-8")
    monkeypatch.setenv("ELP_LOCAL_DENYLIST", str(path))
    with pytest.raises(ValueError, match="outside"):
        private_terms(root)


def test_external_denylist_loads(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "private.txt"
    outside.write_text("# comment\nprivate-synthetic-term\n", encoding="utf-8")
    monkeypatch.setenv("ELP_LOCAL_DENYLIST", str(outside))
    assert private_terms(root) == ["private-synthetic-term"]
