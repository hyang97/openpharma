"""
Tests for RAG generation module, specifically citation extraction and renumbering.
"""
import pytest
from app.rag.generation import extract_and_renumber_citations, Citation
from app.retrieval import SearchResult


def create_mock_chunk(source_id: str, title: str, journal: str = "Test Journal") -> SearchResult:
    """Helper to create mock SearchResult objects for testing."""
    return SearchResult(
        chunk_id=1,
        section="results",
        content="Test content",
        query="test query",
        similarity_score=0.9,
        document_id=1,
        source_id=source_id,
        title=title,
        authors=["Author A", "Author B"],
        publication_date="2024-01-01",
        journal=journal,
        doi="10.1234/test"
    )


def test_single_citation_extraction():
    """Test extraction of single PMC citation."""
    answer_text = "GLP-1 agonists improve glycemic control [PMC12345678]."
    chunks = [create_mock_chunk("12345678", "Test Paper 1")]

    renumbered_answer, citations = extract_and_renumber_citations(answer_text, chunks)

    assert renumbered_answer == "GLP-1 agonists improve glycemic control [1]."
    assert len(citations) == 1
    assert citations[0].number == 1
    assert citations[0].source_id == "12345678"
    assert citations[0].title == "Test Paper 1"


def test_multiple_citations_comma_separated():
    """Test extraction of multiple citations in one bracket."""
    answer_text = "Studies show benefits [PMC11111111, PMC22222222] in patients."
    chunks = [
        create_mock_chunk("11111111", "Study A"),
        create_mock_chunk("22222222", "Study B")
    ]

    renumbered_answer, citations = extract_and_renumber_citations(answer_text, chunks)

    assert renumbered_answer == "Studies show benefits [1, 2] in patients."
    assert len(citations) == 2
    assert citations[0].source_id == "11111111"
    assert citations[1].source_id == "22222222"


def test_multiple_separate_citations():
    """Test extraction of citations in separate brackets."""
    answer_text = "GLP-1 works [PMC11111111] and reduces risk [PMC22222222]."
    chunks = [
        create_mock_chunk("11111111", "Study A"),
        create_mock_chunk("22222222", "Study B")
    ]

    renumbered_answer, citations = extract_and_renumber_citations(answer_text, chunks)

    assert renumbered_answer == "GLP-1 works [1] and reduces risk [2]."
    assert len(citations) == 2


def test_duplicate_citations():
    """Test that duplicate PMC IDs are only listed once."""
    answer_text = "First mention [PMC11111111] and second [PMC11111111] again."
    chunks = [create_mock_chunk("11111111", "Study A")]

    renumbered_answer, citations = extract_and_renumber_citations(answer_text, chunks)

    # Both should be renumbered to [1]
    assert renumbered_answer == "First mention [1] and second [1] again."
    assert len(citations) == 1  # Only one citation object


def test_order_preservation():
    """Test that citation order matches appearance order in text."""
    answer_text = "Third [PMC33333333], first [PMC11111111], second [PMC22222222]."
    chunks = [
        create_mock_chunk("11111111", "Study A"),
        create_mock_chunk("22222222", "Study B"),
        create_mock_chunk("33333333", "Study C")
    ]

    renumbered_answer, citations = extract_and_renumber_citations(answer_text, chunks)

    # Citations should be numbered in order of appearance
    assert renumbered_answer == "Third [1], first [2], second [3]."
    assert citations[0].source_id == "33333333"  # Appeared first
    assert citations[1].source_id == "11111111"  # Appeared second
    assert citations[2].source_id == "22222222"  # Appeared third


def test_missing_chunk_for_citation():
    """Test handling when LLM cites a PMC ID not in chunks."""
    answer_text = "Study shows [PMC99999999] this finding."
    chunks = [create_mock_chunk("11111111", "Study A")]  # Different ID

    renumbered_answer, citations = extract_and_renumber_citations(answer_text, chunks)

    # Should still renumber but not create citation object
    assert renumbered_answer == "Study shows [1] this finding."
    assert len(citations) == 0  # No matching chunk found


def test_mixed_citation_formats():
    """Test extraction with both single and comma-separated citations."""
    answer_text = "First [PMC11111111] and second [PMC22222222, PMC33333333] findings."
    chunks = [
        create_mock_chunk("11111111", "Study A"),
        create_mock_chunk("22222222", "Study B"),
        create_mock_chunk("33333333", "Study C")
    ]

    renumbered_answer, citations = extract_and_renumber_citations(answer_text, chunks)

    assert renumbered_answer == "First [1] and second [2, 3] findings."
    assert len(citations) == 3


def test_no_citations():
    """Test handling when answer has no citations."""
    answer_text = "This is an answer with no citations."
    chunks = [create_mock_chunk("11111111", "Study A")]

    renumbered_answer, citations = extract_and_renumber_citations(answer_text, chunks)

    assert renumbered_answer == "This is an answer with no citations."
    assert len(citations) == 0


def test_citation_metadata_mapping():
    """Test that citation objects include correct metadata from chunks."""
    answer_text = "Study findings [PMC11111111]."
    chunks = [
        SearchResult(
            chunk_id=42,
            section="results",
            content="Test content",
            query="test",
            similarity_score=0.95,
            document_id=100,
            source_id="11111111",
            title="Important Study",
            authors=["Smith J", "Doe A"],
            publication_date="2024-03-15",
            journal="Nature Medicine",
            doi="10.1234/example"
        )
    ]

    renumbered_answer, citations = extract_and_renumber_citations(answer_text, chunks)

    assert len(citations) == 1
    cit = citations[0]
    assert cit.number == 1
    assert cit.title == "Important Study"
    assert cit.journal == "Nature Medicine"
    assert cit.source_id == "11111111"
    assert cit.authors == ["Smith J", "Doe A"]
    assert cit.publication_date == "2024-03-15"
    assert cit.chunk_id == 42


def test_ignores_non_bracketed_pmc():
    """Test that PMC IDs outside brackets are ignored."""
    answer_text = "See PMC11111111 for details. Also [PMC22222222] is relevant."
    chunks = [
        create_mock_chunk("11111111", "Study A"),
        create_mock_chunk("22222222", "Study B")
    ]

    renumbered_answer, citations = extract_and_renumber_citations(answer_text, chunks)

    # Only bracketed PMC should be extracted
    assert "PMC11111111" in renumbered_answer  # Not in brackets, unchanged
    assert "[1]" in renumbered_answer  # PMC22222222 was in brackets
    assert len(citations) == 1
    assert citations[0].source_id == "22222222"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
