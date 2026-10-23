from app.ingestion import chunk_pages, extract_pages


def test_txt_extraction_and_chunking():
    pages = extract_pages("notes.txt", b"Section 1\nNigerian constitutional law", ocr_enabled=False)
    chunks = chunk_pages(pages, chunk_size=20, overlap=5)
    assert chunks
    assert all(item["page_number"] is None for item in chunks)
    assert "Nigerian" in " ".join(item["text"] for item in chunks)


def test_chunker_rejects_bad_overlap():
    try:
        chunk_pages([{"page_number": 1, "text": "example"}], chunk_size=10, overlap=10)
    except ValueError as exc:
        assert "greater than overlap" in str(exc)
    else:
        raise AssertionError("Expected invalid chunk settings to fail")
