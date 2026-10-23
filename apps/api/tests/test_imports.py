import pytest


def test_import_is_idempotent_for_same_pdf_bytes(client, tmp_path):
    fitz = pytest.importorskip("fitz")
    source = tmp_path / "lesson.pdf"
    document = fitz.open()
    document.new_page()
    document.save(source)
    document.close()
    payload = {
        "source_path": str(source),
        "title": "Source fixture",
        "level": "beginner",
        "volume_number": 1,
    }
    first = client.post("/api/v1/imports", json=payload)
    second = client.post("/api/v1/imports", json=payload)
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["already_imported"] is False
    assert second.json()["already_imported"] is True
    assert first.json()["source_document_id"] == second.json()["source_document_id"]
