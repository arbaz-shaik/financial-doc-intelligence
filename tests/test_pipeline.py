from pipeline.chunker import Chunker
from pipeline.sec_client import SECClient
from pipeline.parser import DocumentParser as parser
from unittest.mock import MagicMock,patch


class Test_chunk:

    def test_chunk_size_respected(self):
        text = "some long text " * 100
        chunk_size=521
        metadata = {
            "source": "sec",
            "doc_id": "test-doc",
            "company": "AAPL",
            "doc_type": "10-K",
            "date": "2025-09-27",
            "section": None
        }
        chunker = Chunker(chunk_size=chunk_size, chunk_overlap=50)
        chunks = chunker.chunk_text(text, metadata)
        for chunk in chunks:
            assert len(chunk.text) <= chunk_size, f"Chunk size exceeded: {len(chunk.text)} > {chunk_size}"
        
    def test_metadata_preserved(self):
        text = "some long text " * 100
        metadata = {
            "source": "sec",
            "doc_id": "test-doc",
            "company": "AAPL",
            "doc_type": "10-K",
            "date": "2025-09-27",
            "section": None
        }
    
        chunker = Chunker(chunk_size=521, chunk_overlap=50)
        chunks = chunker.chunk_text(text, metadata)
        for chunk in chunks:
            assert chunk.source == metadata["source"], f"Source metadata not preserved: {chunk.source} != {metadata['source']}"
            assert chunk.company == metadata["company"], f"Company metadata not preserved: {chunk.company} != {metadata['company']}"
            assert chunk.doc_type == metadata["doc_type"], f"Doc type metadata not preserved: {chunk.doc_type} != {metadata['doc_type']}"
            assert chunk.date == metadata["date"], f"Date metadata not preserved: {chunk.date} != {metadata['date']}"
            assert chunk.section == metadata["section"], f"Section metadata not preserved: {chunk.section} != {metadata['section']}"

    def test_chunk_overlap(self):
        text = "some long text " * 100
        chunk_size=521
        chunk_overlap=50
        metadata = {
            "source": "sec",
            "doc_id": "test-doc",
            "company": "AAPL",
            "doc_type": "10-K",
            "date": "2025-09-27",
            "section": None
        }
        chunker = Chunker(chunk_size, chunk_overlap)
        chunks = chunker.chunk_text(text, metadata)
    
        for  i in range(len(chunks) - 1):
            assert chunks[i].text[-chunk_overlap:] == chunks[i+1].text[:chunk_overlap], "Chunk size is invalid"

    def test_empty_text(self):
        text = ""
        chunk_size = 521
        chunk_overlap = 50
        metadata = {
            "source": "sec",
            "doc_id": "test-doc",
            "company": "AAPL",
            "doc_type": "10-K",
            "date": "2025-09-27",
            "section": None
            
        }
        chunker = Chunker(chunk_size, chunk_overlap)
        chunks = chunker.chunk_text(text,metadata)
        assert len(chunks)==0, "Empty Chunk no value produced"

    def test_html_cleanup(self):
        html = "<html><script>var x = 1;</script><p>Hello World</p></html>"
        p = parser()
        text = p.parse_html(html)
        assert "<script>" not in text, "Script tags should be removed"
        assert "Hello World" in text, "Content text should be preserved"

        
    def test_search_returns_results(self):
        with patch("pipeline.sec_client.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: {"filings": {"recent": {
                    "form": ["10-K", "8-K"],
                    "filingDate": ["2025-01-01", "2025-02-01"],
                    "accessionNumber": ["000-123", "000-456"],
                    "reportDate": ["2024-09-30", "2025-01-15"],
                    "primaryDocument": ["doc.htm", "doc2.htm"]
                }}}
            )
            client = SECClient("test agent")
            results = client.search("0000320193")
            assert len(results) == 1
            assert results[0]["filingDate"] == "2025-01-01"


 